# Stem Quality Benchmark — LALAL vs New Engine

Generated: 2026-08-26  |  Engine: MelBand RoFormer + htdemucs_ft via audio-separator 0.31.3

## Judgement — 2026-08-26

**Vocals:** New engine accepted. Confirmed by ear after the `_pick` keyword fix
(bare `"vocal"` fallback removed; see commit `aa956d9`). Both path-collision and
content-hash guards passed on all five runs; vocals and instrumental hashes distinct
on every track.

**Residual (`other`):** `other_htdemucs` selected; `other_subtract` dropped.
`other_subtract` is computed from the RoFormer `instrumental_wav` minus the htdemucs_ft
`drums_wav` minus the htdemucs_ft `bass_wav` — loaded as float32 arrays, resampled
to a common sample rate if they diverge, trimmed to instrumental length, then
`np.clip(instr − drums − bass, −1.0, 1.0)`. It is not a full mix reconstruction:
the htdemucs_ft vocals are not subtracted, and the two models process independently,
so inter-model spectral drift accumulates in the result. Decided by ear between the
two variants. The `other_subtract` code path remains in the worker per CLAUDE.md
rule 4 (additive first, delete second); removal is a separate later commit.

**Storage format:** MP3 320 kbps accepted; FLAC rejected.

**Coverage note:** Judgement was made on four unique tracks, not five. Submissions
`1800f622` (Tyler J — All Along) and `dc9cbb73` (teewhy — all along) are
byte-identical source recordings (mastered sha256 `5ec671126fb8ec8e...`); their
new-engine stems are also identical. Counted as one track for quality assessment.

**Void comparisons:** All pre-fix A/B comparisons of `other_subtract` were void.
`other_subtract` is derived from `instrumental_wav`, and in the pre-fix runs
`instrumental_wav` was the wrong file — the `_(other)` WAV was incorrectly assigned
to both `vocals_wav` and `instrumental_wav` by the bare `"vocal"` keyword bug.
Only the post-fix run (commit `aa956d9`) is authoritative.

---

## Methodology

**What is measured:** file size (bytes), duration (s), peak amplitude (dBFS),
mean amplitude / RMS (dBFS), integrated loudness (LUFS-I), loudness range (LRA),
true peak (dBTP). All computed locally via `ffprobe` and `ffmpeg -af volumedetect,ebur128`.

**What is NOT measured, and not claimed:** signal-to-noise ratio or SDR
(requires a reference separation), MOS or any perceptual quality score (requires
ears, not code), spectral centroid or frequency-domain features (requires local
numpy/librosa, which are not assumed here). The A/B listening session at
`benchmark/compare.html` is the authoritative quality gate for this phase.

**Stem mapping (per PRD-01 §10.4):** LALAL `other` is the full mix minus vocals
— this is identical in intent to the new `instrumental` (RoFormer complement).
These two are the like-for-like comparison pair. The new `other_htdemucs` is the
htdemucs_ft true residual (guitars, keys, pads) and has no LALAL counterpart.

**File format note:** LALAL stored stems in R2 as `pcm_s24le` WAV (24-bit, ~30–40 MB per track)
despite the `.mp3` key suffix. New stems are CBR 320 kbps MP3 (~5–8 MB). File size is
therefore not a direct quality comparison — it reflects format difference, not content.
The `Format` column makes this explicit per row.

**Source sample rate:** htdemucs_ft resamples all input to 44100 Hz internally.
If a source was recorded or mastered at 48 kHz, the new stems will be at 44100 Hz
regardless. This can cause a perceived high-frequency roll-off compared to a
44100 Hz LALAL output. The per-track SR is noted below so this factor is
distinguishable from model quality differences during A/B.

---

## Tyler J — All Along

**Submission:** `1800f622-d246-45a6-b4ad-f44db17cb6f3`  
**Slugs:** `tyler_j / all_along`  
**Source sample rate:** 44100 Hz _(no htdemucs internal resampling)_

