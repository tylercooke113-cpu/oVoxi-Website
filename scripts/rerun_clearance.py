#!/usr/bin/env python3
"""
Re-run clearance on every track with usage choices (Brief 25b Part D1).

D1 added the AI-tools check and an ai_status for AI-training songs, so stored
results are stale until each track is evaluated again. This uses the same
clearance_fields() the server uses. Run once at deploy, after Railway is live.

Usage:
    python scripts/rerun_clearance.py          # dry run: prints what would change
    python scripts/rerun_clearance.py --apply   # writes the new results
"""
import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

BACKEND = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(BACKEND))
load_dotenv(BACKEND / ".env")

from clearance import clearance_fields  # noqa: E402

SHOWN = ("sync_status", "ai_status", "on_sync_profile")


def main(apply: bool) -> None:
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    now_iso = datetime.now(timezone.utc).isoformat()
    docs = list(db.track_submissions.find({"consent": {"$type": "object"}}, {"_id": 0}))
    changed = 0
    for doc in docs:
        fields = clearance_fields(doc, now_iso)
        diff = {k: (doc.get(k), fields[k]) for k in SHOWN if doc.get(k) != fields[k]}
        if not diff:
            continue
        changed += 1
        label = f"{doc.get('artist_name')} - {doc.get('track_name')} ({doc.get('id')})"
        print(label + ": " + ", ".join(f"{k} {a!r} -> {b!r}" for k, (a, b) in diff.items()))
        if apply:
            db.track_submissions.update_one({"id": doc["id"]}, {"$set": fields})
    print(f"\n{len(docs)} tracks checked, {changed} would change." if not apply
          else f"\n{len(docs)} tracks checked, {changed} updated.")
    if not apply:
        print("Dry run. Nothing was written. Re-run with --apply to write.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--apply", action="store_true", help="write the new results")
    main(ap.parse_args().apply)
