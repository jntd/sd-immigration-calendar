#!/usr/bin/env python3
"""Split relevant.ics into the public calendar feeds that Teamup subscribes to.

Each event goes to ONE sub-calendar, chosen in this order:
  5 possibly          label 'possibly' (so the whole layer can be switched off)
  1 citizenship-legal tags Citizenship or Immigration legal
  2 rights-civic      tags Rights & civic or Housing
  3 esl               tag ESL
  4 tabling           tag Tabling
  5 possibly          anything left (relevant but none of the above)

All-day listings spanning more than two weeks are left out.
Public feeds drop our internal X-SD-* working labels; CATEGORIES (the tags) stay.
Output: feeds/<name>.ics plus feeds/all.ics, ready to upload to the GitHub Pages site.
"""
import datetime as dt
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "feeds"

FEEDS = [  # file name, calendar name shown in subscribing apps
    ("citizenship-legal", "SD Immigration - Citizenship & legal help"),
    ("rights-civic", "SD Immigration - Know your rights & civic"),
    ("esl", "SD Immigration - English classes (ESL)"),
    ("tabling", "SD Immigration - Resource tables"),
    ("possibly", "SD Immigration - More events (possibly relevant)"),
]


def unfold(s):
    return re.sub(r"\r\n[ \t]", "", s)


def pick(block):
    u = unfold(block)
    label = (re.search(r"^X-SD-LABEL:(\w+)", u, flags=re.M) or [None, ""])[1].lower()
    tags = set()
    m = re.search(r"^CATEGORIES[^:]*:(.*)$", u, flags=re.M)
    if m:
        tags = {t.replace("\\,", ",").strip() for t in re.split(r"(?<!\\),", m.group(1))}
    if label == "possibly":
        return "possibly"
    if tags & {"Citizenship", "Immigration legal"}:
        return "citizenship-legal"
    if tags & {"Rights & civic", "Housing"}:
        return "rights-civic"
    if "ESL" in tags:
        return "esl"
    if "Tabling" in tags:
        return "tabling"
    return "possibly"


def fold(line):
    out, cur = [], b""
    for ch in line:
        e = ch.encode("utf-8")
        if len(cur) + len(e) > (75 if not out else 74):
            out.append(cur.decode("utf-8"))
            cur = b""
        cur += e
    out.append(cur.decode("utf-8"))
    return "\r\n ".join(out)


def esc(s):
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


_NOW = dt.datetime.now(dt.timezone.utc)
STAMP = "\r\n".join([
    "DTSTAMP:" + _NOW.strftime("%Y%m%dT%H%M%SZ"),
    "LAST-MODIFIED:" + _NOW.strftime("%Y%m%dT%H%M%SZ"),
    "SEQUENCE:" + str(int((_NOW - dt.datetime(2026, 10, 1, tzinfo=dt.timezone.utc)).total_seconds() // 3600)),
])


def public(block):
    """Make the public version of an event: every event gets a DESCRIPTION ending with its
    link and the organization that listed it (calendar apps such as Teamup show the
    description but not always the URL property), and our X-SD-* working labels are removed.
    The URL property itself is then dropped: Teamup shows it as a second copy of the link
    under the description (JTD, 2026-10-18), and the description already carries it."""
    u = unfold(block)
    url = (re.search(r"^URL[^:]*:(.*)$", u, flags=re.M) or [None, ""])[1].strip()
    src = (re.search(r"^X-SD-SOURCE-NAME:(.*)$", u, flags=re.M) or [None, ""])[1].strip()
    src = src.replace("\\,", ",").replace("\\;", ";")
    tail = []
    if url:
        tail.append("More info: " + url)
    if src:
        tail.append("Listed by: " + src)
    m = re.search(r"\r\nDESCRIPTION[^:]*:(.*?)(?=\r\n[^ \t])", block, flags=re.S)
    if m:
        old = unfold("x" + m.group(0))[1:].split(":", 1)[1]
        if url and url in old:
            tail = tail[1:]
        new = "\r\n" + fold("DESCRIPTION:" + old + (esc("\n\n" + "\n".join(tail)) if tail else ""))
        block = block.replace(m.group(0), new)
    elif tail:
        block = block.replace("\r\nSUMMARY", "\r\n" + fold("DESCRIPTION:" + esc("\n".join(tail))) + "\r\nSUMMARY", 1) \
            if "\r\nSUMMARY" in block else block.replace("\r\nEND:VEVENT", "\r\n" + fold("DESCRIPTION:" + esc("\n".join(tail))) + "\r\nEND:VEVENT")
    block = re.sub(r"\r\nURL[;:][^\r]*(\r\n[ \t][^\r]*)*", "", block)
    # Change markers, stamped at build time. Subscribers such as Teamup can keep their old copy
    # of an event whose DTSTAMP never changes (2026-10-21: Teamup still showed the removed URL),
    # so every build gets a fresh DTSTAMP and LAST-MODIFIED and a SEQUENCE that only goes up.
    block = re.sub(r"\r\n(DTSTAMP|LAST-MODIFIED|SEQUENCE)[;:][^\r]*", "", block)
    block = block.replace("\r\nDTSTART", "\r\n" + STAMP + "\r\nDTSTART", 1)
    return re.sub(r"\r\nX-SD-[^\r]*(\r\n[ \t][^\r]*)*", "", block)


def main():
    raw = (ROOT / "relevant.ics").read_text(encoding="utf-8", newline="")
    head = raw.split("BEGIN:VEVENT", 1)[0]
    head = re.sub(r"\r\nX-SD-[^\r]*", "", head)
    blocks = ["BEGIN:VEVENT" + b.split("END:VEVENT")[0] + "END:VEVENT" for b in raw.split("BEGIN:VEVENT")[1:]]
    OUT.mkdir(exist_ok=True)
    keep = []
    for b in blocks:  # an all-day listing spanning weeks (e.g. "ongoing" library programs) would paint a bar across the calendar
        u = unfold(b)
        s_, e_ = re.search(r"^DTSTART;VALUE=DATE:(\d{8})", u, flags=re.M), re.search(r"^DTEND;VALUE=DATE:(\d{8})", u, flags=re.M)
        if s_ and e_ and (dt.datetime.strptime(e_.group(1), "%Y%m%d") - dt.datetime.strptime(s_.group(1), "%Y%m%d")).days > 14:
            print("  left out (spans weeks):", re.search(r"^SUMMARY:(.*)$", u, flags=re.M).group(1))
            continue
        keep.append(b)
    blocks = keep
    groups = {k: [] for k, _ in FEEDS}
    for b in blocks:
        groups[pick(b)].append(public(b))
    for key, name in FEEDS + [("all", "SD Immigration & Refugee Events")]:
        evs = blocks and ([public(b) for b in blocks] if key == "all" else groups[key])
        h = re.sub(r"X-WR-CALNAME:[^\r]*", "X-WR-CALNAME:" + name, head)
        (OUT / f"{key}.ics").write_text(h + "\r\n".join(evs) + "\r\nEND:VCALENDAR\r\n", encoding="utf-8", newline="")
        print(f"  {key + '.ics':24} {len(evs):4} events")


if __name__ == "__main__":
    main()
