"""Temporary: save one sample of each source type so the readers can be written. Pushed to the 'samples' branch only."""
import os, urllib.request
UA = "Mozilla/5.0 (compatible; sd-immigration-calendar/1.0; +https://www.libraryfresh.com/sd-immigration-calendar/)"
S = {
 "sdcl_p1.xml": ("https://gateway.bibliocommons.com/v2/libraries/sdcl/rss/events?types=60d3d4f817df9637003ba141%2C60d3d686618cfb3000ddb6c4%2C60d3d5c99880a342007cde20&page=1", {"Origin": "https://sdcl.bibliocommons.com", "Referer": "https://sdcl.bibliocommons.com/"}),
 "sdcl_p1_noorigin.xml": ("https://gateway.bibliocommons.com/v2/libraries/sdcl/rss/events?types=60d3d4f817df9637003ba141%2C60d3d686618cfb3000ddb6c4%2C60d3d5c99880a342007cde20&page=1", {}),
 "sdcl_p9.xml": ("https://gateway.bibliocommons.com/v2/libraries/sdcl/rss/events?types=60d3d4f817df9637003ba141%2C60d3d686618cfb3000ddb6c4%2C60d3d5c99880a342007cde20&page=9", {}),
 "jfs.html": ("https://www.jfssd.org/calendar/", {}),
 "alliance.html": ("https://www.alliancesd.org/events/", {}),
 "alliance_event.html": ("https://www.alliancesd.org/event/we-the-people-claim-our-collective-power/", {}),
 "escondido.ics": ("https://escondido.librarycalendar.com/events/feed/ical?age_groups%5B4%5D=4&program_types%5B90%5D=90&program_types%5B160%5D=160&program_types%5B91%5D=91&program_types%5B102%5D=102&program_types%5B103%5D=103", {}),
 "casafamiliar.ics": ("https://www.casafamiliar.org/events/list/?ical=1", {}),
 "maac.ics": ("https://maacproject.org/events/list/?ical=1", {}),
}
os.makedirs("samples", exist_ok=True)
for name, (url, h) in S.items():
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, **h}), timeout=40) as r:
            data = r.read()
    except Exception as e:
        data = f"ERROR {e}".encode()
    open(os.path.join("samples", name), "wb").write(data)
    print(name, len(data))
