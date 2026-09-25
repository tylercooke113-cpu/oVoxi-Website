#!/usr/bin/env python3
"""Read-only: per-submission stem key format and OQ-2 collision damage.

Reads MongoDB directly. No writes. Prints to stdout.

Usage:
    python3 scripts/audit_stem_collisions.py
"""
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).parent.parent / "backend" / ".env")


async def main() -> None:
    mongo = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = mongo[os.environ["DB_NAME"]]

    docs = await db.track_submissions.find(
        {"status": "completed", "stem_paths": {"$exists": True, "$ne": {}}},
        {"_id": 0, "id": 1, "artist_name": 1, "track_name": 1, "stem_paths": 1},
    ).sort("upload_date", 1).to_list(10000)

    if not docs:
        print("No completed submissions with stem_paths found.")
        mongo.close()
        return

    # stem_key → [submission_id, ...] for collision detection
    key_to_subs: dict[str, list[str]] = {}

    print(f"{'SUBMISSION ID':<38} {'KEYED':5}  {'ARTIST':<25}  TRACK")
    print("-" * 110)

    for doc in docs:
        sub_id = doc["id"]
        artist = doc.get("artist_name", "?")
        track  = doc.get("track_name", "?")
        stem_paths: dict = doc.get("stem_paths", {})

        # A submission is keyed if every stem key embeds the submission id.
        keyed = bool(stem_paths) and all(sub_id in key for key in stem_paths.values())

        print(f"{sub_id:<38} {'yes' if keyed else 'NO':<5}  {artist[:25]:<25}  {track}")

        for key in stem_paths.values():
            key_to_subs.setdefault(key, []).append(sub_id)

    collisions = {k: subs for k, subs in key_to_subs.items() if len(subs) > 1}

    n_keyed = sum(
        1 for doc in docs
        if doc.get("stem_paths")
        and all(doc["id"] in k for k in doc["stem_paths"].values())
    )
    total = len(docs)

    print()
    print(f"Total completed:                              {total}")
    print(f"Submission-keyed stems (new key convention):  {n_keyed}")
    print(f"Legacy (shared-path convention):              {total - n_keyed}")
    print(f"OQ-2 collisions (key shared by >1 submission): {len(collisions)}")

    if collisions:
        print()
        print("COLLIDING KEYS:")
        for key, subs in sorted(collisions.items()):
            print(f"  {key}")
            for s in subs:
                print(f"    → {s}")

    mongo.close()


asyncio.run(main())
