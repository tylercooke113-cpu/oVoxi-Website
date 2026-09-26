#!/usr/bin/env python3
"""
List (and optionally delete) R2 objects for submissions marked
status=failed / error=abandoned_upload by the sweeper.

The sweeper logs the orphaned key and marks the document failed; it never
deletes from R2. Run this script manually after reviewing the output.

Usage:
    python scripts/cleanup_orphaned_r2.py          # dry run, prints what would be deleted
    python scripts/cleanup_orphaned_r2.py --apply  # deletes from R2
"""
import argparse
import os
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).parent.parent / "backend" / ".env")


def main(apply: bool) -> None:
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    r2 = boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )
    bucket = os.environ["R2_BUCKET_NAME"]

    docs = list(db.track_submissions.find(
        {"status": "failed", "error": "abandoned_upload"},
        {"_id": 0, "id": 1, "original_r2_path": 1},
    ))

    if not docs:
        print("No abandoned uploads found.")
        return

    print(f"Found {len(docs)} abandoned upload(s). Mode: {'APPLY' if apply else 'DRY-RUN'}\n")

    for doc in docs:
        key = doc.get("original_r2_path", "")
        if not key:
            print(f"  SKIP     {doc['id']} — no r2 key recorded")
            continue

        try:
            r2.head_object(Bucket=bucket, Key=key)
            exists = True
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code in ("404", "NoSuchKey", "NotFound"):
                exists = False
            else:
                # Permissions error, network error, etc. — do not treat as missing.
                raise

        label = "DELETE" if apply else "DRY-RUN"
        print(f"  {label}  {doc['id']}  {key}  exists={exists}")

        if apply and exists:
            r2.delete_object(Bucket=bucket, Key=key)
            print(f"           deleted.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean up orphaned R2 objects from abandoned uploads.")
    parser.add_argument("--apply", action="store_true", help="Actually delete from R2 (default is dry run)")
    main(parser.parse_args().apply)
