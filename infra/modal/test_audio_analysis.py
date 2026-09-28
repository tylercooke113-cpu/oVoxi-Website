"""
Tests for infra/modal/audio_analysis.py on generated test tones (CPU only).

Needs librosa==0.10.1 (the worker's pin), soundfile and ffmpeg locally:
    pip install librosa==0.10.1
    pytest infra/modal/test_audio_analysis.py
"""
import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

import audio_analysis as aa

SR = 44100


def tone(freqs, seconds, sr=SR, amp=0.2):
    t = np.arange(int(seconds * sr)) / sr
    return sum(amp * np.sin(2 * np.pi * f * t) for f in freqs)


def click_track(bpm, seconds, sr=SR):
    y = np.zeros(int(seconds * sr))
    step = int(sr * 60 / bpm)
    click = np.hanning(400) * np.sin(2 * np.pi * 1000 * np.arange(400) / sr)
    for start in range(0, len(y) - 400, step):
        y[start:start + 400] += click
    return y


def drum_loop(bpm, seconds, sr=SR):
    """Kick on 1 and 3, noise snare on 2 and 4, eighth-note hats."""
    rng = np.random.default_rng(0)
    y = np.zeros(int(seconds * sr))
    beat = sr * 60 / bpm
    kick = np.exp(-np.arange(4000) / 600) * np.sin(2 * np.pi * 55 * np.arange(4000) / sr)
    snare = np.exp(-np.arange(3000) / 400) * rng.standard_normal(3000) * 0.5
    hat = np.exp(-np.arange(800) / 100) * rng.standard_normal(800) * 0.2
    n = 0
    while int((n + 1) * beat) + 4000 < len(y):
        s = int(n * beat)
        hit = kick if n % 2 == 0 else snare
        y[s:s + len(hit)] += hit
        for half in (0, 0.5):
            h = int(s + half * beat)
            y[h:h + 800] += hat
        n += 1
    return y


def midi(n, cents=0):
    return 440.0 * 2 ** ((n - 69) / 12 + cents / 1200)


def progression(chords, seconds_each=2.0, repeats=3, cents=0):
    return np.concatenate([tone([midi(n, cents) for n in c], seconds_each)
                           for _ in range(repeats) for c in chords])


C_MAJOR = [(60, 64, 67), (65, 69, 72), (67, 71, 74), (60, 64, 67)]
A_MINOR = [(57, 60, 64), (62, 65, 69), (64, 67, 71), (57, 60, 64)]
D_MINOR = [(62, 65, 69), (67, 70, 74), (69, 72, 76), (62, 65, 69)]
D_MAJOR = [(62, 66, 69), (67, 71, 74), (69, 73, 76), (62, 66, 69)]


@pytest.fixture
def wav(tmp_path):
    def _write(y, name="in.wav"):
        path = tmp_path / name
        sf.write(path, y, SR, subtype="PCM_24")
        return path
    return _write


@pytest.mark.parametrize("bpm", [75, 87, 90, 120, 128, 130, 140])
def test_bpm_click_track_exact_whole_number(wav, bpm):
    # Regression: the coarse estimator could only return tempo "rungs"
    # (89.1 for 90, 129.2 for 130). Refined and snapped, it must be exact.
    y = aa.load_mono(wav(click_track(bpm, 40)))
    assert aa.detect_bpm(y) == float(bpm)


def test_bpm_fractional_tempo_kept(wav):
    y = aa.load_mono(wav(click_track(93.5, 40)))
    assert aa.detect_bpm(y) == 93.5


@pytest.mark.parametrize("bpm", [90, 97, 128, 130])
def test_bpm_drum_loop_exact(wav, bpm):
    y = aa.load_mono(wav(drum_loop(bpm, 40)))
    assert aa.detect_bpm(y) == float(bpm)


@pytest.mark.parametrize("chords, expected", [
    (C_MAJOR, "C major"), (A_MINOR, "A minor"), (D_MINOR, "D minor"), (D_MAJOR, "D major"),
])
@pytest.mark.parametrize("cents", [0, 35])
def test_key_progressions_including_detuned(wav, chords, expected, cents):
    # I-IV-V-I / i-iv-v-i. 35 cents sharp checks the tuning correction.
    key, confidence = aa.detect_key_with_confidence(aa.load_mono(wav(progression(chords, cents=cents))))
    assert key == expected
    assert confidence > 0


def test_silence_gives_none(wav):
    y = aa.load_mono(wav(np.zeros(SR * 5)))
    assert aa.detect_bpm(y) is None
    assert aa.detect_key(y) is None
    assert aa.waveform_peaks(y) == [0.0] * aa.WAVEFORM_POINTS


def test_waveform_shape_and_scale():
    y = np.concatenate([np.full(1000, 0.1), np.full(1000, 0.5)])
    peaks = aa.waveform_peaks(y, points=10)
    assert len(peaks) == 10
    assert max(peaks) == 1.0
    assert peaks[0] == pytest.approx(0.2)


def test_analyze_end_to_end(wav, tmp_path):
    src = wav(progression(C_MAJOR))
    out = aa.analyze(src, tmp_path)
    assert out["errors"] == []
    assert out["preview_path"].exists()
    data = json.loads(out["waveform_path"].read_text())
    assert data["version"] == 1 and data["points"] == aa.WAVEFORM_POINTS
    assert len(data["peaks"]) == aa.WAVEFORM_POINTS
    assert out["key"] == "C major"
    assert out["key_confidence"] > 0
    assert out["bpm"] is None or out["bpm"] > 0


def test_preview_is_320k_mp3(wav, tmp_path):
    import subprocess
    dst = tmp_path / "p.mp3"
    aa.make_preview(wav(tone([440], 5)), dst)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=codec_name,bit_rate", "-of", "json", str(dst)],
        capture_output=True, text=True, check=True,
    )
    stream = json.loads(probe.stdout)["streams"][0]
    assert stream["codec_name"] == "mp3"
    assert int(stream["bit_rate"]) == 320000


def test_analyze_missing_file_never_raises(tmp_path):
    out = aa.analyze(Path(tmp_path / "nope.wav"), tmp_path)
    assert out["preview_path"] is None and out["bpm"] is None and out["key"] is None
    assert out["errors"]