### Comparable stems

| Stem | Engine | Format | Size (MB) | Duration (s) | Peak (dBFS) | RMS (dBFS) | LUFS-I | LRA (LU) | True Peak (dBTP) |
|------|--------|--------|----------:|-------------:|------------:|-----------:|-------:|---------:|-----------------:|
| Vocals | LALAL | pcm_s24le | 39.63 | 157.1 | -3.1 | -24.0 | -19.3 | 3.5 | -2.3 |
| Vocals | New | mp3 | 5.99 | 157.1 | -2.9 | -23.7 | -18.9 | 3.5 | -2.2 |
| Drums | LALAL | pcm_s24le | 39.63 | 157.1 | -2.8 | -22.5 | -20.0 | 2.5 | -2.7 |
| Drums | New | mp3 | 5.99 | 157.1 | -3.0 | -22.2 | -19.9 | 2.3 | -2.9 |
| Bass | LALAL | pcm_s24le | 39.63 | 157.1 | -12.0 | -23.0 | -22.2 | 9.3 | -12.0 |
| Bass | New | mp3 | 5.99 | 157.1 | -13.7 | -22.8 | -22.1 | 10.0 | -13.7 |
| Instrumental | LALAL | pcm_s24le | 39.63 | 157.1 | -2.9 | -18.7 | -16.8 | 2.8 | -2.5 |
| Instrumental | New | mp3 | 5.99 | 157.1 | -2.1 | -18.7 | -16.8 | 2.8 | -1.8 |

### New-only stems (no LALAL counterpart)

| Stem | Format | Size (MB) | Duration (s) | Peak (dBFS) | RMS (dBFS) | LUFS-I | LRA (LU) | True Peak (dBTP) |
|------|--------|----------:|-------------:|------------:|-----------:|-------:|---------:|-----------------:|
| Other — htdemucs residual | mp3 | 5.99 | 157.1 | -11.8 | -28.1 | -24.9 | 5.3 | -11.8 |
| Other — arithmetic subtract | mp3 | 5.99 | 157.1 | -11.0 | -27.4 | -24.1 | 4.1 | -11.0 |

---

## teewhy — all along

**Submission:** `dc9cbb73-3149-41d5-bc8a-be27577310aa`  
**Slugs:** `teewhy / all_along`  
**Source sample rate:** 44100 Hz _(no htdemucs internal resampling)_

### Comparable stems

| Stem | Engine | Format | Size (MB) | Duration (s) | Peak (dBFS) | RMS (dBFS) | LUFS-I | LRA (LU) | True Peak (dBTP) |
|------|--------|--------|----------:|-------------:|------------:|-----------:|-------:|---------:|-----------------:|
| Vocals | LALAL | pcm_s24le | 39.63 | 157.1 | -3.1 | -24.0 | -19.3 | 3.5 | -2.3 |
| Vocals | New | mp3 | 5.99 | 157.1 | -2.9 | -23.7 | -18.9 | 3.5 | -2.2 |
| Drums | LALAL | pcm_s24le | 39.63 | 157.1 | -2.8 | -22.5 | -20.0 | 2.5 | -2.7 |
| Drums | New | mp3 | 5.99 | 157.1 | -2.9 | -22.2 | -19.9 | 2.3 | -2.8 |
| Bass | LALAL | pcm_s24le | 39.63 | 157.1 | -12.0 | -23.0 | -22.2 | 9.3 | -12.0 |
| Bass | New | mp3 | 5.99 | 157.1 | -13.7 | -22.8 | -22.1 | 10.0 | -13.7 |
| Instrumental | LALAL | pcm_s24le | 39.63 | 157.1 | -2.9 | -18.7 | -16.8 | 2.8 | -2.5 |
| Instrumental | New | mp3 | 5.99 | 157.1 | -2.1 | -18.7 | -16.8 | 2.8 | -1.8 |

