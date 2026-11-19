#!/usr/bin/env python3
"""Small helper for skool-manager/state/registry.json (standard library only).

  python3 -I skool-manager/tools/registry.py validate
  python3 -I skool-manager/tools/registry.py queue
  python3 -I skool-manager/tools/registry.py seen <gmail-message-id>      # exit 0 if already processed
  python3 -I skool-manager/tools/registry.py mark D-001 edited --edit "her exact text" --note "why"
  python3 -I skool-manager/tools/registry.py mark D-001 published_confirmed --note "Anisia: posted it"

Every write re-reads the file and validates it (read-after-write check).
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "state", "registry.json")
STATUSES = {"queued_for_user", "approved", "edited", "rejected", "skipped", "published_confirmed"}
REPLY_STATUSES = {"needs_verification", "confirmed_unanswered", "confirmed_answered", "not_applicable"}
REQUIRED = ["id", "dedupe_key", "community", "source_url", "author", "conversation",
            "status", "reply_status", "draft_text", "created_at"]


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load():
    with open(PATH, encoding="utf-8") as f:
        return json.load(f)


def problems(reg):
    out = []
    ids, keys = set(), set()
    published = {p.get("draft_id") for p in reg.get("publish_log", [])}
    for d in reg.get("draft_queue", []):
        for k in REQUIRED:
            if k not in d:
                out.append(f"{d.get('id', '?')}: missing field {k}")
        if d.get("id") in ids:
            out.append(f"duplicate draft id {d.get('id')}")
        ids.add(d.get("id"))
        key = (d.get("dedupe_key") or "").lower()
        if key in keys and d.get("status") not in {"rejected", "skipped"}:
            out.append(f"{d.get('id')}: duplicate dedupe_key {key}")
        keys.add(key)
        if d.get("status") not in STATUSES:
            out.append(f"{d.get('id')}: bad status {d.get('status')!r}")
        if d.get("reply_status") not in REPLY_STATUSES:
            out.append(f"{d.get('id')}: bad reply_status {d.get('reply_status')!r}")
        if d.get("status") == "published_confirmed":
            if not d.get("publish_confirmation") or d.get("id") not in published:
                out.append(f"{d.get('id')}: published_confirmed without user confirmation + publish_log entry")
    psi = reg.get("processed_source_ids", [])
    if len(psi) != len(set(psi)):
        out.append("processed_source_ids contains duplicates")
    return out


def save(reg):
    tmp = PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, PATH)
    again = load()  # read-after-write
    if again != reg:
        sys.exit("read-after-write check FAILED")
    errs = problems(again)
    if errs:
        sys.exit("saved, but validation failed:\n" + "\n".join(errs))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate")
    sub.add_parser("queue")
    s = sub.add_parser("seen")
    s.add_argument("source_id")
    m = sub.add_parser("mark")
    m.add_argument("draft_id")
    m.add_argument("status", choices=sorted(STATUSES))
    m.add_argument("--edit")
    m.add_argument("--note")
    m.add_argument("--reply-status", choices=sorted(REPLY_STATUSES))
    a = ap.parse_args()
    reg = load()

    if a.cmd == "validate":
        errs = problems(reg)
        print("OK" if not errs else "\n".join(errs))
        sys.exit(1 if errs else 0)
    if a.cmd == "queue":
        for d in reg["draft_queue"]:
            if d["status"] in {"queued_for_user", "approved", "edited"}:
                print(f"{d['id']} [{d['status']}/{d['reply_status']}] {d['community']} · {d['author']} · {d['source_url']}")
        return
    if a.cmd == "seen":
        sys.exit(0 if a.source_id in reg["processed_source_ids"] else 1)

    d = next((x for x in reg["draft_queue"] if x["id"] == a.draft_id), None)
    if d is None:
        sys.exit(f"no draft {a.draft_id}")
    ts = now()
    d.setdefault("history", []).append({"at": ts, "from": d["status"], "to": a.status, "note": a.note})
    d["status"] = a.status
    if a.reply_status:
        d["reply_status"] = a.reply_status
    if a.edit is not None:
        d["user_edit"] = a.edit
    if a.status in {"edited", "rejected", "skipped", "approved"}:
        reg["feedback_log"].append({"at": ts, "draft_id": d["id"], "action": a.status,
                                    "original": d["draft_text"], "user_edit": a.edit, "note": a.note})
    if a.status == "published_confirmed":
        d["publish_confirmation"] = {"confirmed_by": "Anisia", "at": ts, "note": a.note}
        reg["publish_log"].append({"draft_id": d["id"], "at": ts, "community": d["community"],
                                   "source_url": d["source_url"], "text": d.get("user_edit") or d["draft_text"],
                                   "note": a.note})
    save(reg)
    print(f"{d['id']} -> {a.status} (saved, re-read, valid)")


if __name__ == "__main__":
    main()
