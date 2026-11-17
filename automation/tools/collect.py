#!/usr/bin/env python3
"""Collect the sources that allow automated visits, and write them to raw/ in the same
formats the hand-run browser collectors used, so build_batch.py reads them unchanged.

  County Library            BiblioCommons RSS          -> raw/sdcl_rss_extract.txt
  Oceanside, Escondido,     iCal feeds                 -> raw/<name>.tsv
  Coronado, Legal Aid,
  SDVLP, MAAC, Casa Familiar
  JFS, Alliance San Diego   events pages               -> raw/auto_events.json

Not collected here (they refuse automated visits or have no structure): Carlsbad, Chula Vista,
National City, Instagram and the other agency pages. Those come from the monthly hand-run pass
and stay in raw/ as last collected.

If a source fails, its previous raw file is kept and the failure is counted in state.json.
Usage: python3 tools/collect.py [--days 31]      Exit code 0 always; problems go to state.json.
"""
import argparse, datetime as dt, html, json, re, sys, time, urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw"
UA = "Mozilla/5.0 (compatible; sd-immigration-calendar/1.0; +https://www.libraryfresh.com/sd-immigration-calendar/)"

ICAL_FEEDS = {  # raw file stem -> (label for the header line, feed address)
    "oceanside": ("oceanside LibraryCalendar iCal feed", "https://oceansidepl.librarycalendar.com/events/feed/ical?age_groups%5B25%5D=25&age_groups%5B98%5D=98&program_types%5B165%5D=165&program_types%5B112%5D=112&program_types%5B163%5D=163"),
    "escondido": ("escondido LibraryCalendar iCal feed", "https://escondido.librarycalendar.com/events/feed/ical?age_groups%5B4%5D=4&program_types%5B90%5D=90&program_types%5B160%5D=160&program_types%5B91%5D=91&program_types%5B102%5D=102&program_types%5B103%5D=103"),
    "coronado": ("coronado LibraryCalendar iCal feed", "https://coronado.librarycalendar.com/events/feed/ical?age_groups%5B30%5D=30&age_groups%5B101%5D=101"),
    "lassd": ("lassd The Events Calendar feed", "https://www.lassd.org/events/list/?ical=1"),
    "sdvlp": ("sdvlp The Events Calendar feed", "https://sdvlp.org/events/list/?ical=1"),
    "maac": ("maac The Events Calendar feed", "https://maacproject.org/events/list/?ical=1"),
    "casafamiliar": ("casafamiliar The Events Calendar feed", "https://www.casafamiliar.org/events/list/?ical=1"),
}
SDCL = "https://gateway.bibliocommons.com/v2/libraries/sdcl/rss/events?types=60d3d4f817df9637003ba141%2C60d3d686618cfb3000ddb6c4%2C60d3d5c99880a342007cde20&page="
JFS = "https://www.jfssd.org/calendar/"
ALLIANCE = "https://www.alliancesd.org/events/"


def fetch(url, tries=2):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=45) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001 - any failure means "source unavailable this run"
            last = e
            time.sleep(5)
    raise RuntimeError(f"{type(last).__name__}: {last}")


def shorten(x, strip_trailing_backslash=False):
    if len(x.encode("utf-16-le")) > 600:  # 300 UTF-16 units, as the browser snippets counted
        x = x.encode("utf-16-le")[:600].decode("utf-16-le", "ignore")
        if strip_trailing_backslash:
            x = re.sub(r"\\+$", "", x)
        x = re.sub(r"\s\S*$", "", x) + " …"
    return x


