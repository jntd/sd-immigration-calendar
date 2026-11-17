"""One-off test: can GitHub's servers fetch each calendar source? Writes automation/source_test_results.md"""
import datetime, re, urllib.request, urllib.error

UA = "Mozilla/5.0 (compatible; sd-immigration-calendar/1.0; +https://www.libraryfresh.com/sd-immigration-calendar/)"
VE = r"BEGIN:VEVENT"
SOURCES = [  # name, url, pattern that shows real content, extra headers
 ("County Library (RSS)", "https://gateway.bibliocommons.com/v2/libraries/sdcl/rss/events?types=60d3d4f817df9637003ba141%2C60d3d686618cfb3000ddb6c4%2C60d3d5c99880a342007cde20&page=1", r"<item>", {"Origin": "https://sdcl.bibliocommons.com", "Referer": "https://sdcl.bibliocommons.com/"}),
 ("Oceanside (iCal)", "https://oceansidepl.librarycalendar.com/events/feed/ical?age_groups%5B25%5D=25&age_groups%5B98%5D=98&program_types%5B165%5D=165&program_types%5B112%5D=112&program_types%5B163%5D=163", VE, {}),
 ("Escondido (iCal)", "https://escondido.librarycalendar.com/events/feed/ical?age_groups%5B4%5D=4&program_types%5B90%5D=90&program_types%5B160%5D=160&program_types%5B91%5D=91&program_types%5B102%5D=102&program_types%5B103%5D=103", VE, {}),
 ("Coronado (iCal)", "https://coronado.librarycalendar.com/events/feed/ical?age_groups%5B30%5D=30&age_groups%5B101%5D=101", VE, {}),
 ("Chula Vista (calendar page)", "https://www.chulavistaca.gov/departments/library/library-calendar/-selcat-129", r"Calendar/Event/\d+", {}),
 ("Carlsbad (calendar page)", "https://library.carlsbadca.gov/programs/events-calendar/-selcat-97", r"Calendar/Event/\d+", {}),
 ("National City (calendar page)", "https://www.nationalcityca.gov/government/library/library-calendar", r"Calendar/Event/\d+", {}),
 ("Legal Aid Society (iCal)", "https://www.lassd.org/events/list/?ical=1", VE, {}),
 ("SDVLP (iCal)", "https://sdvlp.org/events/list/?ical=1", VE, {}),
 ("MAAC (iCal)", "https://maacproject.org/events/list/?ical=1", r"BEGIN:VCALENDAR", {}),
 ("Casa Familiar (iCal)", "https://www.casafamiliar.org/events/list/?ical=1", VE, {}),
 ("Eventbrite (search page)", "https://www.eventbrite.com/d/ca--san-diego/immigration/", r"/e/[^\"']*-\d{9,}", {}),
 ("JFS (calendar page)", "https://www.jfssd.org/calendar/", r"Citizenship|UPCOMING EVENTS", {}),
 ("Alliance San Diego (events page)", "https://www.alliancesd.org/events/", r"alliancesd\.org/event/", {}),
]

def get(url, headers):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*", **headers})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:3000]
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"

rows = []
for name, url, pat, hdr in SOURCES:
    status, body = get(url, hdr)
    hits = len(re.findall(pat, body)) if status == 200 else 0
    note = ""
    # Granicus sites: also try one per-event iCal download
    m = re.search(r"Calendar/Event/(\d+)", body) if status == 200 and "Calendar/Event" in pat else None
    if m:
        base = re.match(r"https://[^/]+", url).group(0)
        s2, b2 = get(f"{base}/Home/Components/Calendar/Event/ICalendar?ID={m.group(1)}&IsPublished=True", {})
        note = f"per-event iCal: HTTP {s2}, {'has event' if 'BEGIN:VEVENT' in b2 else 'no event'}"
    if "eventbrite" in url and hits:
        eid = re.search(r"/e/[^\"']*-(\d{9,})", body).group(1)
        s2, b2 = get(f"https://www.eventbrite.com/calendar.ics?eid={eid}&calendar=ical", {})
        note = f"per-event .ics: HTTP {s2}, {'has event' if 'BEGIN:VEVENT' in b2 else 'no event'}"
    if status != 200 or not hits:
        note = (note + " " + re.sub(r"\s+", " ", body[:160])).strip().replace("|", "/")
    verdict = "OK" if status == 200 and hits else "FAILED"
    rows.append(f"| {name} | {verdict} | {status} | {len(body)} | {hits} | {note} |")

out = ["# Source test from GitHub's servers", "", f"Run: {datetime.datetime.utcnow():%Y-%m-%d %H:%M} UTC", "",
       "| Source | Result | HTTP | Bytes | Matches | Note |", "|---|---|---|---|---|---|", *rows, ""]
open("automation/source_test_results.md", "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out))
