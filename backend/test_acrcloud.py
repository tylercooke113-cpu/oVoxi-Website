"""
Standalone ACRCloud response-shape probe — throwaway, not part of the app.

Usage:
    python test_acrcloud.py <match_file> [nomatch_file]

    match_file   — path to a short commercial track clip (mp3/wav/flac)
    nomatch_file — path to silence, noise, or an obscure original recording
                   (defaults to reference/default.wav if omitted)

Requires backend/.env with:
    ACRCLOUD_HOST
    ACRCLOUD_ACCESS_KEY
    ACRCLOUD_ACCESS_SECRET

Prints raw JSON from both calls — no parsing, just response shape.
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

try:
    from acrcloud.recognizer import ACRCloudRecognizer
except ImportError:
    sys.exit("pyacrcloud not installed — run: pip install pyacrcloud")

HOST = os.environ.get("ACRCLOUD_HOST")
KEY = os.environ.get("ACRCLOUD_ACCESS_KEY")
SECRET = os.environ.get("ACRCLOUD_ACCESS_SECRET")

if not all([HOST, KEY, SECRET]):
    sys.exit(
        "Missing env vars. Ensure backend/.env contains:\n"
        "  ACRCLOUD_HOST\n  ACRCLOUD_ACCESS_KEY\n  ACRCLOUD_ACCESS_SECRET"
    )

config = {
    "host": HOST,
    "access_key": KEY,
    "access_secret": SECRET,
    "timeout": 15,
}

recognizer = ACRCloudRecognizer(config)

match_file = sys.argv[1] if len(sys.argv) > 1 else None
nomatch_file = (
    sys.argv[2] if len(sys.argv) > 2
    else str(Path(__file__).parent / "reference" / "default.wav")
)

if not match_file:
    sys.exit("Provide a match_file path as the first argument.")

if not Path(match_file).exists():
    sys.exit(f"match_file not found: {match_file}")

if not Path(nomatch_file).exists():
    sys.exit(f"nomatch_file not found: {nomatch_file}")


def probe(label: str, file_path: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"  file: {file_path}")
    print(f"{'='*60}")
    # start_seconds=0, rec_length=15 — read 15 s from the top of the file
    raw = recognizer.recognize_by_file(file_path, 0, 15)
    # raw is a JSON string from pyacrcloud
    try:
        parsed = json.loads(raw)
        print(json.dumps(parsed, indent=2))
    except (json.JSONDecodeError, TypeError):
        print(raw)


probe("MATCH CASE", match_file)
probe("NO-MATCH CASE", nomatch_file)
