# sd-immigration-calendar

Calendar feeds of immigration and refugee services events in San Diego County, kept by JTD
(San Diego Public Library). The `.ics` files in this folder are the public feeds:

| Feed | What it holds |
|---|---|
| `citizenship-legal.ics` | Citizenship classes and immigration legal help |
| `rights-civic.ics` | Know-your-rights and civic events |
| `esl.ics` | English classes |
| `tabling.ics` | Resource tables |
| `possibly.ics` | Other events that may be of interest |
| `all.ics` | Everything above in one feed |

## How it updates

Every morning GitHub runs `.github/workflows/update.yml`, which:

1. collects the sources that allow automated visits (`automation/tools/collect.py`);
2. builds one batch of events and labels each one relevant / possibly / not, using JTD's past
   review decisions, the keyword rules and earlier AI judgments (`automation/evaluation/`);
3. builds the feeds and, if the safety checks pass, publishes them here.

`automation/status.md` shows the result of the last run. New event titles that nothing has
judged yet are held back until the weekly AI pass.

Collected by hand about once a month, because the sites refuse automated visits or have no
structure: Carlsbad, Chula Vista and National City libraries, Instagram, and some agency pages.
Their data sits in `automation/raw/` as last collected.

The relevance policy is in `automation/evaluation/criteria.md`.
