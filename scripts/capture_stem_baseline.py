#!/usr/bin/env python3
"""
Phase 0 baseline capture — copy LALAL-generated stems from R2 to disk.

Dry run (default): prints artist / track / genre / stem count per submission.
--confirm:         downloads to benchmark/lalal-baseline/{submission_id}/ and
                   writes / updates benchmark/lalal-baseline/manifest.json.

Re-run safe: --confirm skips any submission already recorded in the manifest.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from pymongo import MongoClient, DESCENDING

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ENV = REPO_ROOT / "backend" / ".env"
BASELINE_DIR = REPO_ROOT / "benchmark" / "lalal-baseline"
MANIFEST_PATH = BASELINE_DIR / "manifest.json"
EXPECTED_STEMS = {"vocals", "drums", "bass", "other"}


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def load_env() -> None:
    if not BACKEND_ENV.exists():
        sys.exit(f"ERROR: {BACKEND_ENV} not found — populate it from Railway secrets")
    load_dotenv(BACKEND_ENV)
    for var in ("MONGO_URL", "DB_NAME", "R2_ENDPOINT",
                "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME"):
        if not os.environ.get(var):
            sys.exit(f"ERROR: {var} is not set in {BACKEND_ENV}")


def get_collection():
    client = MongoClient(os.environ["MONGO_URL"])
    return client[os.environ["DB_NAME"]]["track_submissions"]


def get_r2():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


# ---------------------------------------------------------------------------
# Mongo query
# ---------------------------------------------------------------------------

def fetch_submissions(col) -> list[dict]:
    return list(
        col.find(
            {"status": "completed", "stem_paths": {"$exists": True, "$ne": {}}},
            {"_id": 0, "id": 1, "artist_name": 1, "track_name": 1, "genre": 1,
             "stem_paths": 1, "mastered_r2_key": 1, "original_r2_path": 1,
             "upload_date": 1},
            sort=[("upload_date", DESCENDING)],
            limit=10,
        )
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def mastered_key(doc: dict) -> str | None:
    if doc.get("mastered_r2_key"):
        return doc["mastered_r2_key"]
    orig = doc.get("original_r2_path", "")
    if "/original/" in orig:
        return orig.replace("/original/", "/mastered/", 1)
    return None


def load_manifest() -> dict[str, dict]:
    if not MANIFEST_PATH.exists():
        return {}
    with open(MANIFEST_PATH) as fh:
        return {e["submission_id"]: e for e in json.load(fh)}


def save_manifest(entries: dict[str, dict]) -> None:
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w") as fh:
        json.dump(list(entries.values()), fh, indent=2, default=str)


# ---------------------------------------------------------------------------
# Dry run
# ---------------------------------------------------------------------------

def print_dry_run(submissions: list[dict]) -> None:
    col_widths = {"id": 36, "artist": 22, "track": 22, "genre": 14, "stems": 6}
    header = (
        f"{'SUBMISSION ID':<{col_widths['id']}}"
        f"{'ARTIST':<{col_widths['artist']}}"
        f"{'TRACK':<{col_widths['track']}}"
        f"{'GENRE':<{col_widths['genre']}}"
        f"{'STEMS':<{col_widths['stems']}}"
        f"NOTES"
    )
    print(header)
    print("─" * 120)

    for doc in submissions:
        sid = doc.get("id", "?")
        artist = (doc.get("artist_name") or "?")[:col_widths["artist"] - 1]
        track = (doc.get("track_name") or "?")[:col_widths["track"] - 1]
        genre = (doc.get("genre") or "?")[:col_widths["genre"] - 1]
        found = set(doc.get("stem_paths", {}).keys())
        missing = EXPECTED_STEMS - found
        stem_col = f"{len(found)}/4"
        mkey = mastered_key(doc)

        notes = []
        if missing:
            notes.append(f"INCOMPLETE missing={sorted(missing)}")
        if not mkey:
            notes.append("NO_MASTERED_KEY")
        else:
            notes.append(f"mastered={mkey}")

        print(
            f"{sid:<{col_widths['id']}}"
            f"{artist:<{col_widths['artist']}}"
            f"{track:<{col_widths['track']}}"
            f"{genre:<{col_widths['genre']}}"
            f"{stem_col:<{col_widths['stems']}}"
            f"{'  '.join(notes)}"
        )

    print(f"\n{len(submissions)} submission(s) matched. Pass --confirm to download.")


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def download_submission(
    doc: dict,
    r2,
    bucket: str,
) -> tuple[dict, int]:
    sid = doc["id"]
    stem_paths: dict = doc.get("stem_paths", {})
    found_stems = sorted(stem_paths.keys())
    complete = (set(found_stems) == EXPECTED_STEMS)
    mkey = mastered_key(doc)

    sub_dir = BASELINE_DIR / sid
    sub_dir.mkdir(parents=True, exist_ok=True)

    files: dict[str, dict] = {}
    total_bytes = 0

    keys_to_fetch: list[tuple[str, str]] = [
        (stem_name, r2_key) for stem_name, r2_key in stem_paths.items()
    ]
    if mkey:
        keys_to_fetch.append(("mastered", mkey))
    else:
        print(f"  WARNING: no mastered key resolvable — skipping mastered source")

    for label, r2_key in keys_to_fetch:
        ext = Path(r2_key).suffix  # derive from the key; never assume .mp3
        local_path = sub_dir / f"{label}{ext}"

        try:
            resp = r2.get_object(Bucket=bucket, Key=r2_key)
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code == "NoSuchKey":
                print(f"  {label:<14} MISSING in R2  ← {r2_key}")
                files[label] = {"r2_key": r2_key, "error": "NoSuchKey", "bytes": 0}
                continue
            raise

        data: bytes = resp["Body"].read()

        if len(data) == 0:
            raise ValueError(
                f"R2 returned a zero-byte object for key '{r2_key}' "
                f"(submission {sid}, label '{label}') — refusing to write"
            )

        local_path.write_bytes(data)
        nbytes = len(data)
        files[label] = {
            "r2_key": r2_key,
            "local_path": str(local_path.relative_to(REPO_ROOT)),
            "bytes": nbytes,
        }
        total_bytes += nbytes
        print(f"  {label:<14} {nbytes:>12,} bytes  ← {r2_key}")

    entry = {
        "submission_id": sid,
        "artist_name": doc.get("artist_name"),
        "track_name": doc.get("track_name"),
        "genre": doc.get("genre"),
        "complete": complete,
        "found_stems": found_stems,
        "files": files,
    }
    return entry, total_bytes


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture LALAL stem baseline. Default is dry run."
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Download files. Without this flag only prints what would be copied.",
    )
    args = parser.parse_args()

    load_env()
    col = get_collection()
    submissions = fetch_submissions(col)

    if not submissions:
        print("No completed submissions with stem_paths found — nothing to capture.")
        return

    if not args.confirm:
        print("DRY RUN — pass --confirm to download\n")
        print_dry_run(submissions)
        return

    # ── confirm path ─────────────────────────────────────────────────────────
    r2 = get_r2()
    bucket = os.environ["R2_BUCKET_NAME"]
    existing = load_manifest()

    grand_total = 0
    captured = 0
    skipped = 0

    for doc in submissions:
        sid = doc["id"]
        artist = doc.get("artist_name", "?")
        track = doc.get("track_name", "?")

        if sid in existing:
            print(f"SKIP  {sid}  ({artist} — {track}, already in manifest)")
            skipped += 1
            continue

        print(f"\n→ {sid}  {artist} — {track}")
        entry, nbytes = download_submission(doc, r2, bucket)
        existing[sid] = entry
        save_manifest(existing)  # write after each success so partial runs are safe
        grand_total += nbytes
        captured += 1

    print(f"\n{'─' * 60}")
    print(f"Captured : {captured}")
    print(f"Skipped  : {skipped}  (already in manifest)")
    print(f"Total    : {grand_total:,} bytes  ({grand_total / 1_048_576:.1f} MB)")
    print(f"Manifest : {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
