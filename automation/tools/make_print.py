#!/usr/bin/env python3
"""Build the two-page printable handout of the immigration calendar.

Reads relevant.ics (the same events as the public feeds), leaves out ESL, keeps a
two-week window, groups events by topic, merges weekly repeats into one entry, and gives
each entry a QR code holding the event itself (iCalendar text), so a phone camera can
add it to a calendar without visiting any website.

Usage:  python3 -I tools/make_print.py --start 2026-10-19 [--days 14] [--pdf]
Writes print/handout_<start>.html (and .pdf with --pdf, via Playwright/Chromium).
Short descriptions come from evaluation/print_blurbs.json (title -> 10 words or fewer).
"""
import argparse
import datetime as dt
import html
import json
import re
from collections import OrderedDict
from pathlib import Path
from zoneinfo import ZoneInfo

from reportlab.graphics.barcode.qrencoder import QRCode, QRErrorCorrectLevel

ROOT = Path(__file__).resolve().parent.parent
TZ = ZoneInfo("America/Los_Angeles")
UTC = dt.timezone.utc

TOPICS = [  # key, heading, one-line explainer
    ("legal", "Citizenship & Legal Help", "Citizenship classes, immigration services and legal information"),
    ("tables", "Resource Tables & Services", "Drop in and talk to service providers"),
    ("rights", "Know Your Rights & Civic Life", "Rights education, voting and civic engagement"),
    ("community", "Community & More", "Other events from immigrant-serving groups"),
]


# ---------- reading the calendar ----------

