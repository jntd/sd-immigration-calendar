# Relevance criteria - SD immigration events calendar

This is the policy every evaluation follows: keyword rules, AI judgment and your review.
Change it here and the next run picks it up. Last set by JTD: 2026-10-16 (tightened again after the second review: general services, housing and civic events moved to Possibly).

## Who the calendar is for

Immigrants, refugees, asylum seekers and the people who help them in San Diego County.

## Labels (only these three)

| Label | Meaning | Goes on the calendar? |
|---|---|---|
| `relevant` | Serves immigrants or refugees directly, or is a core newcomer service | Yes |
| `possibly` | Could fit, but isn't a newcomer service | Yes, after review, with the category `Possibly relevant` so calendar users can filter it out. Unreviewed AI "possibly" labels are held back. |
| `not` | Off topic, a duplicate, cancelled, or a fundraiser | No |

Every label comes with a one-line reason and the step that decided it: `memory`, `rule`, `ai` or `human`.

## What counts

**Relevant**

- Citizenship and naturalization classes, study tables and tutoring.
- Immigration legal help: clinics, consultations, DACA, TPS, asylum, and immigration policy updates.
- Know-your-rights sessions (the "know your rights" kind aimed at immigrants and communities facing enforcement).
- English learning: ESL, English practice and conversation groups, and literacy for adult learners. Tag these `ESL` so calendar users can filter them out.
- Resource and information tables aimed at immigrants and refugees, such as the County Office of Immigrant and Refugee Affairs, and free legal help tables such as the San Diego Law Library. Tag these `Tabling`.
- Workshops and services an agency runs specifically for newcomers, such as immigration or citizenship help, or classes aimed at immigrant families.

**Possibly** (the AI uses this when unsure)

- Housing rights and access: tenants' rights, fair housing, affordable-housing applications.
- Voter information and civic engagement trainings, even from immigrant-serving agencies.
- Legal information sessions on general topics, such as family law.
- General money, credit, benefits or student-loan workshops and fairs, even from an immigrant-serving agency.
- Rights or civic events aimed at a specific community but not at immigration (e.g. CAIR's conference on anti-Muslim hate).
- Cultural celebrations hosted by an immigrant-serving agency, such as Rhythms of East Africa or Casa Familiar's Día de los Muertos.
- Volunteer actions for migrants, such as Border Angels caravans and water drops.
- General events listed in another language, or aimed at a specific newcomer community, whose purpose is unclear.

**Not relevant**

- General library programming: storytime, crafts, games, film series, book clubs, fitness, and hobby groups.
- Learning Spanish or another language (as opposed to English).
- Cultural celebrations not hosted by an immigrant-serving agency.
- Fundraisers, galas, brunches and ticketed benefit dinners, even when the host is a service agency.
- Business, marketing, wellness, tech and professional conferences on Eventbrite, unless aimed at immigrants.
- Local civic and planning meetings and trainings that aren't aimed at immigrants (neighborhood planning workshops, Documenters training, ballot-measure coffee chats). Voter information is Possibly; know-your-rights events stay relevant.
- Food distributions, safety classes and other general community services, even from an immigrant-serving agency.
- Resource and information tables for general services that aren't aimed at immigrants and refugees: community health clinics, CSA, child support, CalWORKs, notary service, job help drop-ins such as Job Lab, preparedness displays (JTD, 2026-11-10). Tag these `Tabling`. A few tables JTD already marked Possibly (La Maestra, EDD Job Help, the CSA Fair Housing table) keep those decisions.
- Health-awareness tables and talks (dementia, air quality, mobile screening).
- Senior care programs (such as SD PACE) and veterans' services (such as OMVA).
- Homeowner topics, such as homeowner rights clinics.
- Day-laborer outreach and other volunteer events that aren't a service newcomers attend.
- Duplicates (`X-SD-DUPLICATE-OF`) and cancelled events.

## Tags

These are separate from the label. An event can have several.

`Citizenship` · `Immigration legal` · `Rights & civic` · `ESL` · `Tabling` · `Jobs & money` · `Housing` · `Health` · `Family & youth` · `Community & culture` · `Volunteer` · `Online` · `Spanish` · `Other language`

## How later runs learn

- **Your decisions are the training.** Every label you confirm or change on the review page is saved to `examples.jsonl`.
- **Memory step.** When the same source lists the same title again, your earlier decision is reused (`memory`), so weekly classes are decided once.
- **AI examples.** The AI judge is shown your past decisions as examples.
- **Updating the rules.** If you keep overriding the same kind of event, turn the pattern into a rule in `rules.json` or a line in this file.
