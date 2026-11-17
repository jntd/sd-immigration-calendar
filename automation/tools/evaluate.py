#!/usr/bin/env python3
"""Relevance evaluation for the SD immigration events calendar.

Steps, in order, for every event in batch.ics:
  1. memory - JTD's earlier review decisions (evaluation/examples.jsonl): same UID, or same source + same title
  2. rules  - evaluation/rules.json keyword rules
  3. ai     - anything still undecided goes to evaluation/work/judge_queue.jsonl for the AI judge,
              whose answers are read from evaluation/work/ai_judgments.jsonl (and cached for repeat titles)
  4. human  - the review page; its decisions are ingested into examples.jsonl and win from then on

Commands:
  python3 evaluate.py run                  label everything, write the judge queue and the outputs
  python3 evaluate.py ingest <file-or-folder>  add review-page decisions to examples.jsonl, then run

Outputs (folder root):
  labeled.ics   every event, with X-SD-LABEL, X-SD-TAGS, X-SD-REASON, X-SD-DECIDED-BY
  relevant.ics  events to publish: 'relevant' ones, plus 'possibly' ones decided by JTD or a rule (never unreviewed AI),
                which get the category 'Possibly relevant' so calendar users can filter them out
  evaluation/review_data.json  compact list for the review page
"""
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / "evaluation"
WORK = EVAL / "work"
LABELS = {"relevant", "possibly", "not"}
TAGS = ["Citizenship", "Immigration legal", "Rights & civic", "ESL", "Tabling", "Jobs & money", "Housing", "Health",
        "Family & youth", "Community & culture", "Volunteer", "Online", "Spanish", "Other language"]


# ---------- iCalendar helpers ----------
def unfold(s):
    return re.sub(r"\r\n[ \t]", "", s)


def fold(line):
    b = line.encode("utf-8")
    if len(b) <= 75:
        return line
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


def unesc(s):
    return s.replace("\\n", " ").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def prop(block, name):
    m = re.search(rf"^{name}([;:].*)$", block, flags=re.M)
    if not m:
        return ""
    v = m.group(1)
    return unesc(v.split(":", 1)[1]).strip() if ":" in v else ""


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def read_batch():
    raw = (ROOT / "batch.ics").read_text(encoding="utf-8", newline="")
    head, rest = raw.split("BEGIN:VEVENT", 1)
    blocks = ["BEGIN:VEVENT" + b.split("END:VEVENT")[0] + "END:VEVENT" for b in ("BEGIN:VEVENT" + rest).split("BEGIN:VEVENT")[1:]]
    events = []
    for b in blocks:
        u = unfold(b)
        dm = re.search(r"^DTSTART[^:]*:([0-9TZ]+)", u, flags=re.M)
        cats = prop(u, "CATEGORIES")
        events.append({
            "block": b, "uid": prop(u, "UID"), "title": prop(u, "SUMMARY").strip(), "start_raw": dm.group(1) if dm else "",
            "location": prop(u, "LOCATION"), "url": prop(u, "URL"), "categories": cats, "description": prop(u, "DESCRIPTION"),
            "source": prop(u, "X-SD-SOURCE"), "source_name": prop(u, "X-SD-SOURCE-NAME"), "route": prop(u, "X-SD-ROUTE"),
            "cancelled": prop(u, "STATUS").upper() == "CANCELLED", "duplicate_of": prop(u, "X-SD-DUPLICATE-OF"),
            "needs_check": prop(u, "X-SD-NEEDS-CHECK"), "post": prop(u, "X-SD-POST"), "note": prop(u, "X-SD-NOTE"),
        })
    return head, events


def local_start(raw):
    """Readable Pacific start time for the review page."""
    if not raw:
        return ""
    if len(raw) == 8:
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    t = dt.datetime.strptime(raw[:15], "%Y%m%dT%H%M%S")
    if raw.endswith("Z"):  # UTC -> Pacific (DST from 2nd Sun Mar to 1st Sun Nov)
        y = t.year
        dst0 = dt.datetime(y, 3, 8 + (6 - dt.date(y, 3, 8).weekday()) % 7, 10)
        dst1 = dt.datetime(y, 11, 1 + (6 - dt.date(y, 11, 1).weekday()) % 7, 9)
        t -= dt.timedelta(hours=7 if dst0 <= t < dst1 else 8)
    return t.strftime("%Y-%m-%d %H:%M")


