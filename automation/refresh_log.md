# Refresh log

## 2026-10-16
- Window: 2026-10-16 to 2026-11-15
- Collected (events in window): sdcl 99, carlsbad 46, nationalcity 42, coronado 40, oceanside 32, chulavista 10, escondido 2, eventbrite 71, jfs 21, casafamiliar 9, alliancesd 5, chicanofed 4, lassd 4, borderangels 3, maac 2, cair 1, ltf 1, somali 1, sdvlp 1, irc 1, uweast 1 (396 total)
- Carried over (not collected this time): none
- Labels: relevant 146, possibly 13, not 237; decided by rule 290, human 68, ai 37, memory 1
- Going to the calendar (relevant.ics): 156 events
- Problems: computer disconnected once mid-run (resumed); Escondido down to 2 events (4 last time), filters checked, looks like a quiet month
- After JTD's review (60 new decisions, 23 changed): relevant 118, possibly 36, not 242; decided by rule 267, human 128, memory 1
- Feeds built: yes (all 153: citizenship-legal 34, rights-civic 5, esl 76, tabling 2, possibly 36); published: uploaded by JTD (commit 7acd938); live site still showed old files ~5 min later

## 2026-10-17
- Window: 2026-10-17 to 2026-11-16
- Collected (events in window): sdcl 106, carlsbad 44, nationalcity 44, coronado 39, oceanside 34, chulavista 10, escondido 1, sandiego-pl 544 (brochure 2026-10-19 to 2026-10-28, plus 44 Oct 17-18 events carried from the 2026-10-16 brochure), eventbrite 67, jfs 22, casafamiliar 7, alliancesd 5, chicanofed 4, lassd 4, borderangels 3, maac 2, sdvlp 2, ltf 1, somali 1, irc 1, uweast 1 (942 total)
- Carried over (not collected this time): none
- Labels: relevant 129, possibly 40, not 773; decided by rule 511, ai 320, human 108, memory 3
- Going to the calendar (relevant.ics): 169 events
- Problems: Eventbrite .ics and Carlsbad/Chula Vista/National City descriptions stopped escaping commas (source change; lines kept as published); Escondido down to 1 event; Somali Family Service computer class and Paint & Sip details only in flyer images (not added)
- Review: 1 decision added since last ingest (Alliance SD "We the People" English training -> not)
- After JTD's review (218 new decisions, 3 changed: Nuestra Cultura Exhibition -> possibly; Medicare Health Plan table and Ready California tour -> not): relevant 129, possibly 36, not 777; decided by human 433, rule 506, memory 3
- Feeds built: yes (all 163: citizenship-legal 36, rights-civic 5, esl 85, tabling 2, possibly 35); published: pushed by Claude (commit 127a969), live possibly.ics checked (35)
- Printout: print/handout_2026-10-19.pdf (26 entries, 2 pages; SDPL only through Oct 28)
- Review page: rows now fixed height so the label switch stays in line (JTD request)

## 2026-10-21
- Window: 2026-10-21 to 2026-11-20
- Collected (events in window): sdcl 123, carlsbad 49, coronado 45, nationalcity 43, oceanside 34, chulavista 8, escondido 2, sandiego-pl 562 (brochure 2026-10-22 to 2026-11-03, plus 62 Oct 21 events carried from the 2026-10-17 brochure), eventbrite 67, jfs 24, alliancesd 9, casafamiliar 7, chicanofed 4, lassd 4, borderangels 2, maac 1, sdvlp 2, kosd 1, somali 1, irc 1, uweast 1 (990 total)
- Carried over (not collected this time): cair (site showed a bot check; nothing of theirs was in the window last time)
- Labels: relevant 136, possibly 51, not 762 (duplicates left out); decided by rule 568, human 312, memory 62, ai 48
- Going to the calendar (relevant.ics): 185 events
- Problems: Teamup still showed the removed second link on 2026-10-21; make_feeds.py now stamps DTSTAMP, LAST-MODIFIED and SEQUENCE at each build so subscribers re-read changed events
- Feeds built: pending JTD's review; published: not yet
- Printout: not yet

- 2026-11-10: JTD's review of the Oct 21 batch was ingested; feeds were not published, at JTD's request, in favour of this refresh

## 2026-11-10
- Window: 2026-11-10 to 2026-12-10
- Collected (events in window): sdcl 115, carlsbad 43, nationalcity 44, coronado 31, oceanside 31, chulavista 6, escondido 4, sandiego-pl 824 (two brochures, 2026-11-10 to 2026-11-27), eventbrite 47, jfs 25, casafamiliar 9, lassd 2, sdvlp 1, maac 0, borderangels 3, alliancesd 2, majdal 1, casacornelia 1, interfaith 1, uweast 1 (1191 total)
- Carried over (not collected this time): none. SDPL has no events after Nov 27 (brochures end there)
- Labels: relevant 129, possibly 25, not 1037; decided by rule 695, memory 272, ai 204, human 20
- Going to the calendar (relevant.ics): 147 events
- Criteria: general-service resource tables moved to Not relevant (JTD, 2026-11-10); rules tabling-category and tabling-title follow
- Problems: Instagram profile grids no longer sit inside a <main> element (IG_CAPTIONS selector fixed); individual post pages came back blank, so the Instagram pass stopped there and no captions were expanded; somalifamilyservice grid did not load; CAIR events page empty (loads by script)
- After JTD's review (decisions ingested; examples.jsonl 521): relevant 129, possibly 19, not 1043; decided by rule 695, memory 270, ai 201, human 25
- Feeds built: yes (all 143: citizenship-legal 38, rights-civic 1, esl 85, tabling 4, possibly 15), with build-time DTSTAMP/LAST-MODIFIED/SEQUENCE; published: pushed by Claude (commit 8b525c8)
- Printout: print/handout_2026-11-16.pdf (2 pages, 18 QR codes; SDPL only through Nov 27)

## 2026-11-16: automation set up
- Source test from GitHub's servers: 10 of 14 sources reachable. Blocked: Chula Vista, Carlsbad, National City (403), Eventbrite (human-verification page)
- JTD's decisions: Eventbrite dropped; Carlsbad, Chula Vista and National City join the monthly hand-run pass with Instagram and the unstructured agency pages; AI "relevant" labels publish without review; tools may be public
- Tools, raw data and evaluation files moved into this repository under automation/. This repository is now the working copy; the Desktop folder is no longer updated by the daily run
- Daily run (.github/workflows/update.yml, about 5-6 am Pacific): collect.py -> build_batch.py -> evaluate.py -> make_feeds.py -> publish.py. Result in automation/status.md
- First automated publish: 133 events (citizenship-legal 32, rights-civic 1, esl 81, tabling 4, possibly 15); live site checked
- Fixed on the way: Python 3.13 needed; feed reader mishandled Windows line endings (one run briefly published 104 events, corrected within minutes); queued runs now start from the newest state
- Not done yet: weekly Claude pass for new titles and review decisions; automated handout; the temporary "samples" branch could not be deleted from here
