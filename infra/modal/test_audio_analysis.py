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


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def progression(chords, seconds_each=2.0, repeats=3):
    return np.concatenate([tone([midi(n) for n in c], seconds_each) for _ in range(repeats) for c in chords])


@pytest.fixture
def wav(tmp_path):
    def _write(y, name="in.wav"):
        path = tmp_path / name
        sf.write(path, y, SR, subtype="PCM_24")
        return path
    return _write


def test_bpm_click_track_120(wav):
    y = aa.load_mono(wav(click_track(120, 30)))
    assert aa.detect_bpm(y) == pytest.approx(120, abs=3)


def test_key_c_major_progression(wav):
    # I - IV - V - I in C major
    y = aa.load_mono(wav(progression([(60, 64, 67), (65, 69, 72), (67, 71, 74), (60, 64, 67)])))
    assert aa.detect_key(y) == "C major"


def test_key_a_minor_progression(wav):
    # i - iv - v - i in A minor
    y = aa.load_mono(wav(progression([(57, 60, 64), (62, 65, 69), (64, 67, 71), (57, 60, 64)])))
    assert aa.detect_key(y) == "A minor"


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
    src = wav(progression([(60, 64, 67), (65, 69, 72), (67, 71, 74), (60, 64, 67)]))
    out = aa.analyze(src, tmp_path)
    assert out["errors"] == []
    assert out["preview_path"].exists()
    data = json.loads(out["waveform_path"].read_text())
    assert data["version"] == 1 and data["points"] == aa.WAVEFORM_POINTS
    assert len(data["peaks"]) == aa.WAVEFORM_POINTS
    assert out["key"] == "C major"
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