# ---------- memory, rules, AI ----------
def load_jsonl(p):
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def memory_lookup(ev, by_uid, by_series):
    if ev["uid"] in by_uid:
        return by_uid[ev["uid"]], "your decision on this event"
    k = (ev["source"], norm(ev["title"]))
    if k in by_series:
        return by_series[k], "your decision on an earlier listing with the same title"
    return None, None


def apply_rules(ev, cfg):
    groups = cfg["source_groups"]

    def expand(lst):
        out = set()
        for x in lst or []:
            out |= set(groups.get(x, [x]))
        return out

    tags, label, reason, rule_id = [], None, None, None
    fields = {"title": ev["title"], "categories": ev["categories"], "location": ev["location"],
              "text": " | ".join([ev["title"], ev["categories"], ev["location"]])}
    for r in cfg["rules"]:
        if r.get("sources") and ev["source"] not in expand(r["sources"]):
            continue
        if r.get("not_sources") and ev["source"] in expand(r["not_sources"]):
            continue
        sp = r.get("special")
        if sp == "cancelled":
            hit = ev["cancelled"]
        elif sp == "duplicate":
            hit = bool(ev["duplicate_of"])
        else:
            hit = re.search(r["pattern"], fields[r["in"]], flags=re.I) is not None
        if not hit:
            continue
        for t in r.get("tags", []):
            if t not in tags:
                tags.append(t)
        if label is None and r.get("label"):
            label, reason, rule_id = r["label"], r["reason"], r["id"]
    return label, reason, rule_id, tags