### New-only stems (no LALAL counterpart)

| Stem | Format | Size (MB) | Duration (s) | Peak (dBFS) | RMS (dBFS) | LUFS-I | LRA (LU) | True Peak (dBTP) |
|------|--------|----------:|-------------:|------------:|-----------:|-------:|---------:|-----------------:|
| Other — htdemucs residual | mp3 | 5.99 | 157.1 | -11.8 | -28.1 | -24.9 | 5.3 | -11.8 |
| Other — arithmetic subtract | mp3 | 5.99 | 157.1 | -11.2 | -27.4 | -24.1 | 4.1 | -11.2 |

---

## teewhy — ceo

**Submission:** `8ccb8ab3-8a79-43f2-b8cc-326615030273`  
**Slugs:** `teewhy / ceo`  
**Source sample rate:** 44100 Hz _(no htdemucs internal resampling)_

### Comparable stems

| Stem | Engine | Format | Size (MB) | Duration (s) | Peak (dBFS) | RMS (dBFS) | LUFS-I | LRA (LU) | True Peak (dBTP) |
|------|--------|--------|----------:|-------------:|------------:|-----------:|-------:|---------:|-----------------:|
| Vocals | LALAL | pcm_s24le | 48.09 | 190.6 | -4.3 | -22.5 | -18.1 | 6.0 | -4.4 |
| Vocals | New | mp3 | 7.27 | 190.6 | -7.1 | -23.1 | -18.9 | 6.2 | -7.1 |
| Drums | LALAL | pcm_s24le | 48.09 | 190.6 | -0.0 | -22.9 | -18.6 | 20.3 | -0.0 |
| Drums | New | mp3 | 7.27 | 190.6 | -0.8 | -23.1 | -18.5 | 20.5 | -0.8 |
| Bass | LALAL | pcm_s24le | 48.09 | 190.6 | -14.0 | -27.3 | -24.3 | 19.0 | -14.0 |
| Bass | New | mp3 | 7.27 | 190.6 | -13.9 | -27.1 | -24.2 | 10.1 | -13.9 |
| Instrumental | LALAL | pcm_s24le | 48.09 | 190.6 | -0.0 | -20.4 | -17.8 | 7.4 | 0.0 |
| Instrumental | New | mp3 | 7.27 | 190.6 | -1.1 | -21.1 | -18.5 | 6.9 | -1.0 |

### New-only stems (no LALAL counterpart)

| Stem | Format | Size (MB) | Duration (s) | Peak (dBFS) | RMS (dBFS) | LUFS-I | LRA (LU) | True Peak (dBTP) |
|------|--------|----------:|-------------:|------------:|-----------:|-------:|---------:|-----------------:|
| Other — htdemucs residual | mp3 | 7.27 | 190.6 | -8.4 | -27.1 | -23.3 | 5.1 | -8.4 |
| Other — arithmetic subtract | mp3 | 7.27 | 190.6 | -8.5 | -28.0 | -24.1 | 5.3 | -8.3 |

---

## teewhy — Dirty Secret

**Submission:** `86677473-94e8-4c34-abe6-8209ed6e08ad`  
**Slugs:** `teewhy / dirty_secret`  
**Source sample rate:** 44100 Hz _(no htdemucs internal resampling)_

### Comparable stems

