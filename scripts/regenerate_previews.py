#!/usr/bin/env python3
"""
Regenerate sync-library previews at the new keys (Brief 25 Part A).

Each targeted track gets a 128 kbps full preview (.full128.mp3) and a
60-second public excerpt (.short.mp3) written under its previews/ prefix.
The old 320 kbps .mp3 object is NOT deleted — its key is recorded on the
document as legacy_preview_key so Tyler can decide on deletion after the
production checks pass.

Targets: completed tracks that have a mastered_r2_key but no
preview_short_key yet, so a re-run after success does nothing and a
half-finished run resumes safely (the worker guard never overwrites).

Usage:
    python scripts/regenerate_previews.py          # dry run, prints the plan
    python scripts/regenerate_previews.py --apply   # writes previews + updates docs
"""
import argparse
import os
from pathlib import Path

import modal
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).parent.parent / "backend" / ".env")

CHUNK = 25


def main(apply: bool) -> None:
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    docs = list(db.track_submissions.find(
        {"status": "completed",
         "mastered_r2_key": {"$exists": True, "$ne": None},
         "$or": [{"preview_short_key": {"$exists": False}}, {"preview_short_key": None}]},
        {"_id": 0, "id": 1, "artist_name": 1, "track_name": 1,
         "preview_key": 1, "mastered_r2_key": 1},
    ))

    if not docs:
        print("No tracks needing previews (every completed track already has preview_short_key).")
        return

    print(f"Found {len(docs)} track(s). Mode: {'APPLY' if apply else 'DRY-RUN'}\n")
    for d in docs:
        print(f"  {d['id']}  {d.get('artist_name')} / {d.get('track_name')}")
        print(f"     mastered : {d['mastered_r2_key']}")
        print(f"     old 320k : {d.get('preview_key') or '(none)'}  (kept, not deleted)")

    if not apply:
        print("\nDry run only. Re-run with --apply to write the new previews.")
        return

    old_preview = {d["id"]: d.get("preview_key") for d in docs}
    items = [{"submission_id": d["id"], "mastered_r2_key": d["mastered_r2_key"]} for d in docs]
    fn = modal.Function.from_name("ovoxi-stem-worker", "regenerate_previews")
    chunks = [items[i:i + CHUNK] for i in range(0, len(items), CHUNK)]
    results = [r for batch in fn.map(chunks) for r in batch]

    print()
    updated = 0
    for r in results:
        if r.get("error"):
            print(f"  ERROR  {r['submission_id']}: {r['error']}")
            continue
        set_doc = {"preview_key": r["preview_key"], "preview_short_key": r["preview_short_key"]}
        old = old_preview.get(r["submission_id"])
        if old and old.endswith(".mp3") and not old.endswith(".full128.mp3"):
            set_doc["legacy_preview_key"] = old
        db.track_submissions.update_one({"id": r["submission_id"]}, {"$set": set_doc})
        updated += 1
        print(f"  OK     {r['submission_id']}  ->  {r['preview_key']} , {r['preview_short_key']}")
    print(f"\nUpdated {updated}/{len(results)} document(s).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write previews and update documents")
    main(ap.parse_args().apply)
