#!/usr/bin/env python3
"""
Phase 3 benchmark — run Modal worker under _benchmark/ R2 prefix (never catalog/),
download new stems, compute objective metrics, write markdown report + A/B HTML.

Usage:
  python3 scripts/run_stem_benchmark.py            # run modal + compute + render
  python3 scripts/run_stem_benchmark.py --skip-modal  # regen report/HTML from local files

The benchmark prefix is _benchmark/{submission_id}/. The script refuses to run if the
resolved output key would start with catalog/ — enforced in code, not just intent.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT     = Path(__file__).resolve().parent.parent
BASELINE_DIR  = REPO_ROOT / "benchmark" / "lalal-baseline"
NEW_ENG_DIR   = REPO_ROOT / "benchmark" / "new-engine"
SPEC_DIR      = REPO_ROOT / "benchmark" / "spectrograms"
MANIFEST_PATH = BASELINE_DIR / "manifest.json"
REPORT_PATH   = REPO_ROOT / "docs" / "benchmark-stem-quality.md"
HTML_PATH     = REPO_ROOT / "benchmark" / "compare.html"
BACKEND_ENV   = REPO_ROOT / "backend" / ".env"

# ---------------------------------------------------------------------------
# Stem configuration
# ---------------------------------------------------------------------------

# Per PRD-01 §10.4: LALAL `other` is the full mix minus vocals — identical in
# intent to the new `instrumental` (RoFormer complement). Compare those two as
# the like-for-like pair; do NOT compare LALAL `other` against new `other_htdemucs`.
AB_PAIRS = [
    # (lalal_key,  new_key,        display_name,    source_note)
    ("vocals",    "vocals",        "Vocals",         "RoFormer"),
    ("drums",     "drums",         "Drums",          "htdemucs_ft"),
    ("bass",      "bass",          "Bass",           "htdemucs_ft"),
    ("other",     "instrumental",  "Instrumental",   "LALAL: full mix minus vocals = new instrumental (per PRD §10.4)"),
]
NEW_ONLY = [
    # (new_key,          display_name,               description)
    ("other_htdemucs",  "Other — htdemucs residual",
     "htdemucs_ft true residual after vocal/drums/bass removal. No LALAL counterpart."),
    ("other_subtract",  "Other — arithmetic subtract",
     "instrumental − drums − bass, sample-aligned subtraction. No LALAL counterpart."),
]

LALAL_KEYS   = [p[0] for p in AB_PAIRS]
NEW_ALL_KEYS = [p[1] for p in AB_PAIRS] + [n[0] for n in NEW_ONLY]
# = ["vocals","drums","bass","instrumental","other_htdemucs","other_subtract"]

MODAL_APP = "ovoxi-stem-worker"
MODAL_FN  = "separate_stems"
L4_RATE   = 0.000222

# ---------------------------------------------------------------------------
# Env / R2
# ---------------------------------------------------------------------------

def load_env() -> None:
    if not BACKEND_ENV.exists():
        sys.exit(f"ERROR: {BACKEND_ENV} not found")
    load_dotenv(BACKEND_ENV)
    for var in ("R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME"):
        if not os.environ.get(var):
            sys.exit(f"ERROR: {var} not set in {BACKEND_ENV}")


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
# Manifest — load and deduplicate
# ---------------------------------------------------------------------------

def _parse_slugs(mastered_r2_key: str) -> tuple[str, str]:
    """catalog/{artist_slug}/{track_slug}/mastered/... → (artist_slug, track_slug)"""
    parts = mastered_r2_key.split("/")
    return parts[1], parts[2]


def load_and_deduplicate() -> list[dict]:
    """
    Load manifest, skip entries with missing mastered, deduplicate on
    (artist_slug, track_slug) keeping the first (most recent) occurrence.
    Manifest is sorted upload_date DESCENDING by the capture script.
    Duplicate submissions (OQ-2) are skipped with a log line.
    """
    with open(MANIFEST_PATH) as fh:
        entries = json.load(fh)

    seen: set[tuple[str, str]] = set()
    result = []
    for e in entries:
        files   = e.get("files", {})
        mastered = files.get("mastered", {})
        sid   = e["submission_id"]
        label = f"{e['artist_name']} — {e['track_name']}"

        if mastered.get("error"):
            print(f"  SKIP  {sid[:8]}  {label}: mastered missing from R2")
            continue
        mkey = mastered.get("r2_key")
        if not mkey:
            print(f"  SKIP  {sid[:8]}  {label}: no mastered R2 key in manifest")
            continue

        artist_slug, track_slug = _parse_slugs(mkey)
        pair = (artist_slug, track_slug)
        if pair in seen:
            print(f"  SKIP  {sid[:8]}  {label}: duplicate of {artist_slug}/{track_slug} (OQ-2)")
            continue

        seen.add(pair)
        result.append({**e, "artist_slug": artist_slug, "track_slug": track_slug})

    return result

# ---------------------------------------------------------------------------
# R2 helpers
# ---------------------------------------------------------------------------

def _r2_key_exists(r2, bucket: str, key: str) -> bool:
    try:
        r2.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return False
        raise


def _benchmark_prefix(sid: str, artist_slug: str, track_slug: str) -> str:
    return f"_benchmark/{sid}/{artist_slug}/{track_slug}/stems"


def _r2_has_all_benchmark_stems(r2, bucket: str, sid: str, artist_slug: str, track_slug: str) -> bool:
    prefix = _benchmark_prefix(sid, artist_slug, track_slug)
    # NOTE 2026-08-27: stems are 24-bit WAV from stem_schema_version 3 onward.
    # These ".mp3" literals are stale and must be updated before this benchmark is
    # re-run against the current worker, or every existence check will miss.
    return all(_r2_key_exists(r2, bucket, f"{prefix}/{name}.mp3") for name in NEW_ALL_KEYS)


def download_new_stems(r2, bucket: str, sid: str, artist_slug: str, track_slug: str) -> None:
    prefix = _benchmark_prefix(sid, artist_slug, track_slug)
    dest   = NEW_ENG_DIR / sid
    dest.mkdir(parents=True, exist_ok=True)
    for name in NEW_ALL_KEYS:
        r2_key = f"{prefix}/{name}.mp3"
        local  = dest / f"{name}.mp3"
        data   = r2.get_object(Bucket=bucket, Key=r2_key)["Body"].read()
        local.write_bytes(data)
        print(f"    {name:<22} {len(data):>12,} bytes")

# ---------------------------------------------------------------------------
# Modal worker
# ---------------------------------------------------------------------------

def run_modal_worker(sid: str, mastered_r2_key: str, artist_slug: str, track_slug: str) -> dict:
    key_prefix  = f"_benchmark/{sid}"
    stem_prefix = f"{key_prefix}/{artist_slug}/{track_slug}/stems"

    # Hard refuse — never write to catalog/
    if stem_prefix.startswith("catalog/"):
        sys.exit(
            f"FATAL: benchmark would write to catalog/ — refusing.\n"
            f"  stem_prefix: {stem_prefix!r}\n"
            f"  Aborting without any R2 writes."
        )

    import modal
    fn = modal.Function.from_name(MODAL_APP, MODAL_FN)
    t0 = time.monotonic()
    payload = fn.remote(sid, mastered_r2_key, artist_slug, track_slug, key_prefix)
    elapsed = time.monotonic() - t0
    cost = elapsed * L4_RATE
    print(f"    Modal: {elapsed:.1f}s  ${cost:.4f}  ({cost / L4_RATE / 60:.1f} min)")
    return payload or {}

# ---------------------------------------------------------------------------
# Metrics — all via ffprobe / ffmpeg, no Python audio libs required locally
# ---------------------------------------------------------------------------

def ffprobe_sr(path: Path) -> int | None:
    """Return sample rate of first audio stream, or None on failure."""
    try:
        raw = subprocess.check_output(
            ["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=sample_rate", "-of", "json", str(path)],
            stderr=subprocess.DEVNULL,
        )
        return int(json.loads(raw)["streams"][0]["sample_rate"])
    except Exception:
        return None


def ffprobe_stats(path: Path) -> dict:
    """
    Compute: size, duration, sample_rate, channels, peak dBFS, RMS dBFS,
    LUFS-I, LRA, true peak dBTP. Returns {"error": ...} if file is missing.
    """
    if not path.exists():
        return {"error": "file_missing"}

    size = path.stat().st_size

    # Stream metadata (duration, sample_rate, channels, codec)
    duration = sample_rate = channels = codec = None
    try:
        raw = subprocess.check_output(
            ["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=duration,sample_rate,channels,codec_name",
             "-of", "json", str(path)],
            stderr=subprocess.DEVNULL,
        )
        s = json.loads(raw).get("streams", [{}])[0]
        if s.get("duration"):
            duration = float(s["duration"])
        if s.get("sample_rate"):
            sample_rate = int(s["sample_rate"])
        if s.get("channels"):
            channels = int(s["channels"])
        codec = s.get("codec_name")
    except Exception:
        pass

    # Volume + EBU R128 loudness in one ffmpeg pass.
    # peak=true enables the True Peak section in the ebur128 summary.
    peak = rms = lufs_i = lra = true_peak = None
    try:
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-i", str(path),
             "-af", "ebur128=framelog=verbose:peak=true,volumedetect",
             "-f", "null", "-"],
            capture_output=True, text=True, timeout=180,
        )
        err = r.stderr
        m = re.search(r"max_volume:\s+([\-\d\.]+)", err)
        if m: peak = float(m.group(1))
        m = re.search(r"mean_volume:\s+([\-\d\.]+)", err)
        if m: rms = float(m.group(1))
        m = re.search(r"\bI:\s+([\-\d\.]+)\s+LUFS", err)
        if m: lufs_i = float(m.group(1))
        m = re.search(r"\bLRA:\s+([\d\.]+)\s+LU\b", err)
        if m: lra = float(m.group(1))
        m = re.search(r"True peak:.*?Peak:\s+([\-\d\.]+)\s+dB", err, re.DOTALL)
        if m: true_peak = float(m.group(1))
    except Exception:
        pass

    return {
        "size_bytes":     size,
        "duration_s":     duration,
        "sample_rate":    sample_rate,
        "channels":       channels,
        "codec":          codec,
        "peak_dbfs":      peak,
        "rms_dbfs":       rms,
        "lufs_i":         lufs_i,
        "lra":            lra,
        "true_peak_dbtp": true_peak,
    }


def generate_spectrogram(src: Path, out: Path) -> bool:
    """
    Write a log-scale spectrogram PNG via ffmpeg showspectrumpic.
    Returns True on success, False on any failure (graceful fallback).
    """
    if not src.exists():
        return False
    try:
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-y", "-i", str(src),
             "-lavfi", "showspectrumpic=s=800x150:legend=0:scale=log:gain=3:color=channel",
             str(out)],
            check=True, capture_output=True, timeout=60,
        )
        return out.exists() and out.stat().st_size > 0
    except Exception:
        return False

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _mb(n: int | None) -> str:
    return f"{n / 1_048_576:.2f}" if n is not None else "—"

def _db(v: float | None) -> str:
    return f"{v:.1f}" if v is not None else "—"

def _dur(v: float | None) -> str:
    return f"{v:.1f}" if v is not None else "—"

# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

def write_markdown(tracks: list[dict]) -> None:
    lines = [
        "# Stem Quality Benchmark — LALAL vs New Engine",
        "",
        f"Generated: {date.today()}  |  Engine: MelBand RoFormer + htdemucs_ft via audio-separator 0.31.3",
        "",
        "## Methodology",
        "",
        "**What is measured:** file size (bytes), duration (s), peak amplitude (dBFS),",
        "mean amplitude / RMS (dBFS), integrated loudness (LUFS-I), loudness range (LRA),",
        "true peak (dBTP). All computed locally via `ffprobe` and `ffmpeg -af volumedetect,ebur128`.",
        "",
        "**What is NOT measured, and not claimed:** signal-to-noise ratio or SDR",
        "(requires a reference separation), MOS or any perceptual quality score (requires",
        "ears, not code), spectral centroid or frequency-domain features (requires local",
        "numpy/librosa, which are not assumed here). The A/B listening session at",
        "`benchmark/compare.html` is the authoritative quality gate for this phase.",
        "",
        "**Stem mapping (per PRD-01 §10.4):** LALAL `other` is the full mix minus vocals",
        "— this is identical in intent to the new `instrumental` (RoFormer complement).",
        "These two are the like-for-like comparison pair. The new `other_htdemucs` is the",
        "htdemucs_ft true residual (guitars, keys, pads) and has no LALAL counterpart.",
        "",
        "**File format note:** LALAL stored stems in R2 as `pcm_s24le` WAV (24-bit, ~30–40 MB per track)",
        "despite the `.mp3` key suffix. New stems are CBR 320 kbps MP3 (~5–8 MB). File size is",
        "therefore not a direct quality comparison — it reflects format difference, not content.",
        "The `Format` column makes this explicit per row.",
        "",
        "**Source sample rate:** htdemucs_ft resamples all input to 44100 Hz internally.",
        "If a source was recorded or mastered at 48 kHz, the new stems will be at 44100 Hz",
        "regardless. This can cause a perceived high-frequency roll-off compared to a",
        "44100 Hz LALAL output. The per-track SR is noted below so this factor is",
        "distinguishable from model quality differences during A/B.",
        "",
        "---",
        "",
    ]

    for t in tracks:
        sid    = t["submission_id"]
        src_sr = t["src_sr"]

        if src_sr == 44100:
            sr_note = "_(no htdemucs internal resampling)_"
        elif src_sr:
            sr_note = (
                f"⚠️ **{src_sr} Hz input** — htdemucs resamples to 44100 Hz internally. "
                "If new stems sound duller than LALAL, check this first."
            )
        else:
            sr_note = "_(could not determine)_"

        lines += [
            f"## {t['artist_name']} — {t['track_name']}",
            "",
            f"**Submission:** `{sid}`  ",
            f"**Slugs:** `{t['artist_slug']} / {t['track_slug']}`  ",
            f"**Source sample rate:** {src_sr or '?'} Hz {sr_note}",
            "",
            "### Comparable stems",
            "",
            "| Stem | Engine | Format | Size (MB) | Duration (s) | Peak (dBFS) | RMS (dBFS) | LUFS-I | LRA (LU) | True Peak (dBTP) |",
            "|------|--------|--------|----------:|-------------:|------------:|-----------:|-------:|---------:|-----------------:|",
        ]

        for lalal_key, new_key, display, _ in AB_PAIRS:
            ls = t["lalal_stats"].get(lalal_key, {})
            ns = t["new_stats"].get(new_key, {})
            for engine, s in (("LALAL", ls), ("New", ns)):
                if s.get("error"):
                    lines.append(f"| {display} | {engine} | | _({s['error']})_ | | | | | | |")
                else:
                    lines.append(
                        f"| {display} | {engine}"
                        f" | {s.get('codec') or '—'}"
                        f" | {_mb(s.get('size_bytes'))}"
                        f" | {_dur(s.get('duration_s'))}"
                        f" | {_db(s.get('peak_dbfs'))}"
                        f" | {_db(s.get('rms_dbfs'))}"
                        f" | {_db(s.get('lufs_i'))}"
                        f" | {_db(s.get('lra'))}"
                        f" | {_db(s.get('true_peak_dbtp'))}"
                        f" |"
                    )

        lines += [
            "",
            "### New-only stems (no LALAL counterpart)",
            "",
            "| Stem | Format | Size (MB) | Duration (s) | Peak (dBFS) | RMS (dBFS) | LUFS-I | LRA (LU) | True Peak (dBTP) |",
            "|------|--------|----------:|-------------:|------------:|-----------:|-------:|---------:|-----------------:|",
        ]

        for new_key, display, _ in NEW_ONLY:
            ns = t["new_stats"].get(new_key, {})
            if ns.get("error"):
                lines.append(f"| {display} | | _({ns['error']})_ | | | | | | |")
            else:
                lines.append(
                    f"| {display}"
                    f" | {ns.get('codec') or '—'}"
                    f" | {_mb(ns.get('size_bytes'))}"
                    f" | {_dur(ns.get('duration_s'))}"
                    f" | {_db(ns.get('peak_dbfs'))}"
                    f" | {_db(ns.get('rms_dbfs'))}"
                    f" | {_db(ns.get('lufs_i'))}"
                    f" | {_db(ns.get('lra'))}"
                    f" | {_db(ns.get('true_peak_dbtp'))}"
                    f" |"
                )

        lines += ["", "---", ""]

    REPORT_PATH.write_text("\n".join(lines))

# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    background: #0d0d0d; color: #d1d5db;
    font-family: ui-monospace, "Cascadia Code", monospace;
    font-size: 13px; padding: 1.5rem;
}
h1 { color: #f9fafb; font-size: 1.1rem; border-bottom: 1px solid #1f2937; padding-bottom: .5rem; margin-bottom: .25rem; }
.meta { color: #4b5563; font-size: .75rem; margin-bottom: 2rem; }
.track { border: 1px solid #1f2937; border-radius: 6px; margin: 1.5rem 0; padding: 1rem 1.25rem; }
h2 { color: #60a5fa; font-size: .95rem; margin-bottom: .2rem; }
.track-meta { color: #4b5563; font-size: .7rem; margin-bottom: 1rem; }
.sr-warn { color: #fb923c; font-size: .75rem; padding: .35rem .5rem; background: #1c1008; border-radius: 3px; margin-bottom: .75rem; }
h3 { color: #9ca3af; font-size: .75rem; font-weight: 600; text-transform: uppercase; letter-spacing: .06em; margin: 1rem 0 .25rem; }
.stem-note { color: #92400e; font-size: .7rem; font-style: italic; margin-bottom: .5rem; }
.ab { display: grid; grid-template-columns: 1fr 1fr; gap: .75rem; }
.side { background: #111827; border-radius: 4px; padding: .65rem .75rem; }
.side.new-only { grid-column: span 2; background: #0a1a0a; }
.side-label { font-size: .65rem; text-transform: uppercase; letter-spacing: .08em; margin-bottom: .3rem; }
.lalal-label { color: #d97706; }
.new-label   { color: #34d399; }
audio { width: 100%; height: 28px; display: block; margin: .2rem 0; accent-color: #60a5fa; }
.stats { font-size: .65rem; color: #6b7280; margin-top: .2rem; line-height: 1.6; }
.stats b { color: #9ca3af; }
.spec-row { display: grid; grid-template-columns: 1fr 1fr; gap: .5rem; margin-top: .4rem; }
.spec-single { margin-top: .4rem; }
img.spec { width: 100%; height: auto; border-radius: 2px; display: block; }
"""


