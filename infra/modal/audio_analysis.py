"""Preview, waveform, BPM and key for the sync library.

See docs/PRD-03 sections 4.4 and 6.3, decision 9. Pure functions: a file in,
values or local files out. No R2, no network, no GPU. Runs inside the Modal
stem worker after separation and is testable on a normal CPU.

Licenses: librosa is ISC (tempo estimate). The key profiles are the published
Krumhansl-Kessler probe-tone ratings; the matching code is ours.
"""
import json
import logging
import subprocess
from pathlib import Path
from typing import Optional

import numpy as np

log = logging.getLogger("audio_analysis")

PREVIEW_BITRATE = "320k"
WAVEFORM_POINTS = 800
WAVEFORM_VERSION = 1
ANALYSIS_SR = 22050

PITCHES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def make_preview(src: Path, dst: Path) -> None:
    """320 kbps MP3 playback derivative. Never licensed or delivered (PRD-03 6.3)."""
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-vn", "-map_metadata", "-1",
         "-codec:a", "libmp3lame", "-b:a", PREVIEW_BITRATE, str(dst)],
        check=True, capture_output=True,
    )


def load_mono(src: Path, sr: int = ANALYSIS_SR) -> np.ndarray:
    import librosa
    y, _ = librosa.load(str(src), sr=sr, mono=True)
    return y


def waveform_peaks(y: np.ndarray, points: int = WAVEFORM_POINTS) -> list:
    """Peak absolute amplitude per bucket, scaled so the loudest bucket is 1.0."""
    if y.size == 0:
        return [0.0] * points
    buckets = np.array_split(np.abs(y), points)
    peaks = np.array([b.max() if b.size else 0.0 for b in buckets])
    top = peaks.max()
    if top <= 0:
        return [0.0] * points
    return [round(float(p), 3) for p in peaks / top]


def write_waveform(peaks: list, dst: Path) -> None:
    dst.write_text(json.dumps(
        {"version": WAVEFORM_VERSION, "points": len(peaks), "peaks": peaks},
        separators=(",", ":"),
    ))


def detect_bpm(y: np.ndarray, sr: int = ANALYSIS_SR) -> Optional[float]:
    import librosa
    if y.size == 0 or not np.any(y):
        return None
    # librosa.feature.tempo, not beat.beat_track: in librosa 0.10.1 beat_track
    # calls scipy.signal.hann, which scipy >= 1.13 removed. The tempo estimate
    # is the same one beat_track uses internally.
    tempo = librosa.feature.tempo(y=y, sr=sr)
    bpm = float(np.atleast_1d(tempo)[0])
    if not np.isfinite(bpm) or bpm <= 0:
        return None
    return round(bpm, 1)


def detect_key(y: np.ndarray, sr: int = ANALYSIS_SR) -> Optional[str]:
    """Krumhansl-Schmuckler: correlate the average chroma with all 24 rotated
    key profiles and take the best. Returns e.g. "A minor"."""
    import librosa
    if y.size == 0 or not np.any(y):
        return None
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    profile = chroma.mean(axis=1)
    if not np.any(profile) or np.allclose(profile, profile[0]):
        return None
    best, best_score = None, -np.inf
    for tonic in range(12):
        for mode, ref in (("major", MAJOR_PROFILE), ("minor", MINOR_PROFILE)):
            score = np.corrcoef(profile, np.roll(ref, tonic))[0, 1]
            if score > best_score:
                best, best_score = f"{PITCHES[tonic]} {mode}", score
    return best


def analyze(mastered: Path, workdir: Path) -> dict:
    """Run every step independently. A failed step leaves its result as None
    and is listed in `errors`; it never raises."""
    out = {"preview_path": None, "waveform_path": None, "bpm": None, "key": None, "errors": []}

    try:
        preview = workdir / "preview.mp3"
        make_preview(mastered, preview)
        out["preview_path"] = preview
    except Exception as exc:
        out["errors"].append(f"preview: {exc}")

    try:
        y = load_mono(mastered)
    except Exception as exc:
        out["errors"].append(f"load: {exc}")
        return out

    for name, step in (
        ("waveform", lambda: _waveform_step(y, workdir)),
        ("bpm", lambda: detect_bpm(y)),
        ("key", lambda: detect_key(y)),
    ):
        try:
            result = step()
            if name == "waveform":
                out["waveform_path"] = result
            else:
                out[name] = result
        except Exception as exc:
            out["errors"].append(f"{name}: {exc}")
    return out


def _waveform_step(y: np.ndarray, workdir: Path) -> Path:
    path = workdir / "waveform.json"
    write_waveform(waveform_peaks(y), path)
    return path
