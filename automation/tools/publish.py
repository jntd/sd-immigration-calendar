#!/usr/bin/env python3
"""Last step of the automated run: check the new feeds, copy them to the site (the repository
root, which GitHub Pages serves), and write status.md.

Safety checks:
  - If the calendar would shrink to under 60% of what is live, nothing is published (exit 2).
  - If a source has failed three runs in a row, the feeds are still published (the source's last
    good data is used) but the run is marked failed so GitHub emails the owner (exit 3).
"""
import datetime as dt, json, re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT.parent
NEW = ROOT / "feeds"
NAMES = ["all", "citizenship-legal", "rights-civic", "esl", "tabling", "possibly"]


def count(p):
    return p.read_text(encoding="utf-8").count("BEGIN:VEVENT") if p.exists() else 0


def core(p):  # feed text without the build-time stamps, to see whether anything really changed
    return re.sub(r"\r\n(DTSTAMP|LAST-MODIFIED|SEQUENCE)[;:][^\r]*", "", p.read_text(encoding="utf-8", newline="")) if p.exists() else ""


def main():
    state = json.loads((ROOT / "state.json").read_text())
    n_old, n_new = count(SITE / "all.ics"), count(NEW / "all.ics")
    held = n_old >= 20 and n_new < 0.6 * n_old
    changed = []
    if not held:
        for n in NAMES:
            if core(NEW / f"{n}.ics") != core(SITE / f"{n}.ics"):
                shutil.copyfile(NEW / f"{n}.ics", SITE / f"{n}.ics")
                changed.append(n)
    queue = [l for l in (ROOT / "evaluation" / "work" / "judge_queue.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    fails = {k: v for k, v in state.get("consecutive_failures", {}).items() if v}
    stuck = [k for k, v in fails.items() if v >= 3]
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    L = ["# Calendar status", "", f"Last automated run: {now} Pacific", ""]
    if held:
        L += [f"**NOT PUBLISHED.** The new calendar had {n_new} events against {n_old} live, which looks like a fault. "
              "The live calendar was left as it was.", ""]
    else:
        L += [f"Published: {n_new} events" + (f" (feeds changed: {', '.join(changed)})" if changed else " (no change since the last run)"), ""]
        L += ["| Feed | Events |", "|---|---|"] + [f"| {n} | {count(SITE / (n + '.ics'))} |" for n in NAMES] + [""]
    L += ["## Sources collected automatically", "", "| Source | Result | Events in window |", "|---|---|---|"]
    for k, r in state["last_collect"]["sources"].items():
        L.append(f"| {k} | {'ok' if r['ok'] else 'FAILED (' + str(fails.get(k, 1)) + ' in a row): ' + r['error'].replace('|', '/')} | {r.get('events', 'last good copy kept')} |")
    L += ["", "Carlsbad, Chula Vista, National City, Instagram and the other agency pages come from the monthly hand-run pass.", "",
          f"## Waiting for a decision: {len(queue)} new titles", "",
          "New titles are held back from the calendar until the weekly AI pass judges them.", ""]
    L += [f"- {json.loads(q)['source']}: {json.loads(q)['title']}" for q in queue[:60]]
    (ROOT / "status.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    state["last_publish"] = {"when": now, "events": n_new, "held": held, "changed": changed}
    (ROOT / "state.json").write_text(json.dumps(state, indent=1) + "\n")
    print("\n".join(L[:12]))
    if held:
        sys.exit(2)
    if stuck:
        print("Sources failing three runs in a row:", ", ".join(stuck))
        sys.exit(3)


if __name__ == "__main__":
    main()
