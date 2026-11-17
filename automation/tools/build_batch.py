#!/usr/bin/env python3
"""Build batch.ics: every collected event, in one iCalendar file, ready for evaluation.

Routes (how an event reached the batch):
  ical    - native iCalendar from the source; VEVENT text kept as-is, only X-SD-* labels added
  rss     - County Library RSS extract (raw/sdcl_rss_extract.txt), written as VEVENTs (one conversion)
  page    - events read from a web page, supplied as JSON (raw/page_events.json), written as VEVENTs
  social  - events read from social posts, same JSON format, flagged X-SD-NEEDS-CHECK

Usage: python3 build_batch.py [--start YYYY-MM-DD] [--days 30]
Reads ../raw, writes ../batch.ics and prints a per-source report.
"""
import argparse, datetime as dt, hashlib, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RAW = ROOT / "raw"
TZ = "America/Los_Angeles"

VTIMEZONE = """BEGIN:VTIMEZONE
TZID:America/Los_Angeles
BEGIN:DAYLIGHT
TZOFFSETFROM:-0800
TZOFFSETTO:-0700
TZNAME:PDT
DTSTART:19700308T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:-0700
TZOFFSETTO:-0800
TZNAME:PST
DTSTART:19701101T020000
RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU
END:STANDARD
END:VTIMEZONE"""

# Native iCal files in raw/: file name -> (source id, source name)
ICAL_SOURCES = {
    "lassd.ics": ("lassd", "Legal Aid Society of San Diego"),
    "sdvlp.ics": ("sdvlp", "San Diego Volunteer Lawyer Program"),
    "maac.ics": ("maac", "MAAC Project"),
    "casafamiliar.ics": ("casafamiliar", "Casa Familiar"),
    "oceanside.ics": ("oceanside-pl", "Oceanside Public Library"),
    "escondido.ics": ("escondido-pl", "Escondido Public Library"),
    "coronado.ics": ("coronado-pl", "Coronado Public Library"),
    "oira-livewell.ics": ("oira", "County Office of Immigrant and Refugee Affairs"),
    "chulavista.ics": ("chulavista-pl", "Chula Vista Public Library"),
    "carlsbad.ics": ("carlsbad-pl", "Carlsbad City Library"),
    "nationalcity.ics": ("nationalcity-pl", "National City Public Library"),
    "majdal.ics": ("majdal", "Majdal Arab Community Center"),
    "eventbrite.ics": ("eventbrite", "Eventbrite"),
    "sdpl.ics": ("sandiego-pl", "San Diego Public Library"),  # raw/sdpl.tsv from tools/sdpl_brochure.py
}


def esc(s):
    return (s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fold(line):
    out, b = [], line.encode("utf-8")
    while len(b) > 75:
        cut = 75 if not out else 74
        while cut > 0 and (b[cut] & 0xC0) == 0x80:
            cut -= 1
        out.append(b[:cut].decode("utf-8"))
        b = b[cut:]
    out.append(b.decode("utf-8"))
    return "\r\n ".join(out)


def unfold(text):
    return re.sub(r"\r?\n[ \t]", "", text)


def vevents(text):
    return re.findall(r"BEGIN:VEVENT\r?\n.*?END:VEVENT", unfold(text), flags=re.S)


def prop(block, name):
    m = re.search(rf"^{name}([;:][^\r\n]*)$", block, flags=re.M)
    if not m:
        return None, None
    head, _, val = m.group(1).partition(":") if not m.group(1).startswith(":") else ("", ":", m.group(1)[1:])
    return head, val


def parse_dt(head, val):
    """Return (local naive datetime or date, is_date)."""
    if val is None:
        return None, False
    val = val.strip()
    if "VALUE=DATE" in (head or "") or re.fullmatch(r"\d{8}", val):
        return dt.datetime.strptime(val[:8], "%Y%m%d"), True
    d = dt.datetime.strptime(val[:15], "%Y%m%dT%H%M%S")
    if val.endswith("Z"):  # UTC -> Pacific (approximate DST rule, good for 2026-2028)
        d = d + dt.timedelta(hours=-7 if is_pdt(d) else -8)
    return d, False


def is_pdt(d):
    y = d.year
    mar = dt.datetime(y, 3, 8) + dt.timedelta(days=(6 - dt.datetime(y, 3, 8).weekday()) % 7)
    nov = dt.datetime(y, 11, 1) + dt.timedelta(days=(6 - dt.datetime(y, 11, 1).weekday()) % 7)
    return mar.replace(hour=10) <= d < nov.replace(hour=9)


def labels(src_id, src_name, route, collected, extra=None):
    lines = [f"X-SD-SOURCE:{src_id}", fold(f"X-SD-SOURCE-NAME:{esc(src_name)}"), f"X-SD-ROUTE:{route}",
             f"X-SD-COLLECTED:{collected}", "X-SD-STATUS:UNREVIEWED"]
    for k, v in (extra or {}).items():
        lines.append(fold(f"{k}:{esc(v)}"))
    return lines


def make_uid(*parts):
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:20] + "@sd-immigration-calendar"