| Stem | Engine | Format | Size (MB) | Duration (s) | Peak (dBFS) | RMS (dBFS) | LUFS-I | LRA (LU) | True Peak (dBTP) |
|------|--------|--------|----------:|-------------:|------------:|-----------:|-------:|---------:|-----------------:|
| Vocals | LALAL | pcm_s24le | 32.06 | 127.1 | -5.7 | -25.3 | -20.5 | 4.9 | -5.8 |
| Vocals | New | mp3 | 4.85 | 127.1 | -5.2 | -25.2 | -20.4 | 4.5 | -5.3 |
| Drums | LALAL | pcm_s24le | 32.06 | 127.1 | -4.1 | -23.7 | -20.7 | 4.2 | -3.9 |
| Drums | New | mp3 | 4.85 | 127.1 | -4.7 | -23.5 | -20.6 | 4.0 | -4.6 |
| Bass | LALAL | pcm_s24le | 32.06 | 127.1 | -12.3 | -25.4 | -23.9 | 10.9 | -12.3 |
| Bass | New | mp3 | 4.85 | 127.1 | -12.0 | -24.8 | -23.9 | 7.6 | -12.0 |
| Instrumental | LALAL | pcm_s24le | 32.06 | 127.1 | -3.4 | -19.9 | -17.9 | 6.8 | -3.3 |
| Instrumental | New | mp3 | 4.85 | 127.1 | -3.4 | -19.9 | -17.8 | 6.5 | -3.3 |

### New-only stems (no LALAL counterpart)

| Stem | Format | Size (MB) | Duration (s) | Peak (dBFS) | RMS (dBFS) | LUFS-I | LRA (LU) | True Peak (dBTP) |
|------|--------|----------:|-------------:|------------:|-----------:|-------:|---------:|-----------------:|
| Other — htdemucs residual | mp3 | 4.85 | 127.1 | -10.3 | -28.7 | -25.4 | 12.8 | -10.3 |
| Other — arithmetic subtract | mp3 | 4.85 | 127.1 | -8.8 | -27.5 | -24.2 | 12.8 | -8.7 |

---

## damnsonic — cutthroat

**Submission:** `b114fc07-a4c5-43c4-8529-1a06cec4b28e`  
**Slugs:** `damnsonic / cutthroat`  
**Source sample rate:** 44100 Hz _(no htdemucs internal resampling)_

### Comparable stems

| Stem | Engine | Format | Size (MB) | Duration (s) | Peak (dBFS) | RMS (dBFS) | LUFS-I | LRA (LU) | True Peak (dBTP) |
|------|--------|--------|----------:|-------------:|------------:|-----------:|-------:|---------:|-----------------:|
| Vocals | LALAL | pcm_s24le | 38.69 | 153.3 | -3.3 | -24.8 | -20.3 | 3.8 | -2.4 |
| Vocals | New | mp3 | 5.85 | 153.3 | -6.3 | -26.0 | -21.3 | 3.5 | -6.3 |
| Drums | LALAL | pcm_s24le | 38.69 | 153.3 | 0.0 | -21.0 | -18.0 | 5.4 | 0.9 |
| Drums | New | mp3 | 5.85 | 153.3 | -0.9 | -23.5 | -20.0 | 4.1 | -0.4 |
| Bass | LALAL | pcm_s24le | 38.69 | 153.3 | -4.5 | -26.0 | -23.4 | 12.4 | -4.5 |
| Bass | New | mp3 | 5.85 | 153.3 | -6.2 | -23.7 | -22.3 | 6.0 | -6.2 |
| Instrumental | LALAL | pcm_s24le | 38.69 | 153.3 | 0.0 | -18.4 | -16.2 | 6.3 | 0.8 |
| Instrumental | New | mp3 | 5.85 | 153.3 | -0.9 | -19.5 | -17.1 | 4.8 | -0.1 |

### New-only stems (no LALAL counterpart)

| Stem | Format | Size (MB) | Duration (s) | Peak (dBFS) | RMS (dBFS) | LUFS-I | LRA (LU) | True Peak (dBTP) |
|------|--------|----------:|-------------:|------------:|-----------:|-------:|---------:|-----------------:|
| Other — htdemucs residual | mp3 | 5.85 | 153.3 | -9.3 | -25.2 | -22.6 | 5.3 | -9.3 |
| Other — arithmetic subtract | mp3 | 5.85 | 153.3 | -8.8 | -26.0 | -23.4 | 4.4 | -8.8 |

---