def _stats_html(s: dict) -> str:
    if s.get("error"):
        return f'<div class="stats">⚠ {s["error"]}</div>'
    codec_str = s.get("codec") or "—"
    parts = [
        f'<b>fmt</b> {codec_str}',
        f'<b>size</b> {_mb(s.get("size_bytes"))} MB',
        f'<b>dur</b> {_dur(s.get("duration_s"))} s',
        f'<b>peak</b> {_db(s.get("peak_dbfs"))} dBFS',
        f'<b>RMS</b> {_db(s.get("rms_dbfs"))} dBFS',
        f'<b>LUFS-I</b> {_db(s.get("lufs_i"))}',
        f'<b>TP</b> {_db(s.get("true_peak_dbtp"))} dBTP',
    ]
    return '<div class="stats">' + " &thinsp;|&thinsp; ".join(parts) + "</div>"


def _img(rel: str | None) -> str:
    if not rel:
        return ""
    return f'<img class="spec" src="{rel}" alt="spectrogram" loading="lazy">'


def write_html(tracks: list[dict]) -> None:
    sections = []
    for t in tracks:
        sid    = t["submission_id"]
        src_sr = t["src_sr"]
        sr_str = f"{src_sr} Hz" if src_sr else "unknown SR"

        sr_warn_html = ""
        if src_sr and src_sr != 44100:
            sr_warn_html = (
                f'<div class="sr-warn">⚠ Source is {src_sr} Hz. '
                f'htdemucs resamples to 44100 Hz internally — if new stems sound duller '
                f'than LALAL this is the likely cause, not the model.</div>'
            )

        html = [
            f'<div class="track">',
            f'<h2>{t["artist_name"]} — {t["track_name"]}</h2>',
            f'<div class="track-meta">{sid[:8]} &nbsp;·&nbsp; {t["artist_slug"]}/{t["track_slug"]} &nbsp;·&nbsp; {sr_str}</div>',
            sr_warn_html,
        ]

        for lalal_key, new_key, display, note in AB_PAIRS:
            ls = t["lalal_stats"].get(lalal_key, {})
            ns = t["new_stats"].get(new_key, {})
            lalal_src = f"lalal-baseline/{sid}/{lalal_key}.mp3"
            new_src   = f"new-engine/{sid}/{new_key}.mp3"
            lspec = t["lalal_specs"].get(lalal_key)
            nspec = t["new_specs"].get(new_key)

            html += [
                f'<h3>{display}</h3>',
                f'<div class="stem-note">{note}</div>',
                f'<div class="ab">',
                f'  <div class="side">',
                f'    <div class="side-label lalal-label">LALAL baseline</div>',
                f'    <audio controls src="{lalal_src}"></audio>',
                _stats_html(ls),
                f'  </div>',
                f'  <div class="side">',
                f'    <div class="side-label new-label">New engine</div>',
                f'    <audio controls src="{new_src}"></audio>',
                _stats_html(ns),
                f'  </div>',
                f'</div>',
            ]
            if lspec or nspec:
                html += [
                    f'<div class="spec-row">',
                    f'  {_img(lspec)}',
                    f'  {_img(nspec)}',
                    f'</div>',
                ]

        for new_key, display, description in NEW_ONLY:
            ns = t["new_stats"].get(new_key, {})
            new_src = f"new-engine/{sid}/{new_key}.mp3"
            nspec   = t["new_specs"].get(new_key)

            html += [
                f'<h3>{display} <span style="color:#374151;font-weight:normal">(new only)</span></h3>',
                f'<div class="stem-note">{description}</div>',
                f'<div class="ab">',
                f'  <div class="side new-only">',
                f'    <div class="side-label new-label">New engine (no LALAL counterpart)</div>',
                f'    <audio controls src="{new_src}"></audio>',
                _stats_html(ns),
                f'  </div>',
                f'</div>',
            ]
            if nspec:
                html.append(f'<div class="spec-single">{_img(nspec)}</div>')

        html.append("</div>")
        sections.append("\n".join(html))

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stem A/B — LALAL vs New Engine</title>
<style>
{_CSS}
</style>
</head>
<body>
<h1>Stem A/B — LALAL vs New Engine</h1>
<p class="meta">Generated {date.today()} &nbsp;·&nbsp; Gate: do not proceed to /04-stem-wire until A/B listening is complete.</p>
{"".join(sections)}
</body>
</html>"""

    HTML_PATH.write_text(page)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 3 stem benchmark")
    parser.add_argument(
        "--skip-modal", action="store_true",
        help="Skip Modal runs; regen report and HTML from already-downloaded local stems",
    )
    parser.add_argument(
        "--force", action="store_true",
        help=(
            "Bypass local-file and R2 existence checks; force a fresh Modal run "
            "for every track. Use when prior stems are known-bad. "
            "Does NOT delete R2 keys — Modal overwrites them."
        ),
    )
    args = parser.parse_args()

    load_env()
    r2     = get_r2()
    bucket = os.environ["R2_BUCKET_NAME"]

    print("Loading manifest and deduplicating by (artist_slug, track_slug)...")
    tracks_meta = load_and_deduplicate()
    print(f"{len(tracks_meta)} unique tracks selected\n")

    track_data = []

    for entry in tracks_meta:
        sid         = entry["submission_id"]
        artist_slug = entry["artist_slug"]
        track_slug  = entry["track_slug"]
        mastered_r2 = entry["files"]["mastered"]["r2_key"]
        label       = f"{entry['artist_name']} — {entry['track_name']}"

        print(f"→ {label}  ({sid[:8]})")

        local_dest = NEW_ENG_DIR / sid
        all_local  = all((local_dest / f"{name}.mp3").exists() for name in NEW_ALL_KEYS)

        if all_local and not args.force:
            print("  New stems: already local — skipping Modal/R2")
        elif args.skip_modal:
            print("  --skip-modal: missing local stems, will report what exists")
        else:
            if not args.force and _r2_has_all_benchmark_stems(r2, bucket, sid, artist_slug, track_slug):
                print("  New stems: found in R2 from prior run — downloading")
            else:
                if args.force:
                    print("  --force: bypassing cache — running Modal worker...")
                else:
                    print("  New stems: running Modal worker...")
                modal_payload   = run_modal_worker(sid, mastered_r2, artist_slug, track_slug)
                src_sr_modal    = modal_payload.get("source_sample_rate")
                stem_paths_r2   = modal_payload.get("stem_paths", {})
                sr_flag = " ⚠ 48 kHz — htdemucs resamples internally" if src_sr_modal == 48000 else ""
                print(f"    source_sample_rate: {src_sr_modal} Hz{sr_flag}")
                for sname, skey in stem_paths_r2.items():
                    print(f"    stem_paths[{sname}]: {skey}")
                print("  Downloading from R2...")
            download_new_stems(r2, bucket, sid, artist_slug, track_slug)
            # Report sha256 of downloaded vocals and instrumental for item 9
            import hashlib as _hl
            def _local_sha256(p: Path) -> str:
                h = _hl.sha256()
                with open(p, "rb") as _f:
                    for _chunk in iter(lambda: _f.read(65536), b""):
                        h.update(_chunk)
                return h.hexdigest()
            v_path = local_dest / "vocals.mp3"
            i_path = local_dest / "instrumental.mp3"
            if v_path.exists() and i_path.exists():
                print(f"    sha256 vocals.mp3:       {_local_sha256(v_path)}")
                print(f"    sha256 instrumental.mp3: {_local_sha256(i_path)}")

        # Source sample rate — probe the local mastered MP3
        mastered_local = REPO_ROOT / entry["files"]["mastered"]["local_path"]
        src_sr = ffprobe_sr(mastered_local) if mastered_local.exists() else None

        # Compute metrics
        print("  Computing metrics...")
        lalal_stats: dict[str, dict] = {}
        for key in LALAL_KEYS:
            f = entry.get("files", {}).get(key, {})
            if f.get("error"):
                lalal_stats[key] = {"error": f["error"]}
            elif f.get("local_path"):
                lalal_stats[key] = ffprobe_stats(REPO_ROOT / f["local_path"])
            else:
                lalal_stats[key] = {"error": "no_local_path"}

        new_stats: dict[str, dict] = {}
        for key in NEW_ALL_KEYS:
            new_stats[key] = ffprobe_stats(local_dest / f"{key}.mp3")

        # Spectrograms (graceful failure per-stem)
        print("  Generating spectrograms...")
        spec_dir = SPEC_DIR / sid
        spec_dir.mkdir(parents=True, exist_ok=True)

        lalal_specs: dict[str, str | None] = {}
        for key in LALAL_KEYS:
            f = entry.get("files", {}).get(key, {})
            if not f.get("error") and f.get("local_path"):
                src = REPO_ROOT / f["local_path"]
                out = spec_dir / f"lalal_{key}.png"
                ok  = generate_spectrogram(src, out)
                lalal_specs[key] = str(out.relative_to(REPO_ROOT / "benchmark")) if ok else None
            else:
                lalal_specs[key] = None

        new_specs: dict[str, str | None] = {}
        for key in NEW_ALL_KEYS:
            src = local_dest / f"{key}.mp3"
            out = spec_dir / f"new_{key}.png"
            ok  = generate_spectrogram(src, out) if src.exists() else False
            new_specs[key] = str(out.relative_to(REPO_ROOT / "benchmark")) if ok else None

        track_data.append({
            "submission_id": sid,
            "artist_name":   entry["artist_name"],
            "track_name":    entry["track_name"],
            "artist_slug":   artist_slug,
            "track_slug":    track_slug,
            "src_sr":        src_sr,
            "lalal_stats":   lalal_stats,
            "new_stats":     new_stats,
            "lalal_specs":   lalal_specs,
            "new_specs":     new_specs,
        })
        print()

    print("Writing report and HTML...")
    write_markdown(track_data)
    write_html(track_data)

    print(f"\nDone.")
    print(f"  Report : {REPORT_PATH.relative_to(REPO_ROOT)}")
    print(f"  HTML   : {HTML_PATH.relative_to(REPO_ROOT)}")
    print(f"\n  open benchmark/compare.html in a browser to A/B listen.")
    print(f"  Do not proceed to /04 until the A/B is complete.")


if __name__ == "__main__":
    main()