def build_vevent(uid, summary, start, end, location, url, description, categories, src_id, src_name, route,
                 collected, cancelled=False, all_day=False, extra=None):
    L = ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{collected.replace('-', '')}T000000Z"]
    if all_day:
        L += [f"DTSTART;VALUE=DATE:{start:%Y%m%d}"]
        if end:
            L += [f"DTEND;VALUE=DATE:{end:%Y%m%d}"]
    else:
        L += [f"DTSTART;TZID={TZ}:{start:%Y%m%dT%H%M%S}"]
        if end:
            L += [f"DTEND;TZID={TZ}:{end:%Y%m%dT%H%M%S}"]
    L.append(fold(f"SUMMARY:{esc(summary)}"))
    if location:
        L.append(fold(f"LOCATION:{esc(location)}"))
    if description:
        L.append(fold(f"DESCRIPTION:{esc(description)}"))
    if url:
        L.append(fold(f"URL:{url}"))
    if categories:
        L.append(fold("CATEGORIES:" + ",".join(esc(c) for c in categories)))
    if cancelled:
        L.append("STATUS:CANCELLED")
    L += labels(src_id, src_name, route, collected, extra)
    L.append("END:VEVENT")
    return "\r\n".join(L), start, end


def in_window(start, end, w0, w1):
    end = end or start
    return start < w1 and end >= w0


def from_ical(path, src_id, src_name, collected, w0, w1, report):
    out = []
    for b in vevents(path.read_text(encoding="utf-8")):
        h, v = prop(b, "DTSTART")
        start, all_day = parse_dt(h, v)
        eh, ev = prop(b, "DTEND")
        end, _ = parse_dt(eh, ev)
        report["read"] += 1
        if not start or not in_window(start, end, w0, w1):
            continue
        lines = b.split("\n")
        lines = [l.rstrip("\r") for l in lines]
        # Granicus files have no time zone or UID: add them so the event is unambiguous and trackable.
        if h is not None and "TZID" not in h and not (v or "").endswith("Z") and not all_day:
            lines = [re.sub(r"^(DTSTART|DTEND)(;[^:]*)?:", rf"\1;TZID={TZ}:", l) for l in lines]
        if prop(b, "UID")[1] is None:
            _, s = prop(b, "SUMMARY")
            lines.insert(1, f"UID:{make_uid(src_id, s or '', v or '')}")
        body = [fold(l) if len(l.encode()) > 75 else l for l in lines[:-1]]
        body += labels(src_id, src_name, "ical", collected)
        body.append("END:VEVENT")
        out.append(("\r\n".join(body), start, end))
    return out


TSV_COLS = ["UID", "DTSTART", "DTEND", "SUMMARY", "LOCATION", "ROOM", "URL", "CATEGORIES", "STATUS", "DESCRIPTION"]


