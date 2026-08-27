"""
oVoxi stem separation worker — Modal GPU app.

Phase 2: backend-integrated. Callback route wired in server.py.

Model names confirmed via infra/modal/list_models.py against audio-separator 0.31.3:
  ROFORMER_MODEL = "vocals_mel_band_roformer.ckpt"   # Kimberley Jensen, 2-stem
  DEMUCS_MODEL   = "htdemucs_ft.yaml"                 # htdemucs_ft, 4-stem
"""

import hashlib
import hmac
import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path

import modal

# ---------------------------------------------------------------------------
# Constants — confirmed from models.json in audio-separator 0.31.3
# ---------------------------------------------------------------------------

MODEL_DIR      = "/models"
ROFORMER_MODEL = "vocals_mel_band_roformer.ckpt"  # Kimberley Jensen 2-stem vocals
DEMUCS_MODEL   = "htdemucs_ft.yaml"               # htdemucs_ft 4-stem

# L4 GPU billing rate — used by test_modal_stems.py for cost estimate
L4_RATE_PER_SEC = 0.000222  # $/sec as of Modal pricing page (PRD §2)

# Bump this string on every meaningful deploy so Modal logs confirm which
# code version executed. A warm container on old code logs the old string.
WORKER_VERSION = "wav24-v1"

# ---------------------------------------------------------------------------
# Image: CUDA-capable Python 3.12 with models baked in at build time
# ---------------------------------------------------------------------------

def _download_models():
    """
    Runs inside the container at image build time via run_function.
    Writes both model checkpoints to MODEL_DIR so cold starts have
    no network I/O. Called once; result is baked into the image layer.
    """
    import logging
    import os
    os.makedirs(MODEL_DIR, exist_ok=True)
    from audio_separator.separator import Separator

    # RoFormer vocals model (2-stem: Vocals + Instrumental)
    sep_r = Separator(model_file_dir=MODEL_DIR, log_level=logging.INFO)
    sep_r.load_model(ROFORMER_MODEL)
    print(f"[bake] Downloaded {ROFORMER_MODEL}")

    # htdemucs_ft (4-stem: vocals, drums, bass, other)
    sep_d = Separator(model_file_dir=MODEL_DIR, log_level=logging.INFO)
    sep_d.load_model(DEMUCS_MODEL)
    print(f"[bake] Downloaded {DEMUCS_MODEL}")


_gpu_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install(["ffmpeg", "libsndfile1", "libgomp1"])
    # Modal's pip mirror (pypi-mirror.modal.local) ignores extra_index_url.
    # torch 2.13.0+cu130 is what the mirror resolved when unpinned; pin to
    # 2.11.0 (highest confirmed available in the mirror).
    # torchaudio removed: 2.11 changed its default backend to torchcodec which
    # is not installed. Audio I/O is handled by soundfile+librosa instead.
    .pip_install("torch==2.11.0")
    # audioread is imported at the top level by uvr_lib_v5/spec_utils.py but
    # is no longer a transitive dep of librosa>=0.10. Declare it explicitly.
    # librosa pinned to 0.10.1: first series with Python 3.12 compat, still
    # accepts the deprecated `filename` kwarg that audio-separator calls in
    # get_duration(). librosa 1.0.0 removed that kwarg entirely — do not bump
    # until audio-separator is updated to use `path=` instead.
    .pip_install(
        "audio-separator[gpu]==0.31.3",
        "audioread==3.0.1",
        "librosa==0.10.1",
        "boto3",
        "requests",
    )
    .run_function(_download_models)
)

app = modal.App("ovoxi-stem-worker")

# ---------------------------------------------------------------------------
# GPU stem separation
# ---------------------------------------------------------------------------

