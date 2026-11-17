# Monthly hand-run pass

These sources refuse automated visits or have no structure, so Claude collects them about once a
month from the browser pane on JTD's computer (snippets in `tools/browser_snippets.js`). Results go
into `raw/` here; pushing them triggers the daily update job.

## Libraries (Granicus sites; block automated visits)

| Source | Page | Raw file |
|---|---|---|
| Carlsbad City Library | `https://library.carlsbadca.gov/programs/events-calendar/-selcat-97` | `raw/carlsbad.tsv` |
| Chula Vista Public Library | `https://www.chulavistaca.gov/departments/library/library-calendar/-selcat-129` | `raw/chulavista.tsv` |
| National City Public Library | `https://www.nationalcityca.gov/government/library/library-calendar` | `raw/nationalcity.tsv` |

These publish months ahead, so collect a 60-day window (month pages, one month per call).

## Agency pages (into `raw/page_events.json`)

CAIR San Diego, License to Freedom, Chicano Federation, Refugee San Diego, Haitian Bridge Alliance,
Majdal Arab Community Center. Addresses are in the `sd-agency-immigration-events` skill.
Also look at USD's Immigration Dialogue events page, `https://www.sandiego.edu/immigration-dialogue/events.php`
(empty on 2026-11-16).

## Instagram (into `raw/page_events.json`, route `social`)

legalaidsd, sdvlp, maac1965, casa.familiar, jfs_sd, alliancesandiego, cairsandiego, license2freedom,
chicanofederation, refugeesandiego, haitianbridge, majdalcenter, borderangelsofficial, ircsandiego,
pathwaystocitizenship, survivors_sandiego, uweast1, casacornelialawcenter, espaciomigrante,
interfaithcs, karenorganizationsd, somalifamilyservice

Added 2026-11-16 (JTD): university undocumented-student offices. **Include only events the post says
are open to the public or the community**; student-only events are left out.

| id | Office | Instagram |
|---|---|---|
| ucsd-uss | UC San Diego Undocumented Student Services | ucsdundoctritons |
| sdsu-murc | SDSU Undocumented Resource Center | sdsumurc |

## Not sources (decided)

- Eventbrite: dropped 2026-11-16 (blocks automated visits; almost nothing relevant).
- UC San Diego "Visitors" events calendar: looked at 2026-11-16; 429 events a year, none relevant.
- San Diego Public Library: no usable feed; left out of the automation.