def from_ical_tsv(path, src_id, src_name, collected, w0, w1, report):
    """Compact copy of a native iCal feed: one line per VEVENT, each column holds a property's
    parameters and value exactly as published (e.g. ';TZID=America/Los_Angeles:20261014T100000')."""
    lines = []
    for row in path.read_text(encoding="utf-8").splitlines():
        if not row.strip() or row.startswith("#"):
            continue
        cols = (row.split("\t") + [""] * 10)[:10]
        b = ["BEGIN:VEVENT"]
        for name, val in zip(TSV_COLS, cols):
            if val and val not in (":",):
                b.append(f"{name}{val}")
        if not any(l.startswith("DTSTAMP") for l in b):
            b.append(f"DTSTAMP:{collected.replace('-', '')}T000000Z")
        b.append("END:VEVENT")
        lines.append("\n".join(b))
    tmp = "\n".join(lines)
    fake = path.with_suffix(".tmp.ics")
    fake.write_text(tmp, encoding="utf-8")
    try:
        out = from_ical(fake, src_id, src_name, collected, w0, w1, report)
    finally:
        fake.unlink()
    def note(t):
        if "\r\nDESCRIPTION" in t:
            return t
        return t.replace("X-SD-STATUS:UNREVIEWED", "X-SD-STATUS:UNREVIEWED\r\n" + fold("X-SD-NOTE:Core properties copied from the source's iCal feed\\; description not included"))
    return [(note(t), s, e) for t, s, e in out]


def from_rss_extract(path, collected, w0, w1, report):
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        f = [x.strip() for x in line.split("||")]
        guid, title, s, e, branch, addr, link, canc, virt, cats = f[:10]
        desc = f[10] if len(f) > 10 else None  # optional 11th field: plain-text description
        report["read"] += 1
        all_day = "T" not in s
        start = dt.datetime.fromisoformat(s)
        end = dt.datetime.fromisoformat(e) if e else None
        if not in_window(start, end, w0, w1):
            continue
        loc = f"{branch} Branch Library, {addr.rsplit(',', 1)[0]}, CA {addr.rsplit(',', 1)[-1].strip()}"
        extra = {"X-SD-NOTE": "Ongoing listing that spans many weeks"} if all_day and end and (end - start).days > 7 else None
        out.append(build_vevent(f"{guid}@sdcl.bibliocommons.com", title, start, end, loc, link, desc or None,
                                [c for c in cats.split(";") if c], "sdcl", "San Diego County Library", "rss",
                                collected, cancelled=(canc == "true"), all_day=all_day, extra=extra))
    return out


def from_json(path, collected, w0, w1, report):
    """raw/page_events.json: list of {source_id, source_name, route: page|social, title, start, end,
    location, url, description, categories, post_url, check_note, note}.
    start/end are local ISO date-times ("2026-10-15T12:00"), or dates ("2026-10-16") for all-day or time-unknown events."""
    out = []
    for ev in json.loads(path.read_text(encoding="utf-8")):
        r = report.setdefault(ev["source_id"], {"read": 0, "kept": 0})
        r["read"] += 1
        all_day = len(ev["start"]) == 10
        start = dt.datetime.fromisoformat(ev["start"])
        end = dt.datetime.fromisoformat(ev["end"]) if ev.get("end") else None
        if all_day and end is None:
            end = start + dt.timedelta(days=1)
        if not in_window(start, end, w0, w1):
            continue
        extra = {}
        if ev["route"] == "social" or ev.get("check_note"):
            extra["X-SD-NEEDS-CHECK"] = ev.get("check_note", "Written from a social media post")
        if ev.get("post_url"):
            extra["X-SD-POST"] = ev["post_url"]
        if ev.get("note"):
            extra["X-SD-NOTE"] = ev["note"]
        uid = make_uid(ev["source_id"], ev["title"], ev["start"])
        out.append(build_vevent(uid, ev["title"], start, end, ev.get("location"), ev.get("url"),
                                ev.get("description"), ev.get("categories"), ev["source_id"], ev["source_name"],
                                ev["route"], collected, all_day=all_day, extra=extra))
        r["kept"] = r.get("kept", 0) + 1
    return out


# Words too common to show two listings are the same event.
STOP = set("""the and for with from your you our free event events class classes course courses workshop library
online virtual session program community join day night los las del de la el en para con y a an of in on at to""".split())


def sig_words(title):
    return {w for w in norm(title).split() if len(w) >= 5 and w not in STOP}


LOC_STOP = set("san diego california united states avenue street boulevard county center library online virtual".split())


def loc_words(loc):
    return {w for w in norm(loc).split() if len(w) >= 4 and w not in LOC_STOP}