# ---------- iCal feeds -> compact TSV (same columns as the FEED_TSV browser snippet) ----------
def ical_to_tsv(text, a, b):
    """a, b: YYYYMMDD window. Returns (total events in feed, kept lines)."""
    t = re.sub(r"\n[ \t]", "", text.replace("\r\n", "\n").replace("\r", "\n"))
    events = re.findall(r"BEGIN:VEVENT.*?END:VEVENT", t, flags=re.S)

    def g(e, k):
        m = re.search(rf"^{k}([;:][^\r\n]*)$", e, flags=re.M)
        return m.group(1).replace("\t", " ") if m else ""

    def desc(v):
        if not v:
            return ""
        x = v[v.index(":") + 1:]
        x = re.sub(r"<[^>]+>", " ", x)
        x = re.sub(r"&nbsp;|&amp;nbsp;", " ", x)
        x = re.sub(r"(\\n)+", " ", x)
        x = shorten(re.sub(r"\s+", " ", x).strip(), strip_trailing_backslash=True)
        return ":" + x if x else ""

    out = []
    for e in events:
        m = re.search(r"DTSTART[^:\n]*:(\d{8})", e)
        if not m or not (a <= m.group(1) <= b):
            continue
        out.append("\t".join([g(e, "UID"), g(e, "DTSTART"), g(e, "DTEND"), g(e, "SUMMARY"), g(e, "LOCATION"), g(e, "ROOM"),
                              g(e, "URL"), g(e, "CATEGORIES"), g(e, "STATUS"), desc(g(e, "DESCRIPTION"))]))
    return len(events), out


# ---------- County Library RSS ----------
class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, d):
        self.parts.append(d)


def html_text(s):
    p = _Text()
    p.feed(s)
    p.close()
    return "".join(p.parts)


def _cdata(s):
    s = s.strip()
    m = re.fullmatch(r"<!\[CDATA\[(.*)\]\]>", s, flags=re.S)
    return m.group(1) if m else html.unescape(s)


def sdcl_items(xml):
    """One RSS page -> list of (line, start_local)."""
    out = []
    for it in re.findall(r"<item>(.*?)</item>", xml, flags=re.S):
        def g(tag, src=it):
            m = re.search(rf"<{tag}(?:\s[^>]*)?>(.*?)</{tag}>", src, flags=re.S)
            return _cdata(m.group(1)).strip() if m else ""
        loc = re.search(r"<bc:location>(.*?)</bc:location>", it, flags=re.S)
        loc = loc.group(1) if loc else ""
        lg = (lambda tag: g(tag, loc)) if loc else (lambda tag: "")
        cats = ";".join(_cdata(c).strip() for c in re.findall(r"<category>(.*?)</category>", it, flags=re.S))
        d = re.sub(r"\s+", " ", html_text(g("description"))).replace("|", "/").strip()
        d = shorten(d)
        gid = g("guid").split("/")[-1]
        s = g("bc:start_date_local")
        addr = ", ".join(x for x in [(lg("bc:number") + " " + lg("bc:street")).strip(), lg("bc:city"), lg("bc:zip")] if x)
        line = " || ".join([gid, g("title"), s, g("bc:end_date_local"), lg("bc:name"), addr, g("link"),
                            g("bc:is_cancelled"), g("bc:is_virtual"), cats, d])
        out.append((gid, line.replace("\n", " "), s))
    return out


def collect_sdcl(aiso, biso):
    lines, seen, last = [], set(), ""
    for p in range(1, 16):
        items = sdcl_items(fetch(SDCL + str(p)))
        if not items:
            break
        for gid, line, s in items:
            if gid in seen:
                continue
            seen.add(gid)
            lines.append(line)
            last = s
        if last[:10] > biso:
            break
        time.sleep(1)
    if not lines:
        raise RuntimeError("no items in the RSS feed")
    keep = []
    for l in lines:
        f = l.split(" || ")
        if f[2][:10] <= biso and (f[3] or f[2])[:10] >= aiso:
            keep.append(l)
    return keep


# ---------- JFS and Alliance San Diego events pages ----------
def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def _clock(s):
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?", s.strip().lower())
    if not m:
        return None
    h = int(m.group(1)) % 12 + (12 if m.group(3) == "p" else 0)
    return f"{h:02d}:{m.group(2) or '00'}"


