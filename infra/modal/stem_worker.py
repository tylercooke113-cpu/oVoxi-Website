"""
oVoxi stem separation worker — Modal GPU app.

Phase 1: standalone. Backend integration (Phase 2) adds the callback route.

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
) -> dict:
    """
    Download mastered audio from R2, separate into six stems, upload back to R2,
    and POST a signed callback. Never returns silently — always fires the callback.

    Returns the callback payload dict (used by test_modal_stems.py).

    Six stems (stem_schema_version: 2):
      vocals          — RoFormer isolated vocal            (vocals_mel_band_roformer.ckpt)
      instrumental    — RoFormer full mix minus vocals     (vocals_mel_band_roformer.ckpt)
      drums           — htdemucs_ft isolated drums         (htdemucs_ft.yaml)
      bass            — htdemucs_ft isolated bass          (htdemucs_ft.yaml)
      other_htdemucs  — htdemucs_ft residual               (htdemucs_ft.yaml)
      other_subtract  — instrumental − drums − bass,       (sample-aligned subtraction)
                        sample-aligned; for Phase 3 A/B

    Per PRD-01 §10.1: other_htdemucs and other_subtract are both kept in Phase 1
    so the A/B (/03) can decide which to promote to the canonical `other` key.
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

    r2 = boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )
    bucket       = os.environ["R2_BUCKET_NAME"]
    callback_url = os.environ["STEM_CALLBACK_URL"]
    webhook_secret = os.environ["STEM_WEBHOOK_SECRET"]
    stem_prefix  = f"catalog/{artist_slug}/{track_slug}/stems"

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
            # Scan the output directory directly for absolute Path objects.
            def _pick(paths: list[str], keywords: list[str]) -> Path:
                for f in sorted(roformer_dir.iterdir()):
                    if any(kw in f.name.lower() for kw in keywords):
                        return f
                raise FileNotFoundError(
                    f"No file matching {keywords} in roformer_dir. "
                    f"Files: {[f.name for f in sorted(roformer_dir.iterdir())]}"
                )

            # audio-separator names outputs as: input_(STEM_LABEL)_MODEL_NAME.wav
            # The model name "vocals_mel_band_roformer" contains "vocal", so matching
            # bare "vocal" hits both files. Match the parenthetical label instead.
            vocals_wav       = _pick(roformer_outputs, ["_(vocal", "vocal"])
            instrumental_wav = _pick(
                roformer_outputs,
                ["_(other", "instrumental", "instrum", "no_vocal", "no vocal", "no-vocal"],
            )

            # ── 3. htdemucs_ft: drums + bass + other (htdemucs residual) ──────
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

            drums_wav          = _pick_d(["drum"])
            bass_wav           = _pick_d(["bass"])
            other_htdemucs_wav = _pick_d(["other", "residual"])
            # htdemucs vocals output — loaded only for the subtraction; not uploaded
            htdemucs_vocals_wav = _pick_d(["vocal"])

            # ── 4. other_subtract: instrumental − drums − bass ────────────────
            #
            # All four sources derive from the same mastered audio, so they are
            # aligned in time. htdemucs outputs at 44100 Hz regardless of input;
            # RoFormer respects its config SR (also 44100 for this model).
            # We resample to a common rate only if they diverge, then clamp.
            #
            # Phase 3 A/B will decide between other_htdemucs (residual after
            # all four separate cleanly) and other_subtract (algebraic; picks up
            # inter-model spectral drift but no bleed artefacts from a 3rd pass).

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

            sub_np = np.clip(instr_np - drums_np - bass_np, -1.0, 1.0)
            other_subtract_wav = workdir / "other_subtract.wav"
            sf.write(str(other_subtract_wav), sub_np.T, target_sr, subtype="PCM_24")

            # ── 5. Encode WAVs → MP3 320kbps + FLAC ─────────────────────────
            #
            # Both formats written in Phase 1 so we can hear whether the
            # 320kbps lossy floor matters before committing to MP3-only.
            # -ar preserves the actual output sample rate; never allows ffmpeg
            # to choose a default.
            stems: dict[str, Path] = {
                "vocals":         vocals_wav,
                "instrumental":   instrumental_wav,
                "drums":          drums_wav,
                "bass":           bass_wav,
                "other_htdemucs": other_htdemucs_wav,
                "other_subtract": other_subtract_wav,
            }

            enc_dir = workdir / "encoded"
            enc_dir.mkdir()
            encoded: dict[str, dict[str, Path]] = {}
            total_mp3_bytes  = 0
            total_flac_bytes = 0

            for stem_name, wav_path in stems.items():
                wav_sr    = _ffprobe_sr(wav_path)
                mp3_path  = enc_dir / f"{stem_name}.mp3"
                flac_path = enc_dir / f"{stem_name}.flac"

                subprocess.run(
                    ["ffmpeg", "-y", "-i", str(wav_path),
                     "-codec:a", "libmp3lame", "-b:a", "320k",
                     "-ar", str(wav_sr),
                     str(mp3_path)],
                    check=True, capture_output=True,
                )
                subprocess.run(
                    ["ffmpeg", "-y", "-i", str(wav_path),
                     "-codec:a", "flac",
                     "-ar", str(wav_sr),
                     str(flac_path)],
                    check=True, capture_output=True,
                )
                encoded[stem_name] = {"mp3": mp3_path, "flac": flac_path}
                total_mp3_bytes  += mp3_path.stat().st_size
                total_flac_bytes += flac_path.stat().st_size

            flac_delta_mb = (total_flac_bytes - total_mp3_bytes) / 1_048_576
            log.info(
                "Encoded %d stems  MP3=%.1f MB  FLAC=%.1f MB  FLAC_delta=+%.1f MB",
                len(stems),
                total_mp3_bytes  / 1_048_576,
                total_flac_bytes / 1_048_576,
                flac_delta_mb,
            )

            # ── 6. Upload 12 files (6 MP3 + 6 FLAC) to R2 ───────────────────
            stem_paths: dict[str, str] = {}
            flac_paths: dict[str, str] = {}

            for stem_name, paths in encoded.items():
                mp3_key  = f"{stem_prefix}/{stem_name}.mp3"
                flac_key = f"{stem_prefix}/{stem_name}.flac"

                r2.put_object(
                    Bucket=bucket, Key=mp3_key,
                    Body=paths["mp3"].read_bytes(),
                    ContentType="audio/mpeg",
                )
                r2.put_object(
                    Bucket=bucket, Key=flac_key,
                    Body=paths["flac"].read_bytes(),
                    ContentType="audio/flac",
                )
                stem_paths[stem_name] = mp3_key
                flac_paths[stem_name] = flac_key

            # ── 7. Success callback ───────────────────────────────────────────
            payload = {
                "submission_id": submission_id,
                "status": "completed",
                "stem_schema_version": 2,
                "stem_paths": stem_paths,
                "flac_paths": flac_paths,
                "other_variants": {
                    "other_htdemucs": {
                        "description": "htdemucs_ft residual (guitars, keys, pads — non-overlapping)",
                        "mp3_key": stem_paths["other_htdemucs"],
                        "flac_key": flac_paths["other_htdemucs"],
                    },
                    "other_subtract": {
                        "description": "instrumental minus drums minus bass, sample-aligned subtraction",
                        "mp3_key": stem_paths["other_subtract"],
                        "flac_key": flac_paths["other_subtract"],
                    },
                },
                "source_sample_rate": src_sr,
                "storage_delta_flac_bytes": total_flac_bytes - total_mp3_bytes,
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