ROUTE_RANK = {"ical": 0, "rss": 1, "page": 2, "social": 3}


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=dt.date.today().isoformat())
    ap.add_argument("--days", type=int, default=30)
    a = ap.parse_args()
    w0 = dt.datetime.fromisoformat(a.start)
    w1 = w0 + dt.timedelta(days=a.days + 1)
    collected = dt.date.today().isoformat()

    events, report = [], {}
    for fname, (sid, sname) in ICAL_SOURCES.items():
        pair = [(p, fn) for p, fn in ((RAW / fname, from_ical), (RAW / fname.replace(".ics", ".tsv"), from_ical_tsv)) if p.exists()]
        if len(pair) == 2:  # a source collected both ways over time: use only the newer file
            pair = [max(pair, key=lambda x: x[0].stat().st_mtime)]
        for p, fn in pair:
            if True:
                report.setdefault(sid, {"read": 0, "kept": 0})
                got = fn(p, sid, sname, collected, w0, w1, report[sid])
                report[sid]["kept"] += len(got)
                events += got
    if (RAW / "sdcl_rss_extract.txt").exists():
        report["sdcl"] = {"read": 0}
        got = from_rss_extract(RAW / "sdcl_rss_extract.txt", collected, w0, w1, report["sdcl"])
        report["sdcl"]["kept"] = len(got)
        events += got
    # page_events.json: entered by hand in the monthly pass. auto_events.json: written by tools/collect.py.
    for name in ("page_events.json", "auto_events.json"):
        if (RAW / name).exists():
            events += from_json(RAW / name, collected, w0, w1, report)

    # Duplicates. Exact: same normalized title and start time. Likely: same start time, a different
    # source, and both the titles and the locations share a distinctive word (e.g. JFS "Free Citizenship Course (El Cajon)" and
    # County Library "Citizenship Course"). The native-iCal / library listing is kept as the original.
    def route_of(text):
        m = re.search(r"^X-SD-ROUTE:(\w+)", text, flags=re.M)
        return ROUTE_RANK.get(m.group(1) if m else "", 9)

    events.sort(key=lambda e: (e[1], route_of(e[0])))
    seen, final, n_exact, n_likely = [], [], 0, 0
    for text, start, end in events:
        u = unfold(text)
        title = re.search(r"^SUMMARY:(.*)$", u, flags=re.M).group(1)
        src = re.search(r"^X-SD-SOURCE:(.*)$", u, flags=re.M).group(1).strip()
        uid = re.search(r"^UID:(.*)$", u, flags=re.M).group(1).strip()
        lm = re.search(r"^LOCATION[^:]*:(.*)$", u, flags=re.M)
        loc = lm.group(1).replace("\\,", ",") if lm else ""
        match = None
        for s_start, s_title, s_src, s_uid, s_loc in seen:
            if s_start != start:
                continue
            if norm(s_title) == norm(title):
                match, kind = s_uid, "exact"
                break
            if s_src != src and sig_words(s_title) & sig_words(title) and loc_words(s_loc) & loc_words(loc):
                match, kind = s_uid, "likely"
        if match:
            add = f"X-SD-DUPLICATE-OF:{match}"
            if kind == "likely":
                add += "\r\n" + fold("X-SD-NOTE:Likely duplicate: same start time, title word and place as the listing named in X-SD-DUPLICATE-OF")
                n_likely += 1
            else:
                n_exact += 1
            text = text.replace("END:VEVENT", add + "\r\nEND:VEVENT")
        else:
            seen.append((start, title, src, uid, loc))
        final.append(text)

    cal = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//SD Immigration Calendar//batch//EN", "CALSCALE:GREGORIAN",
           "X-WR-CALNAME:SD immigration events - batch (unreviewed)", f"X-WR-TIMEZONE:{TZ}",
           f"X-SD-WINDOW:{w0:%Y-%m-%d}/{(w1 - dt.timedelta(days=1)):%Y-%m-%d}", VTIMEZONE.replace("\n", "\r\n")]
    cal += final + ["END:VCALENDAR"]
    (ROOT / "batch.ics").write_text("\r\n".join(cal) + "\r\n", encoding="utf-8")

    print(f"Window {w0:%Y-%m-%d} to {(w1 - dt.timedelta(days=1)):%Y-%m-%d}; {len(final)} events written to batch.ics")
    print(f"  duplicates marked: {n_exact} exact, {n_likely} likely")
    for sid, r in report.items():
        print(f"  {sid:16} read {r['read']:4}  kept {r.get('kept', '-')}")


if __name__ == "__main__":
    main()
