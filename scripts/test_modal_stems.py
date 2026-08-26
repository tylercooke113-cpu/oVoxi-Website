#!/usr/bin/env python3
"""
Phase 1 gate test — invoke separate_stems on one track, print wall-clock and cost.

Usage:
  python3 scripts/test_modal_stems.py \\
      --r2-key  catalog/artist/track/mastered/submission_id.mp3 \\
      --artist  artist_slug \\
      --track   track_slug

Or pick a random completed track from the baseline manifest:
  python3 scripts/test_modal_stems.py --from-manifest [--index N]

Requires:
  - modal deployed: run `modal deploy infra/modal/stem_worker.py` first
  - ovoxi-stem-secrets updated with real R2 creds + callback URL
"""

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "benchmark" / "lalal-baseline" / "manifest.json"

# L4 GPU rate from Modal pricing / PRD §2. Update if pricing changes.
L4_RATE_PER_SEC = 0.000222  # $/sec


def pick_from_manifest(index: int) -> tuple[str, str, str]:
    """Return (mastered_r2_key, artist_slug, track_slug) from baseline manifest."""
    if not MANIFEST_PATH.exists():
        sys.exit(f"ERROR: {MANIFEST_PATH} not found — run /01 baseline capture first")
    with open(MANIFEST_PATH) as fh:
        entries = json.load(fh)

    complete = [e for e in entries if e.get("complete") and
                e.get("files", {}).get("mastered", {}).get("r2_key")]
    if not complete:
        sys.exit("ERROR: no complete entries with a mastered key in the manifest")

    entry = complete[index % len(complete)]
    mastered_r2_key = entry["files"]["mastered"]["r2_key"]

    # Derive slugs from the R2 key: catalog/{artist_slug}/{track_slug}/mastered/...
    parts = mastered_r2_key.split("/")
    artist_slug = parts[1]
    track_slug  = parts[2]

    print(f"Using manifest entry: {entry['artist_name']} — {entry['track_name']}")
    print(f"  submission_id : {entry['submission_id']}")
    print(f"  mastered key  : {mastered_r2_key}")
    return mastered_r2_key, artist_slug, track_slug


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 1 gate test for the Modal stem worker."
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--r2-key",  help="Mastered R2 key to separate")
    src.add_argument("--from-manifest", action="store_true",
                     help="Pick a track from benchmark/lalal-baseline/manifest.json")
    parser.add_argument("--artist",  help="Artist slug (required with --r2-key)")
    parser.add_argument("--track",   help="Track slug (required with --r2-key)")
    parser.add_argument("--index", type=int, default=0,
                        help="Manifest entry index (default 0, wraps around)")
    args = parser.parse_args()

    if args.from_manifest:
        mastered_r2_key, artist_slug, track_slug = pick_from_manifest(args.index)
    else:
        if not args.artist or not args.track:
            parser.error("--artist and --track are required with --r2-key")
        mastered_r2_key = args.r2_key
        artist_slug     = args.artist
        track_slug      = args.track

    # Use a test submission ID so the callback lands somewhere identifiable
    submission_id = f"test-{int(time.time())}"
    print(f"\nSubmission ID  : {submission_id}")
    print(f"Artist slug    : {artist_slug}")
    print(f"Track slug     : {track_slug}")
    print(f"Mastered key   : {mastered_r2_key}")
    print()

    # Look up the deployed function by name — Function.lookup is deprecated
    # in modal 1.x; from_name is the current API.
    import modal
    fn = modal.Function.from_name("ovoxi-stem-worker", "separate_stems")

    print("Invoking separate_stems.remote() — this blocks until Modal finishes …\n")
    t0 = time.monotonic()
    result = None
    error  = None
    try:
        result = fn.remote(submission_id, mastered_r2_key, artist_slug, track_slug)
    except Exception as exc:
        error = str(exc)

    elapsed = time.monotonic() - t0

    if error:
        # Print the separator and error without fake cost/timing numbers from a
        # call that may have thrown before any GPU work ran.
        print("─" * 60)
        print(f"FAILED after {elapsed:.1f}s")
        print(f"  {error}")
        sys.exit(1)

    _print_stats(elapsed, result=result)


def _print_stats(elapsed: float, result: dict) -> None:
    cost = elapsed * L4_RATE_PER_SEC
    print("─" * 60)
    print(f"Wall-clock      : {elapsed:.1f} s  ({elapsed / 60:.1f} min)")
    print(f"Estimated cost  : ${cost:.4f}  ({elapsed:.0f}s × ${L4_RATE_PER_SEC}/s L4)")
    print()
    print(f"Status          : {result.get('status')}")
    print(f"Schema version  : {result.get('stem_schema_version')}")
    print(f"Source SR       : {result.get('source_sample_rate')} Hz")
    flac_delta = result.get("storage_delta_flac_bytes", 0)
    print(f"FLAC delta      : +{flac_delta / 1_048_576:.1f} MB per track "
          f"({flac_delta / 1_048_576 * 1000 / 1_048_576:.2f} GB / 1000 tracks)")
    print()
    print("Stem paths (MP3):")
    for k, v in sorted(result.get("stem_paths", {}).items()):
        print(f"  {k:<18} {v}")
    print()
    print("Gate check:")
    gate_ok = cost <= 0.10 and elapsed <= 300
    print(f"  cost ≤ $0.10  : {'PASS' if cost <= 0.10 else 'FAIL'} (${cost:.4f})")
    print(f"  time ≤ 5 min  : {'PASS' if elapsed <= 300 else 'FAIL'} ({elapsed:.0f}s)")
    print(f"  Overall       : {'PASS — proceed to /03 A/B' if gate_ok else 'FAIL — stop and re-plan'}")


if __name__ == "__main__":
    main()
