#!/usr/bin/env python3
"""Copy the handout built by make_print.py to the site:
  handout.pdf                      always the newest (the permanent link)
  handouts/handout_<start>.pdf     dated copy
and record it in state.json so status.md shows it.   Usage: publish_handout.py YYYY-MM-DD
"""
import json, shutil, sys
from pathlib import Path
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT.parent
start = sys.argv[1]
src = ROOT / "print" / f"handout_{start}.pdf"
pages = len(PdfReader(str(src)).pages)
entries = len(json.loads((ROOT / "print" / f"qr_{start}.json").read_text(encoding="utf-8")))
(SITE / "handouts").mkdir(exist_ok=True)
shutil.copyfile(src, SITE / "handouts" / f"handout_{start}.pdf")
shutil.copyfile(src, SITE / "handout.pdf")
state_p = ROOT / "state.json"
state = json.loads(state_p.read_text())
state["last_handout"] = {"start": start, "pages": pages, "entries": entries}
state_p.write_text(json.dumps(state, indent=1) + "\n")
line = f"\n## Handout\n\nNewest: two weeks from {start}, {entries} entries, {pages} page{'s' if pages != 1 else ''}. Permanent link: `handout.pdf`; dated copies in `handouts/`.\n"
with open(ROOT / "status.md", "a", encoding="utf-8") as f:
    f.write(line)
print(line)
if pages > 2:
    print("WARNING: the handout ran to more than two pages")
