#!/usr/bin/env python3
"""Turn a San Diego Public Library "My Events Brochure" PDF into raw/sdpl.tsv.

The brochure comes from https://sandiego.events.mylibrary.digital (print / brochure button).
It holds up to 500 events in a 3-column grid, read column by column, top to bottom.
Each card: optional teal date bar, title, library, time, description, category line.

Usage:  python3 -I tools/sdpl_brochure.py <brochure.pdf> [raw/sdpl.tsv]

Output is the compact 10-column TSV that build_batch.py reads. Times are local (build_batch adds
the Pacific time zone). The UID is made from title + start + branch, so it stays the same from run
to run and JTD's review decisions carry over. The brochure has no event links, so every event
gets the calendar's home page as its URL.
"""
import hashlib
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import pdfplumber

DEFAULT_URL = "https://sandiego.events.mylibrary.digital"
COLS = [(0, 196), (196, 397), (397, 9999)]
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def esc(s):
    return (s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n").replace("\t", " ")


def kind(ch):
    f, size, col = ch["fontname"], round(ch["size"], 1), tuple(round(c, 2) for c in (ch.get("non_stroking_color") or ()))
    bold = "Bold" in f
    if bold and size >= 10 and col == (1.0, 1.0, 1.0):
        return "date"
    if bold and col == (1.0, 1.0, 1.0):
        return "flag"          # e.g. REGISTRATION REQUIRED (white on black)
    if bold and size >= 8.5:
        return "title"
    if bold and size == 7.5:
        return "lib"
    if bold and col == (0.0, 0.0, 0.5):
        return "tags"
    if bold and col == (1.0, 1.0, 1.0):
        return "flag"          # e.g. REGISTRATION REQUIRED (white on black)
    if bold:
        return "time"
    return "desc"


def pick_year(mon, day, dow, near):
    """Brochure range bars have no year; choose the year whose weekday matches, nearest to `near`."""
    best = None
    for y in range(near.year - 2, near.year + 3):
        try:
            d = date(y, mon, day)
        except ValueError:
            continue
        if dow is None or d.weekday() == dow:
            if best is None or abs((d - near).days) < abs((best - near).days):
                best = d
    return best or date(near.year, mon, day)


def parse_date_bar(text, near):
    t = text.replace(",", " ")
    m = re.match(r"(\w{3})\w*\s+(\w{3})\w*\s+(\d{1,2})\s+(\d{4})$", t.strip())
    if m:  # "Fri October 16, 2026"
        return date(int(m.group(4)), MONTHS[m.group(2).lower()], int(m.group(3))), None
    parts = re.findall(r"(\w{3})\w*\s+(\w{3})\w*\s+(\d{1,2})", t)
    if len(parts) == 2:  # "Wed, Aug 12 – Thu, Dec 31"
        (d1, m1, n1), (d2, m2, n2) = parts
        a = pick_year(MONTHS[m1.lower()], int(n1), DAYS.index(d1.lower()), near)
        b = pick_year(MONTHS[m2.lower()], int(n2), DAYS.index(d2.lower()), a)
        if b < a:
            b = pick_year(MONTHS[m2.lower()], int(n2), None, a + timedelta(days=200))
        return a, b
    raise ValueError(f"unreadable date bar: {text!r}")


def hhmm(s):
    m = re.match(r"(\d{1,2}):(\d{2})\s*([AP]M)", s.strip(), re.I)
    h, mi = int(m.group(1)) % 12, int(m.group(2))
    if m.group(3).upper() == "PM":
        h += 12
    return h, mi


def lines_by_column(page):
    page = page.dedupe_chars(tolerance=1)
    words = page.extract_words(extra_attrs=["fontname", "size", "non_stroking_color"], keep_blank_chars=False)
    groups = {}
    for w in words:
        ci = next(i for i, (x0, x1) in enumerate(COLS) if x0 <= w["x0"] < x1)
        k = kind(w)
        key = (ci, round(w["top"]), k)
        # merge with a line of the same kind within 1.5pt in the same column
        for g in list(groups):
            if g[0] == ci and g[2] == k and abs(g[1] - w["top"]) <= 1.5:
                key = g
                break
        groups.setdefault(key, []).append(w)
    out = {0: [], 1: [], 2: []}
    for (ci, top, k), ws in groups.items():
        ws.sort(key=lambda w: w["x0"])
        text = ws[0]["text"]
        for a, b in zip(ws, ws[1:]):
            # a wide gap separates items on a category line ("Focus: Art...     All Ages")
            text += (" | " if b["x0"] - a["x1"] > 8 else " ") + b["text"]
        out[ci].append((top, k, text))
    return out


def parse(pdf_path):
    pdf = pdfplumber.open(pdf_path)
    head = pdf.pages[0].extract_text() or ""
    m = re.search(r"(\d{2})-(\d{2})-(\d{4})\s*-\s*(\d{2})-(\d{2})-(\d{4})", head)
    near = date(int(m.group(3)), int(m.group(1)), int(m.group(2))) if m else date.today()
    rng = (near, date(int(m.group(6)), int(m.group(4)), int(m.group(5)))) if m else None
    cards, cur = [], None
    current_date = (near, None)
    for pi, page in enumerate(pdf.pages):
        cols = lines_by_column(page)
        for ci in range(3):
            for top, k, text in sorted(cols[ci]):
                if pi == 0 and top < 210:
                    continue  # page-1 header block
                if k == "date":
                    current_date = parse_date_bar(text, near)
                    cur = None
                elif k == "title":
                    if cur and cur["stage"] == "title":
                        cur["title"] += " " + text   # title wraps onto a second line
                        continue
                    cur = {"date": current_date, "title": text, "lib": "", "time": "", "desc": [], "tags": [],
                           "flags": [], "stage": "title"}
                    cards.append(cur)
                elif cur is None:
                    continue
                elif k == "lib":
                    cur["lib"] = (cur["lib"] + " " + text).strip()
                    cur["stage"] = "lib"
                elif k == "time" and not cur["time"]:
                    cur["time"] = text
                    cur["stage"] = "time"
                elif k == "tags":
                    cur["tags"].append(text)
                    cur["stage"] = "tags"
                elif k == "flag":
                    cur["flags"].append(text)
                else:
                    cur["desc"].append(text)
                    cur["stage"] = "desc"
    return cards, rng


def to_rows(cards):
    rows = []
    for c in cards:
        d0, d1 = c["date"]
        raw = " | ".join(c["tags"]).replace("•", "|").replace("/", "|")
        tags = []
        for t in raw.split("|"):
            t = re.sub(r"^\d+\s+", "", t.replace("...", "").replace("…", "").strip())
            if len(t) > 2 and t not in tags:
                tags.append(t)
        desc = " ".join(c["desc"]).strip()
        if c["flags"]:
            desc = (desc + " " + " ".join(f.capitalize() + "." for f in c["flags"])).strip()
        lib = c["lib"]
        loc = "Online (San Diego Public Library)" if lib.lower().startswith("virtual") else (lib + ", San Diego" if lib else "San Diego Public Library")
        tm = re.findall(r"\d{1,2}:\d{2}\s*[AP]M", c["time"], re.I)
        if d1 is not None:  # multi-day range: all-day span
            ds = ";VALUE=DATE:" + d0.strftime("%Y%m%d")
            de = ";VALUE=DATE:" + (d1 + timedelta(days=1)).strftime("%Y%m%d")
            if c["time"]:
                desc = f"Daily {c['time']}. " + desc
        elif len(tm) == 2:
            (h0, m0), (h1, m1) = hhmm(tm[0]), hhmm(tm[1])
            ds = ":" + d0.strftime("%Y%m%d") + f"T{h0:02d}{m0:02d}00"
            de = ":" + d0.strftime("%Y%m%d") + f"T{h1:02d}{m1:02d}00"
        else:
            ds = ";VALUE=DATE:" + d0.strftime("%Y%m%d")
            de = ";VALUE=DATE:" + (d0 + timedelta(days=1)).strftime("%Y%m%d")
        # Same title, start and branch = same event from run to run (two branches can share a title and time).
        uid = hashlib.sha1(f"{c['title']}|{ds}|{lib}".encode()).hexdigest()[:20] + "@sandiego.events.mylibrary.digital"
        rows.append([":" + uid, ds, de, ":" + esc(c["title"]), ":" + esc(loc), "", ":" + DEFAULT_URL,
                     ":" + ",".join(esc(t) for t in tags), ":CONFIRMED", ":" + esc(desc)])
    return rows


def main():
    src = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parent.parent / "raw" / "sdpl.tsv"
    cards, rng = parse(src)
    rows = to_rows(cards)
    hdr = (f"# San Diego Public Library from My Events Brochure PDF ({src.name}); brochure range "
           f"{rng[0]} to {rng[1] if rng else '?'}; {len(rows)} events; columns UID DTSTART DTEND SUMMARY LOCATION ROOM URL CATEGORIES STATUS DESCRIPTION")
    out.write_text(hdr + "\n" + "\n".join("\t".join(r) for r in rows) + "\n", encoding="utf-8")
    print(f"{len(rows)} events -> {out}")


if __name__ == "__main__":
    main()