def unesc(s):
    return s.replace("\\n", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def prop(block, name):
    m = re.search(r"^" + name + r"((?:;[^:\r\n]*)?):(.*)$", block, flags=re.M)
    return (m.group(1), m.group(2).strip()) if m else ("", "")


def parse_dt(params, value):
    if not value:
        return None, False
    if "VALUE=DATE" in params or re.fullmatch(r"\d{8}", value):
        return dt.datetime.strptime(value[:8], "%Y%m%d").replace(tzinfo=TZ), True
    base = dt.datetime.strptime(value[:15], "%Y%m%dT%H%M%S")
    if value.endswith("Z"):
        return base.replace(tzinfo=UTC).astimezone(TZ), False
    return base.replace(tzinfo=TZ), False


def read_events():
    raw = (ROOT / "relevant.ics").read_text(encoding="utf-8")
    raw = re.sub(r"\r?\n[ \t]", "", raw)
    out = []
    for b in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", raw, flags=re.S):
        s, all_day = parse_dt(*prop(b, "DTSTART"))
        e, _ = parse_dt(*prop(b, "DTEND"))
        cats = [c.strip() for c in re.split(r"(?<!\\),", prop(b, "CATEGORIES")[1]) if c.strip()]
        out.append({
            "uid": prop(b, "UID")[1], "title": unesc(prop(b, "SUMMARY")[1]), "start": s, "end": e,
            "all_day": all_day, "location": unesc(prop(b, "LOCATION")[1]), "url": prop(b, "URL")[1],
            "desc": unesc(prop(b, "DESCRIPTION")[1]), "cats": [unesc(c) for c in cats],
            "label": prop(b, "X-SD-LABEL")[1].lower(), "source": unesc(prop(b, "X-SD-SOURCE-NAME")[1]),
        })
    return out


def topic_of(ev):
    c = set(ev["cats"])
    if c & {"Citizenship", "Immigration legal"}:
        return "legal"
    if "Tabling" in c:
        return "tables"
    if c & {"Rights & civic", "Housing"}:
        return "rights"
    return "community"


# ---------- text helpers ----------

def short_place(loc):
    """'El Cajon Branch Library, 201 E. Douglas, El Cajon, CA 92020' -> without state, zip, country."""
    if not loc:
        return "Location: see organizer"
    parts = [p.strip() for p in loc.split(",")]
    parts = [p for p in parts if p and not re.fullmatch(r"(CA|California)?\s*\d{5}(-\d{4})?", p)
             and p not in ("CA", "US", "USA", "United States", "California")]
    out = []
    for p in parts:  # drop repeats ("Thomas Jefferson School of Law - Thomas Jefferson School of Law")
        p = re.sub(r"\s+(CA|California)\s+\d{5}$", "", p)
        p = re.sub(r"^(.+?) - \1", r"\1", p)
        if p not in out:
            out.append(p)
    return ", ".join(out)


def qr_place(loc):
    """Shorter place for the QR code: venue and street, without the city when the venue names it."""
    parts = short_place(loc).split(", ")
    return ", ".join(parts[:2]) if len(parts) > 2 else ", ".join(parts)


def blurb(ev, blurbs):
    if ev["title"] in blurbs:
        return blurbs[ev["title"]]
    words = re.sub(r"https?://\S+", "", ev["desc"].split("\n\n")[0]).split()
    return " ".join(words[:10]) + ("…" if len(words) > 10 else "")


def fmt_time(t):
    s = t.strftime("%-I:%M").replace(":00", "")
    return s + ("am" if t.hour < 12 else "pm")


def fmt_span(ev):
    if ev["all_day"]:
        return "Time: see organizer"
    a, b = ev["start"], ev["end"]
    if b and b > a:
        same = (a.hour < 12) == (b.hour < 12)
        return (fmt_time(a)[:-2] if same else fmt_time(a)) + "–" + fmt_time(b)
    return fmt_time(a)


def fmt_dates(starts):
    """[Mon Oct 19, Mon Oct 26] -> 'Mon, Oct 19 & 26'; different weekdays listed in full."""
    if len(starts) == 1:
        return starts[0].strftime("%a, %b %-d")
    if len({d.strftime("%a") for d in starts}) == 1:
        days, cur = [], None
        for d in starts:
            days.append(d.strftime("%b %-d") if d.strftime("%b") != cur else d.strftime("%-d"))
            cur = d.strftime("%b")
        return starts[0].strftime("%a, ") + (", ".join(days[:-1]) + " & " + days[-1])
    return " · ".join(d.strftime("%a %b %-d") for d in starts)


# ---------- QR (iCalendar event text) ----------

def ical_text(ev, starts, short):
    def z(t):
        return t.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")

    def esc(s):
        return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
    lines = ["BEGIN:VEVENT", "SUMMARY:" + esc(ev["title"])]
    if ev["all_day"]:
        lines += ["DTSTART;VALUE=DATE:" + ev["start"].strftime("%Y%m%d"),
                  "DTEND;VALUE=DATE:" + (ev["start"] + dt.timedelta(days=1)).strftime("%Y%m%d")]
    else:
        lines.append("DTSTART:" + z(ev["start"]))
        if ev["end"]:
            lines.append("DTEND:" + z(ev["end"]))
    weekly = len(starts) > 1 and all((b - a).days == 7 for a, b in zip(starts, starts[1:]))
    if weekly:
        lines.append(f"RRULE:FREQ=WEEKLY;COUNT={len(starts)}")
    if ev["location"]:
        lines.append("LOCATION:" + esc(qr_place(ev["location"])))
    lines.append("DESCRIPTION:" + esc(short))
    if ev["url"]:
        lines.append("URL:" + ev["url"])
    lines.append("END:VEVENT")
    return "\n".join(lines), weekly


def qr_svg(text):
    q = QRCode(None, QRErrorCorrectLevel.L)
    q.addData(text.encode("utf-8").decode("latin-1"))  # 8-bit mode carries the UTF-8 bytes
    q.make()
    n = q.getModuleCount()
    path = "".join(f"M{c + 2},{r + 2}h1v1h-1z" for r in range(n) for c in range(n) if q.isDark(r, c))
    return (f'<svg class="qr" viewBox="0 0 {n + 4} {n + 4}" shape-rendering="crispEdges" '
            f'xmlns="http://www.w3.org/2000/svg"><path d="{path}" fill="#1b2a3a"/></svg>'), n


# ---------- folk motif (original geometric SVG, used sparingly) ----------

def motif_band(width_units=40):
    unit = (
        # tulip: three petals on a stem, deep red
        '<path d="M12 4 C10 7 10 10 12 12 C14 10 14 7 12 4Z" fill="var(--red)"/>'
        '<path d="M12 12 C9 11 7 8 7 6 C9 7 11 9 12 12Z M12 12 C15 11 17 8 17 6 C15 7 13 9 12 12Z" fill="var(--red)"/>'
        '<path d="M12 12 V19" stroke="var(--green)" stroke-width="1.1"/>'
        '<path d="M12 17 C10 16 8.5 16 8 17.5 C9.5 18 11 17.8 12 17Z M12 17 C14 16 15.5 16 16 17.5 C14.5 18 13 17.8 12 17Z" fill="var(--green)"/>'
        # diamond with dot, blue
        '<path d="M30 7 L34 11.5 L30 16 L26 11.5Z" fill="none" stroke="var(--blue)" stroke-width="1.1"/>'
        '<circle cx="30" cy="11.5" r="1.3" fill="var(--blue)"/>'
    )
    body = "".join(f'<g transform="translate({i * 36},0)">{unit}</g>' for i in range(width_units))
    return (f'<svg class="band" viewBox="0 0 {width_units * 36} 22" preserveAspectRatio="xMinYMid slice" '
            f'xmlns="http://www.w3.org/2000/svg">'
            f'<path d="M0 1 H{width_units * 36} M0 21 H{width_units * 36}" stroke="var(--blue)" stroke-width="0.8"/>'
            f'{body}</svg>')


ROSETTE = ('<svg class="rosette" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
           + "".join(f'<ellipse cx="12" cy="6.2" rx="2.3" ry="4.6" fill="var(--red)" transform="rotate({a} 12 12)"/>'
                     for a in range(0, 360, 45))
           + '<circle cx="12" cy="12" r="2.6" fill="#fff" stroke="var(--blue)" stroke-width="1.2"/></svg>')

HEART = ('<svg class="mark" viewBox="0 0 12 12" xmlns="http://www.w3.org/2000/svg">'
         '<path d="M6 10.5 C2 7.5 1 5.5 2.2 3.6 C3.4 2 5.2 2.4 6 3.8 C6.8 2.4 8.6 2 9.8 3.6 C11 5.5 10 7.5 6 10.5Z" '
         'fill="none" stroke="var(--red)" stroke-width="1.2"/></svg>')


CSS = """
@page { size: Letter; margin: 0.45in 0.5in 0.55in; }
:root { --red:#a63a2b; --blue:#1f3d5c; --green:#4f6e4a; --ink:#1b2a3a; --muted:#5b6672; --rule:#d9d2c3; }
* { box-sizing: border-box; }
html, body { margin:0; background:#fff; color:var(--ink); font-family: Inter, "DejaVu Sans", sans-serif; font-size: 8.4pt; line-height: 1.28; }
.band { display:block; width:100%; height:0.24in; }
header { margin: 0.06in 0 0.1in; display:grid; grid-template-columns: 1fr auto; gap: 0.2in; align-items:end; }
h1 { font-family: "Inter Display", Inter, sans-serif; font-weight: 800; font-size: 19pt; line-height:1.05; margin:0; letter-spacing:-0.01em; color:var(--blue); }
.sub { margin-top: 3pt; font-size: 9.5pt; color: var(--ink); }
.sub b { color: var(--red); }
.howto { font-size: 7.4pt; color: var(--muted); max-width: 2.55in; text-align:left; border-left: 1.5pt solid var(--red); padding-left: 7pt; }
.howto p { margin: 0 0 2pt; }
.mark { width: 8pt; height: 8pt; vertical-align: -1pt; }
main { column-count: 2; column-gap: 0.28in; column-rule: 0.5pt solid var(--rule); }
section { break-inside: auto; }
h2 { break-after: avoid; display:flex; align-items:center; gap:5pt; margin: 2pt 0 1pt; font-family:"Inter Display", Inter, sans-serif; font-size: 11pt; font-weight: 750; color: var(--blue); }
h2 + .topic-note { margin: 0 0 4pt; color: var(--muted); font-size: 7.4pt; }
.rosette { width: 12pt; height: 12pt; flex: none; }
.ev { break-inside: avoid; display:grid; grid-template-columns: 1fr 0.92in; gap: 6pt; padding: 4.5pt 0 5pt; border-top: 0.5pt solid var(--rule); }
.when { font-weight: 700; color: var(--red); font-size: 8pt; }
.title { font-weight: 700; font-size: 9pt; margin: 1pt 0; }
.where, .who { color: var(--muted); font-size: 7.6pt; }
.desc { margin-top: 1pt; }
.qr { width: 0.92in; height: 0.92in; display:block; margin-top: 1pt; }
section + section { margin-top: 6pt; }
"""


QR_LOG = []


def build(start, days):
    end = start + dt.timedelta(days=days)
    blurbs = json.loads((ROOT / "evaluation" / "print_blurbs.json").read_text(encoding="utf-8"))
    evs = [e for e in read_events() if "ESL" not in e["cats"] and start <= e["start"].date() < end]
    evs.sort(key=lambda e: e["start"])
    series = OrderedDict()  # same title, place and time of day -> one entry
    for e in evs:
        key = (e["title"], e["location"], e["all_day"] or e["start"].strftime("%H%M"))
        series.setdefault(key, []).append(e)
    by_topic = {k: [] for k, _, _ in TOPICS}
    for group in series.values():
        by_topic[topic_of(group[0])].append(group)

    sections = []
    for key, heading, note in TOPICS:
        items = []
        for group in by_topic[key]:
            ev = group[0]
            starts = [g["start"] for g in group]
            short = blurb(ev, blurbs)
            text, weekly = ical_text(ev, starts, short)
            svg, n = qr_svg(text)
            QR_LOG.append((n, len(text.encode()), ev["title"], text))
            possibly = any(g["label"] == "possibly" for g in group)
            items.append(f"""
<article class="ev">
  <div>
    <div class="when">{html.escape(fmt_dates(starts))} · {html.escape(fmt_span(ev))}</div>
    <div class="title">{HEART if possibly else ""}{html.escape(ev["title"])}</div>
    <div class="where">{html.escape(short_place(ev["location"]))}</div>
    <div class="desc">{html.escape(short)}</div>
    <div class="who">{html.escape(ev["source"])}</div>
  </div>
  {svg}
</article>""")
        if items:
            sections.append(f'<section><h2>{ROSETTE}{heading}</h2><p class="topic-note">{note}</p>{"".join(items)}</section>')

    last = end - dt.timedelta(days=1)
    rng = f"{start.strftime('%B %-d')} – {last.strftime('%B %-d, %Y')}" if start.month != last.month \
        else f"{start.strftime('%B %-d')} – {last.strftime('%-d, %Y')}"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Immigration Resources & Events – San Diego County</title><style>{CSS}</style></head><body>
{motif_band()}
<header>
  <div>
    <h1>Immigration Resources &amp; Events<br>in San Diego County</h1>
    <div class="sub"><b>{rng}</b> · Free and low-cost help for immigrants, refugees and their families</div>
  </div>
  <div class="howto">
    <p><b>Scan a code</b> with your phone camera to add the event to your calendar.</p>
    <p>{HEART} = may be of interest. Events can change; check with the organizer before you go.</p>
  </div>
</header>
<main>{"".join(sections)}</main>
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--pdf", action="store_true")
    a = ap.parse_args()
    start = dt.date.fromisoformat(a.start)
    out = ROOT / "print"
    out.mkdir(exist_ok=True)
    page = out / f"handout_{start}.html"
    page.write_text(build(start, a.days), encoding="utf-8")
    print("wrote", page)
    big = max(QR_LOG)[0] if QR_LOG else 0
    print(f"QR codes: {len(QR_LOG)}, largest {big} modules ({0.92 * 25.4 / (big + 4):.2f} mm per module at 0.92 in)")
    (out / f"qr_{start}.json").write_text(json.dumps([t for *_, t in QR_LOG], ensure_ascii=False, indent=0), encoding="utf-8")
    if a.pdf:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page()
            pg.goto(page.as_uri())
            pdf = page.with_suffix(".pdf")
            foot = ('<div style="width:100%;font-family:Inter,sans-serif;font-size:7px;color:#5b6672;'
                    'padding:0 0.5in;display:flex;justify-content:space-between">'
                    '<span>Provided by San Diego Public Library</span>'
                    f'<span>Updated {dt.date.today().strftime("%B %-d, %Y")} · Page <span class="pageNumber"></span> of <span class="totalPages"></span></span></div>')
            pg.pdf(path=str(pdf), format="Letter", print_background=True, prefer_css_page_size=True,
                   display_header_footer=True, header_template="<span></span>", footer_template=foot)
            b.close()
        print("wrote", pdf)


if __name__ == "__main__":
    main()