def jfs_events(page):
    out = []
    for b in re.split(r'<div class="event_listing ', page)[1:]:
        title = re.search(r'wpem-heading-text">(.*?)<', b, flags=re.S)
        when = re.search(r'wpem-event-date-time-text">(.*?)</span>', b, flags=re.S)
        if not title or not when:
            continue
        m = re.search(r"(\d{2})-(\d{2})-(\d{4})\s*\|\s*([^‒–-]+?)\s*[‒–-]\s*(.+)", clean(when.group(1)))
        if not m:
            continue
        day = f"{m.group(3)}-{m.group(1)}-{m.group(2)}"
        t0, t1 = _clock(m.group(4)), _clock(m.group(5))
        loc = re.search(r'wpem-event-location-text">(.*?)</span>', b, flags=re.S)
        loc = clean(re.sub(r"<br\s*/?>", ", ", loc.group(1))).strip(" ,") if loc else ""
        ex = re.search(r'wpem-event-excerpt">(.*?)</div>', b, flags=re.S)
        url = re.search(r'href="([^"]+)"', b)
        url = url.group(1).split("#new_tab")[0] if url else JFS
        cats = sorted({c.replace("-", " ").title() for c in re.findall(r"event_listing_category-([a-z0-9-]+)", b.split('"')[0])})
        out.append({"source_id": "jfs", "source_name": "Jewish Family Service of San Diego", "route": "page",
                    "title": clean(title.group(1)), "start": f"{day}T{t0}" if t0 else day,
                    "end": f"{day}T{t1}" if t0 and t1 else None, "location": loc, "url": url,
                    "description": clean(ex.group(1)) if ex else "", "categories": cats,
                    "note": "Read automatically from the JFS events calendar page"})
    return out


def alliance_events(page):
    out, seen = [], set()
    for b in re.findall(r'<article class="post-card".*?</article>', page, flags=re.S):
        url = re.search(r'href="(https://www\.alliancesd\.org/event/[^"]+)"', b)
        title = re.search(r"<h\d[^>]*>\s*<a [^>]*>(.*?)</a>", b, flags=re.S)
        date = re.search(r'class="date left-bordered">(.*?)<', b, flags=re.S)
        if not (url and title and date):
            continue
        try:
            day = dt.datetime.strptime(clean(date.group(1)), "%B %d, %Y").date().isoformat()
        except ValueError:
            continue
        foot = re.search(r'class="date-location">(.*?)</div>', b, flags=re.S)
        start, loc = day, ""
        if foot:
            tm = re.search(r"\d{4}\s+(\d{1,2}(?::\d{2})?\s*[AP]M)", clean(foot.group(1)), flags=re.I)
            if tm and _clock(tm.group(1)):
                start = f"{day}T{_clock(tm.group(1))}"
            lm = re.search(r'class="location">(.*?)<', foot.group(1), flags=re.S)
            loc = clean(lm.group(1)) if lm else ""
        key = (url.group(1), day)
        if key in seen:
            continue
        seen.add(key)
        cat = re.search(r'class="category left-bordered">(.*?)<', b, flags=re.S)
        out.append({"source_id": "alliancesd", "source_name": "Alliance San Diego", "route": "page",
                    "title": clean(title.group(1)), "start": start, "end": None, "location": loc, "url": url.group(1),
                    "description": "", "categories": [c.strip() for c in clean(cat.group(1)).split(",")] if cat else [],
                    "check_note": "Read automatically from the Alliance San Diego events page; " +
                                  ("end time not given" if "T" in start else "time not given") +
                                  ", and a series may have more dates on its own page",
                    "note": ""})
    return out


STOP = set("the and for with from your you our free event events class classes course courses workshop".split())


def _words(t):
    return {w for w in re.sub(r"[^a-z0-9]+", " ", t.lower()).split() if len(w) >= 5 and w not in STOP}