def run():
    WORK.mkdir(parents=True, exist_ok=True)
    cfg = json.loads((EVAL / "rules.json").read_text(encoding="utf-8"))
    examples = load_jsonl(EVAL / "examples.jsonl")
    by_uid, by_series = {}, {}
    for x in examples:  # later decisions win
        by_uid[x["uid"]] = x
        by_series[(x["source"], norm(x["title"]))] = x

    ai_cache = {}  # (source, title) -> judgment; AI answers are reused for repeat listings, never become 'memory'
    for x in load_jsonl(WORK / "ai_cache.jsonl") + load_jsonl(WORK / "ai_judgments.jsonl"):
        if x.get("label") in LABELS and x.get("reason"):
            ai_cache[(x["source"], norm(x["title"]))] = x
    with open(WORK / "ai_cache.jsonl", "w", encoding="utf-8") as f:
        for x in ai_cache.values():
            f.write(json.dumps(x, ensure_ascii=False) + "\n")

    head, events = read_batch()
    queue, counts = [], {}
    for ev in events:
        r_label, r_reason, r_id, r_tags = apply_rules(ev, cfg)
        mem, why = memory_lookup(ev, by_uid, by_series)
        if mem and not ev["duplicate_of"] and not ev["cancelled"]:
            ev.update(label=mem["label"], reason=mem.get("note") or why, decided_by="memory" if mem["uid"] != ev["uid"] else "human",
                      tags=mem.get("tags") or r_tags)
        elif r_label:
            ev.update(label=r_label, reason=r_reason, decided_by=f"rule:{r_id}", tags=r_tags)
        elif (ev["source"], norm(ev["title"])) in ai_cache:
            j = ai_cache[(ev["source"], norm(ev["title"]))]
            ev.update(label=j["label"], reason=j["reason"], decided_by="ai",
                      tags=list(dict.fromkeys(r_tags + [t for t in j.get("tags", []) if t in TAGS])))
        else:
            ev.update(label="possibly", reason="Not yet judged", decided_by="pending", tags=r_tags)
            queue.append({"uid": ev["uid"], "source": ev["source"], "source_name": ev["source_name"], "title": ev["title"],
                          "start": local_start(ev["start_raw"]), "location": ev["location"], "categories": ev["categories"],
                          "description": ev["description"][:400], "rule_tags": r_tags})
        counts[ev["decided_by"].split(":")[0]] = counts.get(ev["decided_by"].split(":")[0], 0) + 1

    # one queue line per distinct source+title (repeat listings are judged once)
    seen, q = set(), []
    for x in queue:
        k = (x["source"], norm(x["title"]))
        if k not in seen:
            seen.add(k)
            q.append(x)
    with open(WORK / "judge_queue.jsonl", "w", encoding="utf-8") as f:
        for x in q:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")

    write_outputs(head, events, by_uid)
    lab = {}
    for ev in events:
        lab[ev["label"]] = lab.get(ev["label"], 0) + 1
    print(f"{len(events)} events. Decided by: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    print("Labels: " + ", ".join(f"{k} {v}" for k, v in sorted(lab.items())))
    print(f"Judge queue: {len(q)} distinct titles ({len(queue)} events) -> evaluation/work/judge_queue.jsonl")


def write_outputs(head, events, by_uid):
    today = dt.date.today().isoformat()
    labeled, relevant, review = [], [], []
    for ev in events:
        add = [f"X-SD-LABEL:{ev['label'].upper()}", fold("X-SD-TAGS:" + ",".join(esc(t) for t in ev["tags"])) if ev["tags"] else None,
               fold("X-SD-REASON:" + esc(ev["reason"])), f"X-SD-DECIDED-BY:{ev['decided_by']}", f"X-SD-EVALUATED:{today}"]
        add = [a for a in add if a]
        status = "REVIEWED" if ev["decided_by"] in ("human", "memory") else "LABELED"
        b = re.sub(r"\r\nX-SD-(LABEL|TAGS|REASON|DECIDED-BY|EVALUATED):.*?(?=\r\n[^ \t])", "", ev["block"], flags=re.S)
        b = b.replace("X-SD-STATUS:UNREVIEWED", f"X-SD-STATUS:{status}")
        b = b.replace("\r\nEND:VEVENT", "\r\n" + "\r\n".join(add) + "\r\nEND:VEVENT")
        labeled.append(b)
        publish = ev["label"] == "relevant" or (ev["label"] == "possibly" and ev["decided_by"] in ("human", "memory")
                                                     or ev["label"] == "possibly" and ev["decided_by"].startswith("rule"))
        if publish:
            cats = ev["tags"] + (["Possibly relevant"] if ev["label"] == "possibly" else [])
            rb = b
            if cats:  # make tags visible to calendar apps as CATEGORIES, so users can filter (e.g. hide ESL or Tabling)
                rb = re.sub(r"\r\nCATEGORIES[^\r]*(\r\n[ \t][^\r]*)*", "", rb)
                rb = rb.replace("\r\nX-SD-SOURCE:", "\r\n" + fold("CATEGORIES:" + ",".join(esc(t) for t in cats)) + "\r\nX-SD-SOURCE:", 1)
            relevant.append(rb)
        review.append({k: ev[k] for k in ("uid", "title", "location", "url", "post", "source", "source_name", "route", "label",
                                          "tags", "reason", "decided_by", "needs_check", "duplicate_of", "categories")}
                      | {"start": local_start(ev["start_raw"])})
    tail = "END:VCALENDAR\r\n"
    (ROOT / "labeled.ics").write_text(head.replace("batch (unreviewed)", "labeled") + "\r\n".join(labeled) + "\r\n" + tail,
                                      encoding="utf-8", newline="")
    (ROOT / "relevant.ics").write_text(head.replace("batch (unreviewed)", "relevant") + "\r\n".join(relevant) + "\r\n" + tail,
                                       encoding="utf-8", newline="")
    review.sort(key=lambda x: x["start"])
    (EVAL / "review_data.json").write_text(json.dumps({"generated": today, "tags": TAGS, "events": review}, ensure_ascii=False),
                                           encoding="utf-8")


def ingest(path):
    """Add review-page decisions to examples.jsonl.
    path: a JSON file holding a list of decisions, or a folder of saved decision documents
    (ArtifactData list with out_dir). Each decision: {uids: [...]} or {uid}, plus label, tags, note, decided."""
    p = Path(path)
    raw = []
    if p.is_dir():
        for f in sorted(p.rglob("*.json")):
            raw.append(json.loads(f.read_text(encoding="utf-8")))
    else:
        raw = json.loads(p.read_text(encoding="utf-8"))
    _, events = read_batch()
    by = {e["uid"]: e for e in events}
    old = {x["uid"]: x for x in load_jsonl(EVAL / "examples.jsonl")}
    n = 0
    for d in raw:
        d = d.get("data", d) if isinstance(d.get("data"), dict) else d
        if d.get("label") not in LABELS:
            continue
        for uid in d.get("uids") or [d.get("uid")]:
            e = by.get(uid)
            src, title = (e["source"], e["title"]) if e else (d.get("source", ""), d.get("title", ""))
            if not src:
                continue
            old[uid] = {"uid": uid, "source": src, "title": title, "label": d["label"],
                        "tags": [t for t in d.get("tags", []) if t in TAGS], "note": d.get("note", ""),
                        "decided": d.get("decided", dt.date.today().isoformat())}
            n += 1
    with open(EVAL / "examples.jsonl", "w", encoding="utf-8") as f:
        for x in old.values():
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    print(f"Ingested {n} event decisions; examples.jsonl now has {len(old)}")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "ingest":
        ingest(sys.argv[2])
    run()