@app.function(
    gpu="L4",
    timeout=1800,
    retries=0,          # explicit: a retry = duplicate GPU charge + duplicate callback
    image=_gpu_image,
    secrets=[modal.Secret.from_name("ovoxi-stem-secrets")],
)
def separate_stems(
    submission_id: str,
    mastered_r2_key: str,
    artist_slug: str,
    track_slug: str,
    key_prefix: str = "catalog",
) -> dict:
    """
    Download mastered audio from R2, separate into five stems, upload back to R2,
    and POST a signed callback. Never returns silently — always fires the callback.

    Returns the callback payload dict (used by test_modal_stems.py).

    Five stems (stem_schema_version: 2):
      vocals        — RoFormer isolated vocal            (vocals_mel_band_roformer.ckpt)
      instrumental  — RoFormer full mix minus vocals     (vocals_mel_band_roformer.ckpt)
      drums         — htdemucs_ft isolated drums         (htdemucs_ft.yaml)
      bass          — htdemucs_ft isolated bass          (htdemucs_ft.yaml)
      other         — htdemucs_ft true residual          (htdemucs_ft.yaml)

    other_subtract (instrumental − drums − bass) is still computed but not uploaded;
    kept per CLAUDE.md rule 4 (additive first, delete second).
    """
    import numpy as np
    import boto3
    import librosa
    import requests
    import soundfile as sf
    import torch
    from botocore.config import Config
    from audio_separator.separator import Separator

    # Fail loudly rather than falling back to CPU and burning 20 minutes of
    # GPU-priced wall clock at a fraction of the throughput.
    assert torch.cuda.is_available(), (
        f"No CUDA device visible (torch {torch.__version__}) — "
        "refusing to run on CPU. Check the Modal function's gpu= parameter."
    )

    log = logging.getLogger("stem_worker")
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    log.info("stem_worker %s  submission_id=%s", WORKER_VERSION, submission_id)

    r2 = boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )
    bucket         = os.environ["R2_BUCKET_NAME"]
    callback_url   = os.environ["STEM_CALLBACK_URL"]
    webhook_secret = os.environ["STEM_WEBHOOK_SECRET"]
    stem_prefix    = f"{key_prefix}/{artist_slug}/{track_slug}/stems"

    def _ffprobe_sr(path: Path) -> int:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error",
             "-select_streams", "a:0",
             "-show_entries", "stream=sample_rate",
             "-of", "json",
             str(path)],
            stderr=subprocess.DEVNULL,
        )
        return int(json.loads(out)["streams"][0]["sample_rate"])

    # The HMAC is computed over the exact bytes in `body`. The POST must use
    # data=body, never json=payload — requests' json= re-serializes with
    # different separators and the server's hmac.compare_digest would always
    # fail, hanging every track in processing with no visible error.
    def _post_callback(payload: dict) -> None:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        sig = hmac.new(
            webhook_secret.encode(), body, hashlib.sha256
        ).hexdigest()
        try:
            resp = requests.post(
                callback_url,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Ovoxi-Signature": f"sha256={sig}",
                },
                timeout=30,
            )
            log.info("Callback HTTP %s for submission %s", resp.status_code, submission_id)
        except Exception as exc:
            log.error("Callback POST failed for submission %s: %s", submission_id, exc)

    try:
        with tempfile.TemporaryDirectory() as _tmp:
            workdir = Path(_tmp)

            # ── 1. Download mastered audio from R2 ────────────────────────────
            log.info("Downloading %s", mastered_r2_key)
            src_ext  = Path(mastered_r2_key).suffix
            src_path = workdir / f"mastered{src_ext}"
            obj = r2.get_object(Bucket=bucket, Key=mastered_r2_key)
            src_path.write_bytes(obj["Body"].read())

            # Verify and log sample rate. Do NOT silently resample here.
            # htdemucs_ft resamples internally to 44100; this is auditable via
            # source_sample_rate in the callback payload.
            src_sr = _ffprobe_sr(src_path)
            if src_sr != 44100:
                log.warning(
                    "Source is %d Hz (not 44100). htdemucs_ft will resample "
                    "internally; output WAVs are at 44100 regardless of input. "
                    "RoFormer respects its config sample rate. "
                    "Verify via source_sample_rate in the callback payload.",
                    src_sr,
                )

            # ── 2. RoFormer: vocals + instrumental ─────────────────────────────
            log.info("Running RoFormer (%s)", ROFORMER_MODEL)
            roformer_dir = workdir / "roformer"
            roformer_dir.mkdir()
            sep_r = Separator(
                output_dir=str(roformer_dir),
                model_file_dir=MODEL_DIR,
                output_format="WAV",
                log_level=logging.INFO,
            )
            sep_r.load_model(ROFORMER_MODEL)
            roformer_outputs = sep_r.separate(str(src_path))
            log.info("RoFormer outputs: %s", roformer_outputs)

            # separate() returns bare filenames, not absolute paths.
            # Join each to roformer_dir to get absolute Paths; do not rescan the
            # directory, which could pick up stale files from a previous pass.
            def _pick(paths: list[str], keywords: list[str]) -> Path:
                candidates = sorted(roformer_dir / p for p in paths)
                for f in candidates:
                    if any(kw in f.name.lower() for kw in keywords):
                        return f
                raise FileNotFoundError(
                    f"No file matching {keywords} in {[p for p in paths]}. "
                    f"Searched: {[f.name for f in candidates]}"
                )

            # audio-separator names outputs as: input_(STEM_LABEL)_MODEL_NAME.wav
            # The model name "vocals_mel_band_roformer" contains "vocal", so bare "vocal"
            # matches both files — the (other) file sorts first alphabetically and wins.
            # Match only the parenthetical label: "_(vocal" hits (vocals) not (other).
            vocals_wav       = _pick(roformer_outputs, ["_(vocal"])
            instrumental_wav = _pick(
                roformer_outputs,
                ["_(other", "instrumental", "instrum", "no_vocal", "no vocal", "no-vocal"],
            )

            # ── 3. htdemucs_ft: drums + bass + other ──────────────────────────
            log.info("Running htdemucs_ft")
            demucs_dir = workdir / "demucs"
            demucs_dir.mkdir()
            sep_d = Separator(
                output_dir=str(demucs_dir),
                model_file_dir=MODEL_DIR,
                output_format="WAV",
                log_level=logging.INFO,
            )
            sep_d.load_model(DEMUCS_MODEL)
            demucs_outputs = sep_d.separate(str(src_path))
            log.info("Demucs outputs: %s", demucs_outputs)

            def _pick_d(keywords: list[str]) -> Path:
                # rglob handles the subdirectory demucs sometimes creates
                for f in sorted(demucs_dir.rglob("*.wav")):
                    if any(kw in f.name.lower() for kw in keywords):
                        return f
                raise FileNotFoundError(
                    f"No file matching {keywords} in demucs_dir. "
                    f"Files: {[f.name for f in sorted(demucs_dir.rglob('*.wav'))]}"
                )

            drums_wav = _pick_d(["drum"])
            bass_wav  = _pick_d(["bass"])
            other_wav = _pick_d(["other", "residual"])
            # htdemucs vocals output — not uploaded, not used in other_subtract
            # (which is computed from RoFormer instrumental minus htdemucs drums/bass).
            # Included in the collision guard below to catch demucs output misassignments.
            htdemucs_vocals_wav = _pick_d(["vocal"])

            # Sanity: every resolved stem path must be unique.
            # A duplicate means two stems point to the same file on disk —
            # the vocal keyword bug produced exactly this failure mode.
            # .resolve() normalises symlinks so two Path objects pointing to
            # the same inode compare equal.
            _resolved = {
                "vocals":          vocals_wav,
                "instrumental":    instrumental_wav,
                "drums":           drums_wav,
                "bass":            bass_wav,
                "other":           other_wav,
                "htdemucs_vocals": htdemucs_vocals_wav,  # internal; not uploaded
            }
            _seen_paths: set[Path] = set()
            for _stem_name, _stem_path in _resolved.items():
                _canonical = _stem_path.resolve()
                if _canonical in _seen_paths:
                    raise RuntimeError(
                        f"Stem path collision: '{_stem_name}' resolved to a path "
                        f"already claimed by another stem.\n"
                        f"Resolved mapping: "
                        f"{ {k: str(v.resolve()) for k, v in _resolved.items()} }"
                    )
                _seen_paths.add(_canonical)

            # Reject if vocals and instrumental are byte-identical.
            # The path-collision guard above catches same Path object; this
            # catches two *different* files on disk with identical content —
            # e.g., the pipeline wrote the same source bytes to two paths.
            import hashlib as _hashlib
            def _sha256(p: Path) -> str:
                h = _hashlib.sha256()
                with open(p, "rb") as _fh:
                    for _chunk in iter(lambda: _fh.read(65536), b""):
                        h.update(_chunk)
                return h.hexdigest()

            _vocals_hash = _sha256(vocals_wav)
            _instr_hash  = _sha256(instrumental_wav)
            if _vocals_hash == _instr_hash:
                raise RuntimeError(
                    f"vocals and instrumental are byte-identical "
                    f"(sha256={_vocals_hash}).\n"
                    f"vocals path:       {vocals_wav}\n"
                    f"instrumental path: {instrumental_wav}\n"
                    f"This indicates a stem assignment error."
                )

            log.info(
                "sha256 check passed  vocals=%s  instrumental=%s",
                _vocals_hash, _instr_hash,
            )

            # ── 4. other_subtract: instrumental − drums − bass ────────────────
            #
            # Computed but not written to disk or uploaded. Kept per CLAUDE.md
            # rule 4 (additive first, delete second). The /03 A/B chose
            # other_htdemucs (now `other`) as the canonical residual;
            # other_subtract removal is a later commit.
            #
            # Uses RoFormer instrumental minus htdemucs drums and bass.
            # htdemucs_vocals_wav is not involved in this computation.

            def _load_wav(path: Path) -> tuple[np.ndarray, int]:
                # Returns (channels, frames) float32, matching separator convention
                data, sr = sf.read(str(path), dtype="float32", always_2d=True)
                return data.T, sr

            instr_np, instr_sr = _load_wav(instrumental_wav)
            drums_np, drums_sr = _load_wav(drums_wav)
            bass_np,  bass_sr  = _load_wav(bass_wav)

            # htdemucs and RoFormer both output at 44100; resample only if they
            # diverge (guards against future model changes).
            target_sr = instr_sr
            if drums_sr != target_sr:
                drums_np = librosa.resample(drums_np, orig_sr=drums_sr, target_sr=target_sr)
            if bass_sr != target_sr:
                bass_np  = librosa.resample(bass_np,  orig_sr=bass_sr,  target_sr=target_sr)

            # Trim all to instrumental length (should be identical; guard anyway)
            L = instr_np.shape[-1]
            drums_np = drums_np[..., :L]
            bass_np  = bass_np[...,  :L]

            sub_np = np.clip(instr_np - drums_np - bass_np, -1.0, 1.0)  # noqa: F841

            # ── 5. Normalise five stems → 24-bit PCM WAV, upload to R2 ───────
            #
            # Format reversed 2026-08-27. /03 accepted MP3 320, but LALAL's legacy
            # stems were pcm_s24le WAV, so MP3 made the catalog half lossless and
            # half lossy — the wrong direction for a training-data product, where
            # lossy artifacts are learned by the models trained on them.
            #
            # pcm_s24le, not FLAC: ffmpeg's FLAC encoder takes s16/s32 and will
            # silently downgrade a float input to 16-bit unless given explicit
            # -sample_fmt/-bits_per_raw_sample flags. WAV has no such ambiguity and
            # matches both the mastered file (mg.pcm24) and the legacy LALAL stems.
            #
            # The separator's own output bit depth is not guaranteed, so every stem
            # is normalised through ffmpeg rather than uploaded as-is.
            # -ar preserves the actual output sample rate; never allows ffmpeg
            # to choose a default.
            stems: dict[str, Path] = {
                "vocals":       vocals_wav,
                "instrumental": instrumental_wav,
                "drums":        drums_wav,
                "bass":         bass_wav,
                "other":        other_wav,
            }

            enc_dir = workdir / "encoded"
            enc_dir.mkdir()
            stem_paths: dict[str, str] = {}
            total_out_bytes = 0

            for stem_name, wav_path in stems.items():
                wav_sr   = _ffprobe_sr(wav_path)
                out_path = enc_dir / f"{stem_name}.wav"

                subprocess.run(
                    ["ffmpeg", "-y", "-i", str(wav_path),
                     "-codec:a", "pcm_s24le",
                     "-ar", str(wav_sr),
                     str(out_path)],
                    check=True, capture_output=True,
                )
                total_out_bytes += out_path.stat().st_size

                out_key = f"{stem_prefix}/{stem_name}.wav"
                r2.put_object(
                    Bucket=bucket, Key=out_key,
                    Body=out_path.read_bytes(),
                    ContentType="audio/wav",
                )
                stem_paths[stem_name] = out_key

            log.info(
                "Encoded and uploaded %d stems  WAV24=%.1f MB",
                len(stems), total_out_bytes / 1_048_576,
            )

            # ── 6. Success callback ───────────────────────────────────────────
            payload = {
                "submission_id":       submission_id,
                "status":              "completed",
                "stem_schema_version": 3,
                "stem_format":         "wav24",
                "stem_paths":          stem_paths,
                "source_sample_rate":  src_sr,
            }
            _post_callback(payload)
            return payload

    except Exception as exc:
        log.error(
            "Separation failed for submission %s: %s", submission_id, exc,
            exc_info=True,
        )
        _post_callback({
            "submission_id": submission_id,
            "status": "failed",
            "error": str(exc),
        })
        raise