def drop_hand_entered(auto, manual):
    """Leave out an automatic event when the hand-run pass already has the same one
    (same source, same start, a title word in common), so it is not listed twice."""
    out = []
    for e in auto:
        dup = any(m["source_id"] == e["source_id"] and m["start"][:16] == e["start"][:16]
                  and (_words(m["title"]) & _words(e["title"]) or m["title"] == e["title"])
                  for m in manual)
        if not dup:
            out.append(e)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=31)
    a = ap.parse_args()
    today = dt.date.today()
    end = today + dt.timedelta(days=a.days)
    A, B, AISO, BISO = today.strftime("%Y%m%d"), end.strftime("%Y%m%d"), today.isoformat(), end.isoformat()
    RAW.mkdir(exist_ok=True)
    state_p = ROOT / "state.json"
    state = json.loads(state_p.read_text()) if state_p.exists() else {}
    fails = state.setdefault("consecutive_failures", {})
    result = {}

    def attempt(name, fn):
        try:
            result[name] = {"ok": True, "events": fn()}
            fails[name] = 0
        except Exception as e:  # noqa: BLE001
            fails[name] = fails.get(name, 0) + 1
            result[name] = {"ok": False, "error": str(e)[:200]}
        print(f"{name:14}", result[name])

    def do_sdcl():
        keep = collect_sdcl(AISO, BISO)
        head = ("# County Library RSS via tools/collect.py; fields: guid || title || start || end || branch || address || link "
                f"|| cancelled || virtual || categories || description (collected {AISO})")
        (RAW / "sdcl_rss_extract.txt").write_text(head + "\n" + "".join(l + "\n" for l in keep), encoding="utf-8")
        return len(keep)

    attempt("sdcl", do_sdcl)

    for stem, (label, url) in ICAL_FEEDS.items():
        def do_feed(stem=stem, label=label, url=url):
            text = fetch(url)
            if "BEGIN:VCALENDAR" not in text:
                raise RuntimeError("the address did not return a calendar feed")
            total, lines = ical_to_tsv(text, A, B)
            if any(not l.split("\t")[1] or not l.split("\t")[3] for l in lines):
                raise RuntimeError("events came back without a start time or title")
            head = (f"# Compact copy of {label} via tools/collect.py; columns UID DTSTART DTEND SUMMARY LOCATION ROOM URL "
                    f"CATEGORIES STATUS DESCRIPTION (collected {AISO}; {total} events in feed)")
            (RAW / f"{stem}.tsv").write_text(head + "\n" + "".join(l + "\n" for l in lines), encoding="utf-8")
            return len(lines)
        attempt(stem, do_feed)
        time.sleep(1)

    auto_p = RAW / "auto_events.json"
    old_auto = json.loads(auto_p.read_text(encoding="utf-8")) if auto_p.exists() else []
    new_auto = []
    for sid, url, fn, marker in (("jfs", JFS, jfs_events, "wpem-"), ("alliancesd", ALLIANCE, alliance_events, "post-card")):
        def do_page(sid=sid, url=url, fn=fn, marker=marker):
            page = fetch(url)
            if marker not in page:
                raise RuntimeError("the page layout changed; no event listings found")
            evs = [e for e in fn(page) if AISO <= e["start"][:10] <= BISO]
            new_auto.extend(evs)
            return len(evs)
        attempt(sid, do_page)
        if not result[sid]["ok"]:  # keep what we had for this source
            new_auto.extend(e for e in old_auto if e["source_id"] == sid)
    manual_p = RAW / "page_events.json"
    manual = json.loads(manual_p.read_text(encoding="utf-8")) if manual_p.exists() else []
    new_auto = drop_hand_entered(new_auto, manual)
    new_auto.sort(key=lambda e: (e["start"], e["source_id"], e["title"]))
    auto_p.write_text(json.dumps(new_auto, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    state["last_collect"] = {"date": AISO, "window_end": BISO, "sources": result}
    state_p.write_text(json.dumps(state, indent=1) + "\n")


if __name__ == "__main__":
    main()
