import asyncio
import hashlib
import hmac
import json
import os
import logging
import re
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timezone, timedelta
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import List, Literal, Optional
from urllib.parse import quote

import boto3
import httpx
import modal
from botocore.config import Config
from botocore.exceptions import ClientError
from dotenv import load_dotenv
import jwt
from jwt import PyJWKClient
from fastapi import BackgroundTasks, Depends, FastAPI, APIRouter, HTTPException, Header, Request
from fastapi.responses import JSONResponse, Response
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from pydantic import BaseModel, Field, ConfigDict, EmailStr, field_validator, model_validator
from sync_constants import (
    MOODS, MAX_MOODS, VOCALS, SAMPLE_DECLARATIONS, CONTENT_ID_ANSWERS,
    DISTRIBUTORS, PRO_ORGS, IPI_PATTERN, MUSICAL_KEYS, BPM_MIN, BPM_MAX, COUNTRIES,
    PLANS, SUB_DAY_CAP,
)
from consent_ledger import record_grants, record_withdrawals, GRANT_VERSION
import artist_agreement
from profile_photo import (
    MAX_PHOTO_BYTES, PHOTO_CONTENT_TYPES, PHOTO_SIZES, PhotoRejected, REJECT_MESSAGE, process_photo,
)
from sync_public import (
    LISTING_FILTER, is_listed, photo_visible, public_profile_view, public_track_view,
)
import sync_orders
import licenses
import quotes
from license_pdf import TERMS as LICENSE_TERMS, render_license_pdf
from email_sender import send_email
from sync_emails import license_email, quote_email, subscription_license_email
import subscriptions
from sync_search import PAGE_SIZE, SearchParamError, build_filter, build_pipeline, encode_cursor, parse_params
from sync_vault import (
    INSTAGRAM_URL, SPOTIFY_ARTIST_URL, is_legacy, metadata_patch_fields,
    slugify_profile, vault_track_view,
)
from rights import TrackRightsIn, build_rights
from clearance import evaluate as evaluate_clearance
from metadata_reconcile import reconcile as reconcile_metadata
from starlette.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

import acrcloud_check


# Railway's edge REPLACES both X-Real-IP and X-Forwarded-For with values it
# controls rather than appending to client-supplied values. Verified 2026-09-25
# by sending forged X-Real-IP and X-Forwarded-For headers to production and
# confirming neither reached this handler. X-Real-IP is the real client alone;
# X-Forwarded-For arrives as "<real client>, <railway edge>", so the leftmost
# entry is equally trustworthy. If a second proxy (Cloudflare, etc.) is placed
# in front of Railway this must be re-tested -- the trust assumption changes.
# Current assumption: 1 Railway replica; slowapi's in-process counter is
# per-replica, so a multi-replica deployment would require shared storage (Redis).
def get_real_client_ip(request: Request) -> str:
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip
    first = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if first:
        return first
    return request.client.host if request.client else "unknown"


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Cloudflare R2
r2_client = boto3.client(
    "s3",
    endpoint_url=os.environ.get("R2_ENDPOINT"),
    aws_access_key_id=os.environ.get("R2_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("R2_SECRET_ACCESS_KEY"),
    config=Config(signature_version="s3v4"),
    region_name="auto",
)
R2_BUCKET = os.environ.get("R2_BUCKET_NAME", "")
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(150 * 1024 * 1024)))

# Lalal.ai
LALAL_API_KEY = os.environ.get("LALAL_API_KEY", "")
LALAL_BASE = "https://www.lalal.ai/api"

MODAL_APP = "ovoxi-stem-worker"
MODAL_FN  = "separate_stems"

AUDIO_CONTENT_TYPES = {".mp3": "audio/mpeg", ".wav": "audio/wav"}

INSTANCE_ID = str(uuid.uuid4())
RUN_WORKER = os.environ.get("RUN_WORKER", "true") == "true"
WORKER_POLL_INTERVAL = int(os.environ.get("WORKER_POLL_INTERVAL", "5"))
WORKER_CONCURRENCY = int(os.environ.get("WORKER_CONCURRENCY", "1"))
STALE_LOCAL_MIN = int(os.environ.get("STALE_LOCAL_MIN", "30"))
# Must exceed worst-case in-process runtime: Matchering (~10 min) + LALAL polling (~12 min)
# = ~22 min worst case. Assumes Modal path where "mastering" ends at dispatch; if LALAL
# is re-enabled this threshold must be revisited before deploying.
STALE_MODAL_MIN = int(os.environ.get("STALE_MODAL_MIN", "45"))
# Must exceed the Modal function timeout (currently 1800s = 30 min). Raise this if the
# Modal timeout increases.
SWEEPER_INTERVAL = int(os.environ.get("SWEEPER_INTERVAL", "120"))
ABANDON_PENDING_HOURS = int(os.environ.get("ABANDON_PENDING_HOURS", "2"))
# Fulfilment reconciler (Brief 17): retry paid-but-unfulfilled orders out of band.
FULFIL_RECONCILE_INTERVAL = int(os.environ.get("FULFIL_RECONCILE_INTERVAL", "300"))
FULFIL_MIN_AGE_MIN = int(os.environ.get("FULFIL_MIN_AGE_MIN", "2"))
FULFIL_MAX_ATTEMPTS = int(os.environ.get("FULFIL_MAX_ATTEMPTS", "10"))
CALLBACK_TIMESTAMP_TOLERANCE = int(os.environ.get("CALLBACK_TIMESTAMP_TOLERANCE", "300"))
# seconds; must accommodate clock skew between Modal and Railway

KNOWN_STEM_NAMES = {"vocals", "instrumental", "drums", "bass", "other"}

PROOF_CONTENT_TYPES = {
    ".pdf":  "application/pdf",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
    ".doc":  "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

limiter = Limiter(key_func=get_real_client_ip)
app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    lambda request, exc: JSONResponse(
        status_code=429,
        content={"error": "Too many requests. Please try again in a minute."},
    ),
)

# NOTE: an exception_handler registered for bare Exception runs in Starlette's outermost
# middleware layer, outside CORSMiddleware. These 500 responses carry no CORS headers, so
# browsers surfacing them from the frontend see a CORS error rather than a 500. This is
# acceptable — the error is still logged server-side — but do not waste time debugging a
# "CORS issue" on a path that is actually throwing a Python exception.
@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=500, content={"error": "Internal server error"})
app.add_middleware(SlowAPIMiddleware)

api_router = APIRouter(prefix="/api")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

CLERK_JWKS_URL = os.environ["CLERK_JWKS_URL"]
CLERK_ISSUER = os.environ["CLERK_ISSUER"]
CLERK_AUTHORIZED_PARTIES = {
    o.strip() for o in os.environ.get(
        "CLERK_AUTHORIZED_PARTIES", "https://ovoxi.net,https://www.ovoxi.net"
    ).split(",") if o.strip()
}
CLERK_SECRET_KEY = os.environ.get("CLERK_SECRET_KEY", "")
# Keys are cached in-process for an hour; Clerk is only called on cache miss or key rotation.
_jwks_client = PyJWKClient(CLERK_JWKS_URL, cache_keys=True, lifespan=3600)


async def verify_clerk_token(authorization: str = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ", 1)[1]
    try:
        signing_key = await asyncio.to_thread(_jwks_client.get_signing_key_from_jwt, token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=CLERK_ISSUER,
            options={"require": ["exp", "iat", "iss", "sub"]},
            leeway=5,
        )
    except jwt.PyJWKClientConnectionError:
        logger.info("Clerk JWKS fetch failed (possible outage)")
        raise HTTPException(status_code=503, detail="Authentication temporarily unavailable")
    except jwt.PyJWTError as exc:
        logger.info("Rejected Clerk token: %s", exc)
        raise HTTPException(status_code=401, detail="Not authenticated")
    azp = payload.get("azp")
    if azp and azp not in CLERK_AUTHORIZED_PARTIES:
        logger.info("Rejected Clerk token: azp=%s", azp)
        raise HTTPException(status_code=401, detail="Not authenticated")
    return payload


async def optional_clerk(authorization: str = Header(default=None)) -> Optional[dict]:
    """Viewer identity for public pages. Never fails the request: a missing,
    invalid or expired token simply means an anonymous viewer."""
    if not authorization:
        return None
    try:
        return await verify_clerk_token(authorization)
    except HTTPException:
        return None


def _role(payload: dict) -> Optional[str]:
    return (payload.get("metadata") or {}).get("role")


def require_role(*roles: str):
    async def _dep(payload: dict = Depends(verify_clerk_token)) -> dict:
        if _role(payload) not in roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return payload
    return _dep


require_artist = require_role("artist", "admin")
require_admin = require_role("admin")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(text: str) -> str:
    text = re.sub(r'[^\w\s-]', '', text.lower().strip())
    return re.sub(r'[\s_-]+', '_', text)[:80].strip('_')


async def _set_status(submission_id: str, status: str, extra: Optional[dict] = None,
                      match: Optional[dict] = None) -> int:
    fields: dict = {"status": status, "status_updated_at": datetime.now(timezone.utc).isoformat()}
    if extra:
        fields.update(extra)
    if isinstance(fields.get("error"), str):
        fields["error"] = fields["error"][:500]
    filter_doc: dict = {"id": submission_id}
    if match:
        filter_doc.update(match)
    result = await db.track_submissions.update_one(filter_doc, {"$set": fields})
    return result.matched_count


async def _run_clearance(submission_id: str) -> None:
    """PRD-03 section 5. Evaluate a sync-consented track and store the result.
    Never raises: a clearance error must not break the pipeline or a callback."""
    try:
        doc = await db.track_submissions.find_one({"id": submission_id}, {"_id": 0})
        if not doc:
            return
        result = evaluate_clearance(doc)
        if result is None:
            return
        now = datetime.now(timezone.utc).isoformat()
        fields = {
            "checks": result["checks"],
            "sync_status": result["sync_status"],
            "clearance_evaluated_at": now,
        }
        if (result["sync_status"] == "cleared"
                and not doc.get("on_sync_profile")
                and not doc.get("sync_delisted_by_admin")):
            fields["on_sync_profile"] = True
            fields["sync_listed_at"] = now
        await db.track_submissions.update_one({"id": submission_id}, {"$set": fields})
        logger.info("Clearance submission=%s sync_status=%s", submission_id, result["sync_status"])
    except Exception as exc:
        logger.error("Clearance evaluation failed for %s: %s", submission_id, exc)


async def _claim_next() -> Optional[dict]:
    now = datetime.now(timezone.utc).isoformat()
    return await db.track_submissions.find_one_and_update(
        {"status": "uploaded"},
        {
            "$set": {
                "status": "scanning",
                "status_updated_at": now,
                "claimed_by": INSTANCE_ID,
                "claimed_at": now,
            },
            "$inc": {"attempts": 1},
        },
        sort=[("upload_date", 1)],
        return_document=ReturnDocument.AFTER,
    )


async def _worker_loop() -> None:
    logger.info("Worker started instance=%s", INSTANCE_ID)
    while True:
        try:
            doc = await _claim_next()
            if doc is None:
                await asyncio.sleep(WORKER_POLL_INTERVAL)
                continue
            await _process_stems(
                doc["id"],
                doc["original_r2_path"],
                doc["artist_name"],
                doc["track_name"],
            )
        except Exception as exc:
            logger.error("worker_loop unhandled error: %s", exc)
            await asyncio.sleep(WORKER_POLL_INTERVAL)


async def _run_sweeper() -> None:
    logger.info("Sweeper started instance=%s", INSTANCE_ID)
    while True:
        await asyncio.sleep(SWEEPER_INTERVAL)
        try:
            now = datetime.now(timezone.utc)

            # 1. Stale local jobs: "scanning" or "mastering" with no status update in STALE_LOCAL_MIN.
            stale_local_cutoff = (now - timedelta(minutes=STALE_LOCAL_MIN)).isoformat()
            stale_local = await db.track_submissions.find({
                "status": {"$in": ["scanning", "mastering"]},
                "status_updated_at": {"$lt": stale_local_cutoff},
            }, {"_id": 0, "id": 1, "status": 1, "status_updated_at": 1, "attempts": 1}).to_list(100)

            for doc in stale_local:
                attempts = doc.get("attempts") or 0
                matched_status = doc.get("status")
                matched_ts = doc.get("status_updated_at")
                if attempts >= 2:
                    logger.error(
                        "sweeper: pipeline_timeout id=%s status=%s attempts=%d"
                        " — marking failed, no retry",
                        doc["id"], matched_status, attempts,
                    )
                    await db.track_submissions.update_one(
                        {"id": doc["id"], "status": matched_status, "status_updated_at": matched_ts},
                        {"$set": {"status": "failed", "error": "pipeline_timeout",
                                  "status_updated_at": now.isoformat()}},
                    )
                else:
                    logger.warning(
                        "sweeper: resetting stale local job id=%s status=%s attempts=%d",
                        doc["id"], matched_status, attempts,
                    )
                    await db.track_submissions.update_one(
                        {"id": doc["id"], "status": matched_status, "status_updated_at": matched_ts},
                        {"$set": {"status": "uploaded", "status_updated_at": now.isoformat()}},
                    )

            # 2. Stale Modal jobs: "processing" (= awaiting Modal callback) older than STALE_MODAL_MIN.
            #    NOT re-dispatched: re-dispatch charges another GPU run and, if callbacks are broken
            #    systemically (wrong STEM_WEBHOOK_SECRET or STEM_CALLBACK_URL), every job would retry
            #    forever. Fail loudly; re-trigger manually after diagnosing why the callback never arrived.
            #    "$exists: true" excludes pre-1b legacy documents at "processing" with no modal_dispatched_at.
            stale_modal_cutoff = (now - timedelta(minutes=STALE_MODAL_MIN)).isoformat()
            stale_modal = await db.track_submissions.find({
                "status": "processing",
                "modal_dispatched_at": {"$exists": True, "$lt": stale_modal_cutoff},
            }, {"_id": 0, "id": 1, "status": 1, "status_updated_at": 1, "modal_dispatched_at": 1}).to_list(100)

            for doc in stale_modal:
                logger.error(
                    "sweeper: stem_callback_timeout id=%s dispatched_at=%s"
                    " — marking failed, no retry;"
                    " check STEM_WEBHOOK_SECRET and STEM_CALLBACK_URL before re-triggering manually",
                    doc["id"], doc.get("modal_dispatched_at"),
                )
                await db.track_submissions.update_one(
                    {"id": doc["id"], "status": doc.get("status"),
                     "status_updated_at": doc.get("status_updated_at")},
                    {"$set": {"status": "failed", "error": "stem_callback_timeout",
                              "status_updated_at": now.isoformat()}},
                )

            # 3. OQ-10: abandoned pending uploads.
            #    Presigned URL expires after 30 min; still "pending" after ABANDON_PENDING_HOURS means
            #    the upload was never completed. Mark failed, log the orphaned R2 key for the manual
            #    cleanup script. Does NOT delete from R2 -- see scripts/cleanup_orphaned_r2.py.
            abandon_cutoff = (now - timedelta(hours=ABANDON_PENDING_HOURS)).isoformat()
            abandoned = await db.track_submissions.find({
                "status": "pending",
                "upload_date": {"$lt": abandon_cutoff},
            }, {"_id": 0, "id": 1, "upload_date": 1, "original_r2_path": 1}).to_list(100)

            for doc in abandoned:
                logger.info(
                    "sweeper: abandoned_upload id=%s orphaned_r2_key=%s",
                    doc["id"], doc.get("original_r2_path"),
                )
                await db.track_submissions.update_one(
                    {"id": doc["id"], "status": "pending", "upload_date": doc.get("upload_date")},
                    {"$set": {"status": "failed", "error": "abandoned_upload",
                              "status_updated_at": now.isoformat()}},
                )

        except Exception as exc:
            logger.error("sweeper error: %s", exc)


async def _lalal_upload(audio_data: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    content_type = AUDIO_CONTENT_TYPES.get(ext, "audio/mpeg")
    headers = {
        "Authorization": "license " + str(LALAL_API_KEY),
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": content_type,
    }
    async with httpx.AsyncClient(timeout=180.0) as http:
        resp = await http.post(f"{LALAL_BASE}/upload/", content=audio_data, headers=headers)
        resp.raise_for_status()
        logger.info("lalal upload response: %s", resp.json())
        return resp.json()["id"]


async def _lalal_split(file_id: str, stem: str) -> tuple:
    """Returns (stem_url, back_url). Polls until processing finishes."""
    auth = {"Authorization": "license " + str(LALAL_API_KEY)}
    params_json = json.dumps([{"id": file_id, "stem": stem, "splitter": "phoenix"}])
    async with httpx.AsyncClient(timeout=30.0) as http:
        resp = await http.post(
            f"{LALAL_BASE}/split/",
            data={"params": params_json},
            headers=auth,
        )
        resp.raise_for_status()
        logger.info("lalal split response: %s", resp.json())

        for _ in range(72):  # poll up to 12 minutes
            await asyncio.sleep(10)
            check = await http.post(
                f"{LALAL_BASE}/check/",
                data={"id": file_id},
                headers=auth,
            )
            check.raise_for_status()
            data = check.json()
            logger.info("lalal check response: %s", data)
            if data.get("status") == "error":
                raise RuntimeError(f"Lalal.ai error: {data.get('error', 'unknown')}")
            result = data.get("result", {}).get(file_id, {})
            state = result.get("task", {}).get("state")
            if state == "error":
                raise RuntimeError(f"Lalal.ai task error for {file_id}")
            if state == "success":
                split = result.get("split", {})
                return split.get("stem_track"), split.get("back_track")

    raise RuntimeError("Lalal.ai processing timed out after 12 minutes")


async def _download(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=180.0, follow_redirects=True) as http:
        resp = await http.get(url)
        resp.raise_for_status()
        return resp.content


async def _r2_get(key: str) -> bytes:
    def _blocking():
        return r2_client.get_object(Bucket=R2_BUCKET, Key=key)["Body"].read()
    return await asyncio.to_thread(_blocking)


async def _r2_put(key: str, data: bytes, content_type: str) -> None:
    def _blocking():
        r2_client.put_object(Bucket=R2_BUCKET, Key=key, Body=data, ContentType=content_type)
    await asyncio.to_thread(_blocking)


async def _r2_download_to(key: str, local_path: str) -> None:
    await asyncio.to_thread(r2_client.download_file, R2_BUCKET, key, local_path)


async def _master_track(submission_id: str, r2_key: str) -> str:
    """
    Downloads raw track from R2, masters it with Matchering,
    uploads mastered WAV to R2, returns the mastered R2 key.
    """
    import matchering as mg

    # Matchering always writes 24-bit PCM WAV (mg.pcm24 below), so the mastered
    # key must carry a .wav suffix regardless of the source container. Deriving it
    # from the source extension produced e.g. mastered/{id}.mp3 holding WAV bytes —
    # which also propagated into the Modal worker, where src_ext is read straight
    # off this key to name the local temp file. Legacy documents keep their old
    # keys; every consumer reads the stored value rather than rebuilding it.
    _mastered_key   = r2_key.replace("/original/", "/mastered/")
    mastered_r2_key = str(PurePosixPath(_mastered_key).with_suffix(".wav"))

    # Reference track bundled in the repo
    reference_path = os.path.join(os.path.dirname(__file__), "reference", "default.wav")

    with tempfile.TemporaryDirectory() as tmpdir:
        raw_path = os.path.join(tmpdir, "input.wav")
        mastered_path = os.path.join(tmpdir, "mastered.wav")

        # 1. Download raw file from R2
        await _r2_download_to(r2_key, raw_path)

        # 2. Run Matchering in a thread (CPU-bound)
        def _run_matchering():
            mg.process(
                target=raw_path,
                reference=reference_path,
                results=[mg.pcm24(mastered_path)],
            )

        await asyncio.to_thread(_run_matchering)

        # 3. Upload mastered file to R2
        def _check_mastered_overwrite():
            try:
                r2_client.head_object(Bucket=R2_BUCKET, Key=mastered_r2_key)
                return True
            except ClientError as exc:
                if exc.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                    return False
                raise

        if await asyncio.to_thread(_check_mastered_overwrite):
            raise RuntimeError(f"Refusing to overwrite existing object {mastered_r2_key}")

        await asyncio.to_thread(
            r2_client.upload_file,
            mastered_path,
            R2_BUCKET,
            mastered_r2_key,
            ExtraArgs={"ContentType": "audio/wav"},
        )

    return mastered_r2_key


async def _process_stems(submission_id: str, r2_key: str, artist_name: str, track_name: str) -> None:
    try:
        # Status is already "scanning" — set atomically by _claim_next before this runs.
        ext = Path(r2_key).suffix
        with tempfile.TemporaryDirectory() as scan_dir:
            scan_path = os.path.join(scan_dir, f"scan{ext}")
            await _r2_download_to(r2_key, scan_path)

            # ffprobe before ACR — invalid or overlong files never reach ACRCloud.
            # Raises RuntimeError("file_rejected_format"), caught by the outer except.
            MAX_TRACK_SECONDS = int(os.environ.get("MAX_TRACK_SECONDS", "900"))

            def _ffprobe() -> float:
                result = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "json", scan_path],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode != 0:
                    raise RuntimeError("file_rejected_format")
                dur = json.loads(result.stdout).get("format", {}).get("duration")
                if dur is None or float(dur) > MAX_TRACK_SECONDS:
                    raise RuntimeError("file_rejected_format")
                return float(dur)

            duration_s = await asyncio.to_thread(_ffprobe)
            acr_result = await asyncio.to_thread(acrcloud_check.scan_file, scan_path)

        acr_status = acr_result["status"]
        logger.info("ACRCloud result submission=%s status=%s", submission_id, acr_status)

        # PRD-03 section 5 check 2 needs the scan result kept after `status` moves on.
        scan_fields = {
            "fingerprint_result": acr_status,
            "metadata.duration_s": round(duration_s, 2),
        }

        if acr_status != "CLEARED":
            extra = {f: acr_result[f] for f in ("matched_title", "matched_artist",
                     "matched_label", "matched_isrc", "confidence", "acrid", "raw_code")
                     if acr_result.get(f) is not None}
            extra.update(scan_fields)
            await _set_status(submission_id, acr_status, extra)
            await _run_clearance(submission_id)
            return

        await _set_status(submission_id, "mastering", scan_fields)
        mastered_r2_key = await _master_track(submission_id, r2_key)
        await _set_status(submission_id, "mastering", {"mastered_r2_key": mastered_r2_key})

        safe_artist = _slugify(artist_name)
        safe_track = _slugify(track_name)
        if not safe_artist or not safe_track:
            raise RuntimeError(
                f"Refusing dispatch: blank slug "
                f"(artist_name={artist_name!r}, track_name={track_name!r})"
            )

        stem_engine = os.environ.get("STEM_ENGINE", "modal")
        if stem_engine == "modal":
            fn = modal.Function.from_name(MODAL_APP, MODAL_FN)
            # fn.spawn is a synchronous HTTP call; wrap in to_thread to avoid blocking the event loop.
            await asyncio.to_thread(
                fn.spawn,
                submission_id,
                mastered_r2_key,
                safe_artist,
                safe_track,
            )
            await _set_status(submission_id, "processing",
                               {"modal_dispatched_at": datetime.now(timezone.utc).isoformat()})
            logger.info("Dispatched to Modal submission=%s", submission_id)
            return

        # LALAL path — status stays "mastering" through stem separation.
        # "processing" is not written here; it means Modal dispatch only.
        audio_data = await _r2_get(mastered_r2_key)
        filename = Path(r2_key).name
        lalal_file_id = await _lalal_upload(audio_data, filename)
        logger.info("Lalal.ai upload complete, file_id=%s submission=%s", lalal_file_id, submission_id)

        stem_paths: dict = {}

        # Stem pairs: (local label, lalal stem name)
        stems = [("vocals", "vocals"), ("drums", "drum"), ("bass", "bass")]

        for label, lalal_stem in stems:
            logger.info("Processing stem=%s for submission=%s", label, submission_id)
            stem_url, back_url = await _lalal_split(lalal_file_id, lalal_stem)

            if stem_url:
                data = await _download(stem_url)
                key = f"catalog/{safe_artist}/{safe_track}/stems/{label}.mp3"
                await _r2_put(key, data, "audio/mpeg")
                stem_paths[label] = key

            # The "other" stem = instrumental (no-vocals back track)
            if label == "vocals" and back_url:
                data = await _download(back_url)
                key = f"catalog/{safe_artist}/{safe_track}/stems/other.mp3"
                await _r2_put(key, data, "audio/mpeg")
                stem_paths["other"] = key

        await _set_status(submission_id, "completed", {"stem_paths": stem_paths})
        logger.info("Stem processing completed for submission=%s", submission_id)

    except Exception as exc:
        logger.error("Stem processing failed for submission=%s: %s", submission_id, exc)
        await _set_status(submission_id, "failed", {"error": str(exc)})


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ContactSubmissionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr
    company: Optional[str] = Field(default=None, max_length=160)
    interest: Optional[str] = Field(default=None, max_length=60)
    message: str = Field(..., min_length=1, max_length=4000)
    website: str = Field(default="")


class ContactSubmission(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    email: str
    company: Optional[str] = None
    interest: Optional[str] = None
    message: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


VALID_GENRES = {
    "Hip-Hop", "R&B", "Afrobeats", "Trap", "Soul", "Pop",
    "Electronic", "Latin", "Reggaeton", "Afropop", "Other",
}


class ArtistCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr
    spotify_url: str = Field(..., min_length=1, max_length=300)
    genre: str
    bio: str = Field(..., min_length=1, max_length=2000)
    website: str = Field(default="")

    @field_validator('genre')
    @classmethod
    def validate_genre(cls, v: str) -> str:
        if v not in VALID_GENRES:
            raise ValueError(f'genre must be one of: {", ".join(sorted(VALID_GENRES))}')
        return v


class Artist(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    email: str
    spotify_url: str
    genre: str
    bio: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tracks: List[dict] = []


def _one_of(value, allowed, label):
    if value not in allowed:
        raise ValueError(f"Invalid {label}.")
    return value


class SyncIntake(BaseModel):
    model_config = ConfigDict(extra="forbid")

    samples: str
    samples_attested: bool
    distributor: str
    content_id: str
    pro_not_affiliated: bool = False
    pro_name: Optional[str] = None
    ipi: Optional[str] = None

    @field_validator("samples")
    @classmethod
    def _samples(cls, v):
        return _one_of(v, SAMPLE_DECLARATIONS, "samples declaration")

    @field_validator("samples_attested")
    @classmethod
    def _attested(cls, v):
        if not v:
            raise ValueError("Confirm the samples declaration to use sync.")
        return v

    @field_validator("distributor")
    @classmethod
    def _distributor(cls, v):
        return _one_of(v, DISTRIBUTORS, "distributor")

    @field_validator("content_id")
    @classmethod
    def _content_id(cls, v):
        return _one_of(v, CONTENT_ID_ANSWERS, "Content ID answer")

    @model_validator(mode="after")
    def _pro_rules(self):
        if self.pro_not_affiliated:
            if self.pro_name or self.ipi:
                raise ValueError("Leave PRO and IPI empty when not affiliated.")
        else:
            _one_of(self.pro_name, PRO_ORGS, "PRO")
            if not self.ipi or not re.fullmatch(IPI_PATTERN, self.ipi):
                raise ValueError("IPI must be 9 or 11 digits.")
        return self


class PresignRequest(BaseModel):
    artist_name: str = Field(..., min_length=1, max_length=120)
    track_name: str = Field(..., min_length=1, max_length=120)
    genre: str
    filename: str = Field(..., min_length=1, max_length=200)
    file_size: int = Field(..., gt=0)
    pro_registered: bool = False
    pro_org: str = ''
    pro_register_us: bool = False
    consent_ai_training: bool = False
    consent_sync: bool = False
    moods: List[str]                        # required, no default
    vocals: str                             # required, no default
    sync_intake: Optional[SyncIntake] = None
    rights: Optional[TrackRightsIn] = None
    bpm: Optional[float] = None
    bpm_unsure: bool = False
    key: Optional[str] = None
    key_unsure: bool = False

    @field_validator("moods")
    @classmethod
    def _moods(cls, v):
        if not 1 <= len(v) <= MAX_MOODS:
            raise ValueError("Pick 1 to 3 moods.")
        if len(set(v)) != len(v):
            raise ValueError("Moods must not repeat.")
        for m in v:
            _one_of(m, MOODS, "mood")
        return v

    @field_validator("vocals")
    @classmethod
    def _vocals(cls, v):
        return _one_of(v, VOCALS, "vocals value")

    @field_validator("bpm")
    @classmethod
    def _bpm(cls, v):
        if v is None:
            return v
        if not BPM_MIN <= v <= BPM_MAX:
            raise ValueError(f"BPM must be between {BPM_MIN} and {BPM_MAX}.")
        return round(float(v), 1)

    @field_validator("key")
    @classmethod
    def _key(cls, v):
        if v is None:
            return v
        return _one_of(v, MUSICAL_KEYS, "key")

    @model_validator(mode="after")
    def _consent_rules(self):
        if not (self.consent_ai_training or self.consent_sync):
            raise ValueError("Choose at least one use for this upload.")
        if self.consent_sync and self.sync_intake is None:
            raise ValueError("Sync details are required when sync is selected.")
        if not self.consent_sync and self.sync_intake is not None:
            raise ValueError("Sync details were sent without sync consent.")
        if self.rights is None:
            raise ValueError("Add the splits for this upload.")
        if self.bpm is None and not self.bpm_unsure:
            raise ValueError("Enter the BPM or choose I'm unsure.")
        if self.bpm is not None and self.bpm_unsure:
            raise ValueError("Choose a BPM or I'm unsure, not both.")
        if self.key is None and not self.key_unsure:
            raise ValueError("Enter the key or choose I'm unsure.")
        if self.key is not None and self.key_unsure:
            raise ValueError("Choose a key or I'm unsure, not both.")
        return self


class VaultMetadataPatch(BaseModel):
    """PRD-03 4.4 / 9: artist edits from the Vault. A BPM or key sent here is
    the artist's confirmed value."""
    model_config = ConfigDict(extra="forbid")

    bpm: Optional[float] = None
    key: Optional[str] = None
    moods: Optional[List[str]] = None
    genre: Optional[str] = None

    @field_validator("bpm")
    @classmethod
    def _bpm(cls, v):
        if v is None:
            return v
        if not BPM_MIN <= v <= BPM_MAX:
            raise ValueError(f"BPM must be between {BPM_MIN} and {BPM_MAX}.")
        return round(float(v), 1)

    @field_validator("key")
    @classmethod
    def _key(cls, v):
        return v if v is None else _one_of(v, MUSICAL_KEYS, "key")

    @field_validator("moods")
    @classmethod
    def _moods(cls, v):
        if v is None:
            return v
        if not 1 <= len(v) <= MAX_MOODS:
            raise ValueError("Pick 1 to 3 moods.")
        if len(set(v)) != len(v):
            raise ValueError("Moods must not repeat.")
        for m in v:
            _one_of(m, MOODS, "mood")
        return v

    @field_validator("genre")
    @classmethod
    def _genre(cls, v):
        return v if v is None else _one_of(v, VALID_GENRES, "genre")

    @model_validator(mode="after")
    def _something(self):
        if self.bpm is None and self.key is None and self.moods is None and self.genre is None:
            raise ValueError("Nothing to change.")
        return self


CONSENT_SCOPES = ("ai_training", "sync", "exclusive_buyout")
CONSENT_ACTIONS = ("grant", "withdraw")


class ConsentChange(BaseModel):
    """PRD-03 3.4 / 4.2: add or remove a use from the Vault."""
    model_config = ConfigDict(extra="forbid")

    scope: str
    action: str
    sync_intake: Optional[SyncIntake] = None

    @field_validator("scope")
    @classmethod
    def _scope(cls, v):
        return _one_of(v, CONSENT_SCOPES, "use")

    @field_validator("action")
    @classmethod
    def _action(cls, v):
        return _one_of(v, CONSENT_ACTIONS, "action")

    @model_validator(mode="after")
    def _intake_rule(self):
        adding_sync = self.scope == "sync" and self.action == "grant"
        if adding_sync and self.sync_intake is None:
            raise ValueError("Sync details are required to add sync.")
        if not adding_sync and self.sync_intake is not None:
            raise ValueError("Sync details are only sent when adding sync.")
        return self


_BAD_TEXT = re.compile(r"[\x00-\x1f\x7f]|\{\{|\}\}")


class AgreementFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: Literal["individual", "company"]
    legal_name: str = Field(..., max_length=120)
    artist_name: str = Field(default="", max_length=80)
    company_name: str = Field(default="", max_length=120)
    signer_title: str = Field(default="", max_length=80)
    address_line1: str = Field(..., max_length=120)
    address_line2: str = Field(default="", max_length=120)
    city: str = Field(..., max_length=80)
    region: str = Field(default="", max_length=80)
    postal_code: str = Field(default="", max_length=20)
    country: str = Field(..., max_length=80)
    adult_confirmed: bool

    @field_validator("legal_name", "artist_name", "company_name", "signer_title", "address_line1",
                     "address_line2", "city", "region", "postal_code", "country")
    @classmethod
    def _clean(cls, v):
        # Check the raw value for control characters and braces before collapsing
        # whitespace, otherwise a newline would be folded into a space and slip past.
        if _BAD_TEXT.search(v):
            raise ValueError("Remove special characters from this field.")
        return " ".join(v.split())

    @model_validator(mode="after")
    def _rules(self):
        for name in ("legal_name", "address_line1", "city", "country"):
            if not getattr(self, name):
                raise ValueError("Fill in your legal name, street address, city and country.")
        if not self.adult_confirmed:
            raise ValueError("You must be 18 or older to sign.")
        if self.entity_type == "company":
            if not (self.company_name and self.signer_title):
                raise ValueError("Enter the company name and your title.")
        elif self.company_name or self.signer_title:
            raise ValueError("Company name and title are only for company signers.")
        return self


class AgreementSignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: AgreementFields
    text_sha256: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    typed_signature: str = Field(..., max_length=120)
    consent_electronic: bool
    agreed: bool

    @model_validator(mode="after")
    def _checks(self):
        if not self.consent_electronic:
            raise ValueError("Agree to sign electronically to continue.")
        if not self.agreed:
            raise ValueError("Confirm you have read and agree to the agreement.")
        return self


class SyncProfileUpdate(BaseModel):
    """PRD-03 4.3 / 11. Photo arrives in Phase 4b."""
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(..., max_length=80)
    bio: str = Field(default="", max_length=500)
    location: str = Field(default="", max_length=80)
    spotify_url: str = Field(default="", max_length=300)
    instagram_url: str = Field(default="", max_length=300)

    @field_validator("display_name")
    @classmethod
    def _name(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Enter a display name.")
        return v

    @field_validator("bio", "location")
    @classmethod
    def _strip(cls, v):
        return v.strip()

    @field_validator("spotify_url")
    @classmethod
    def _spotify(cls, v):
        v = v.strip()
        if v and not SPOTIFY_ARTIST_URL.match(v):
            raise ValueError("Use your Spotify artist link (https://open.spotify.com/artist/...).")
        return v

    @field_validator("instagram_url")
    @classmethod
    def _instagram(cls, v):
        v = v.strip()
        if v and not INSTAGRAM_URL.match(v):
            raise ValueError("Use your Instagram profile link (https://instagram.com/...).")
        return v


class PhotoPresignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content_type: str
    file_size: int = Field(..., gt=0)

    @field_validator("content_type")
    @classmethod
    def _type(cls, v):
        if v not in PHOTO_CONTENT_TYPES:
            raise ValueError("Use a JPEG, PNG or WebP image.")
        return v

    @field_validator("file_size")
    @classmethod
    def _size(cls, v):
        if v > MAX_PHOTO_BYTES:
            raise ValueError("Photo must be 10 MB or smaller.")
        return v


class PhotoCompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    upload_id: str = Field(..., min_length=1, max_length=64)


class CheckoutRequest(BaseModel):
    """PRD-03 7.2 step 2. No price field: the server computes it (decision 27)."""
    model_config = ConfigDict(extra="forbid")
    track_id: str = Field(min_length=1, max_length=64)
    tier: Literal["creator", "digital", "campaign", "broadcast"]
    term: Optional[Literal["1y", "2y", "3y", "5y", "perpetual"]] = None
    territory: Optional[str] = None
    include_stems: bool = False
    buyer_name: str = Field(min_length=1, max_length=120)
    buyer_company: str = Field(default="", max_length=120)
    buyer_email: EmailStr
    project_name: str = Field(min_length=1, max_length=120)
    project_client: str = Field(default="", max_length=120)
    accept_terms: bool
    terms_version: str = Field(min_length=1, max_length=32)

    @field_validator("buyer_name", "buyer_company")
    @classmethod
    def _strip(cls, v: str) -> str:
        return " ".join(v.split())

    @field_validator("project_name", "project_client")
    @classmethod
    def _clean_project(cls, v: str, info) -> str:
        v = " ".join(v.split())
        if _BAD_TEXT.search(v):
            raise ValueError("Remove special characters from this field.")
        if info.field_name == "project_name" and not v:
            raise ValueError("Name the project this license is for.")
        return v

    @model_validator(mode="after")
    def _scope_rules(self):
        needs_term = self.tier in ("campaign", "broadcast")
        if needs_term and self.term is None:
            raise ValueError("Choose a term.")
        if not needs_term and self.term is not None:
            raise ValueError("Term is only for Campaign and Broadcast.")
        if self.term == "perpetual" and self.tier != "campaign":
            raise ValueError("Perpetual is available only for Campaign.")
        if self.tier == "broadcast":
            if not self.territory:
                raise ValueError("Choose a territory.")
            if self.territory not in COUNTRIES:
                raise ValueError("Unknown territory.")
        elif self.territory is not None:
            raise ValueError("Territory is only for Broadcast.")
        return self


class SubscribeRequest(BaseModel):
    """Brief 19. Only the plan id and interval cross the wire; the price lives in Stripe."""
    model_config = ConfigDict(extra="forbid")
    plan: Literal["creator", "pro", "business"]
    interval: Literal["month", "year"]


class RegisterRequest(BaseModel):
    """Register (license) one track under the signed-in user's subscription."""
    model_config = ConfigDict(extra="forbid")
    track_id: str = Field(min_length=1, max_length=64)
    include_stems: bool = False
    project_name: str = Field(min_length=1, max_length=120)
    project_client: str = Field(default="", max_length=120)
    accept_terms: bool
    terms_version: str = Field(min_length=1, max_length=32)

    @field_validator("project_name", "project_client")
    @classmethod
    def _clean_project(cls, v: str, info) -> str:
        v = " ".join(v.split())
        if _BAD_TEXT.search(v):
            raise ValueError("Remove special characters from this field.")
        if info.field_name == "project_name" and not v:
            raise ValueError("Name the project this license is for.")
        return v


class QuoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["enterprise", "buyout"]
    track_id: Optional[str] = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    company: str = Field(default="", max_length=120)
    email: EmailStr
    use: Literal["Exclusive buyout", "National TV campaign", "Feature film", "Game", "Other"]
    territory: str = Field(default="", max_length=120)
    term: str = Field(default="", max_length=120)
    budget: Literal["Under $5,000", "$5,000 to $25,000", "$25,000 to $100,000", "Over $100,000"]
    details: str = Field(default="", max_length=2000)
    website: str = Field(default="", max_length=200)   # honeypot; must stay empty

    @field_validator("name", "company", "territory", "term")
    @classmethod
    def _clean_inline(cls, v: str) -> str:
        return quotes.clean(v, 120)

    @field_validator("details")
    @classmethod
    def _clean_details(cls, v: str) -> str:
        return quotes.clean_multiline(v, 2000)


class AdminReissue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    send_email: bool = True


class AdminDelist(BaseModel):
    model_config = ConfigDict(extra="forbid")
    delisted: bool = Field(..., strict=True)
    reason: str = Field(default="", max_length=500)


class AdminHideProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hidden: bool = Field(..., strict=True)
    reason: str = Field(default="", max_length=500)


PROFILE_PUBLIC_FIELDS = ("slug", "display_name", "bio", "location",
                         "spotify_url", "instagram_url", "created_at", "updated_at")


class CompleteUploadRequest(BaseModel):
    submission_id: str


class AppealPresignRequest(BaseModel):
    submission_id: str = Field(..., min_length=1, max_length=100)
    artist_name: str = Field(..., min_length=1, max_length=120)
    track_name: str = Field(..., min_length=1, max_length=120)
    filename: str = Field(..., min_length=1, max_length=200)
    message: Optional[str] = Field(default=None, max_length=2000)


class AppealCompleteRequest(BaseModel):
    appeal_id: str


class Appeal(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    submission_id: str
    clerk_user_id: Optional[str] = None
    artist_name: str
    track_name: str
    proof_r2_key: str = ""
    filename: str = ""
    message: Optional[str] = None
    status: str = "pending"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# PRD-03 3.6 / decision 13: ACRCloud match detail is never returned by any API.
# It is written by the pipeline and visible only in the database.
MATCH_DETAIL_FIELDS = ("matched_title", "matched_artist", "matched_label",
                       "matched_isrc", "confidence", "acrid", "raw_code")


class TrackSubmission(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    artist_name: str
    track_name: str
    genre: str
    original_r2_path: str = ""
    stem_paths: dict = {}
    upload_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "pending"
    error: Optional[str] = None
    pro_registered: bool = False
    pro_org: str = ''
    pro_register_us: bool = False
    clerk_user_id: Optional[str] = None
    matched_title: Optional[str] = None
    matched_artist: Optional[str] = None
    matched_label: Optional[str] = None
    matched_isrc: Optional[str] = None
    confidence: Optional[int] = None
    acrid: Optional[str] = None
    raw_code: Optional[int] = None
    expected_size: Optional[int] = None
    status_updated_at: Optional[datetime] = None
    claimed_by: Optional[str] = None
    claimed_at: Optional[datetime] = None
    attempts: int = 0
    modal_dispatched_at: Optional[datetime] = None
    consent: Optional[dict] = None
    consent_grant_version: Optional[str] = None
    metadata: Optional[dict] = None
    intake: Optional[dict] = None
    rights: Optional[dict] = None


# ---------------------------------------------------------------------------
# Existing routes
# ---------------------------------------------------------------------------

@api_router.get("/")
async def root():
    return {"message": "Hello World"}


# ---------------------------------------------------------------------------
# Contact / partnership form routes
# ---------------------------------------------------------------------------

@api_router.post("/contact", response_model=ContactSubmission, status_code=201)
@limiter.limit("5/minute")
async def create_contact_submission(request: Request, payload: ContactSubmissionCreate):
    if payload.website:
        logger.info("Honeypot triggered on /contact")
        return ContactSubmission(**payload.model_dump())
    submission = ContactSubmission(**payload.model_dump())
    doc = submission.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.contact_submissions.insert_one(doc)
    logger.info("New contact submission: %s (%s)", submission.email, submission.name)
    return submission


@api_router.get("/contact", response_model=List[ContactSubmission])
@limiter.limit("30/minute")
async def get_contact_submissions(request: Request, admin: dict = Depends(require_admin)):
    logger.info("admin_access user=%s path=%s", admin.get("sub"), request.url.path)
    submissions = await db.contact_submissions.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    for s in submissions:
        if isinstance(s.get('created_at'), str):
            s['created_at'] = datetime.fromisoformat(s['created_at'])
    return submissions


# ---------------------------------------------------------------------------
# Artist application routes
# ---------------------------------------------------------------------------

@api_router.post("/artists", response_model=Artist, status_code=201)
@limiter.limit("5/minute")
async def create_artist(request: Request, payload: ArtistCreate):
    if payload.website:
        logger.info("Honeypot triggered on /artists from %s", payload.email)
        return Artist(**payload.model_dump())
    existing = await db.artists.find_one({"email": payload.email}, {"_id": 0})
    if existing:
        logger.info("Duplicate artist application suppressed email=%s", payload.email)
        return Artist(**payload.model_dump())
    artist = Artist(**payload.model_dump())
    doc = artist.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.artists.insert_one(doc)
    logger.info("New artist application: %s (%s)", artist.email, artist.genre)
    return artist


@api_router.post("/artists/{email}/tracks")
async def upload_artist_tracks(email: str):
    raise HTTPException(status_code=410, detail="Track upload via this endpoint has been retired. Use the Upload page.")


@api_router.get("/artists")
@limiter.limit("30/minute")
async def get_artists(
    request: Request,
    admin: dict = Depends(require_admin),
):
    logger.info("admin_access user=%s path=%s", admin.get("sub"), request.url.path)
    artists = await db.artists.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    for artist in artists:
        if isinstance(artist.get('created_at'), str):
            artist['created_at'] = datetime.fromisoformat(artist['created_at'])
    return artists


# ---------------------------------------------------------------------------
# Artist Agreement
# ---------------------------------------------------------------------------

async def fetch_clerk_user(user_id: str) -> dict:
    """Primary email and name from Clerk's Backend API. Raises 503 on any failure."""
    if not CLERK_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Account lookup is not configured.")
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"https://api.clerk.com/v1/users/{quote(user_id, safe='')}",
                            headers={"Authorization": f"Bearer {CLERK_SECRET_KEY}"})
    except Exception as exc:
        logger.warning("Clerk user lookup failed: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Could not load your account. Please try again.")
    if r.status_code != 200:
        logger.warning("Clerk user lookup returned %s", r.status_code)
        raise HTTPException(status_code=503, detail="Could not load your account. Please try again.")
    u = r.json()
    primary = next((e for e in u.get("email_addresses", [])
                    if e.get("id") == u.get("primary_email_address_id")), None)
    email = (primary or {}).get("email_address")
    if not email:
        raise HTTPException(status_code=422, detail="Add an email address to your account first.")
    verified = ((primary or {}).get("verification") or {}).get("status") == "verified"
    return {"email": email, "first_name": u.get("first_name") or "", "last_name": u.get("last_name") or "",
            "email_verified": verified}


async def _current_agreement(uid: str) -> Optional[dict]:
    return await db.artist_agreements.find_one(
        {"user_id": uid, "version": artist_agreement.current_version()},
        {"_id": 0, "id": 1, "version": 1, "signed_at": 1})


async def _require_signed_agreement(clerk_payload: dict) -> Optional[dict]:
    """Agreement for the consent ledger, or None when not enforced or for admins."""
    if _role(clerk_payload) == "admin":
        return None
    a = await _current_agreement(clerk_payload["sub"])
    if a is None and artist_agreement.enforced():
        raise HTTPException(status_code=403, detail="Sign the Artist Agreement before uploading.")
    return a


def _agreement_values(fields: dict, *, email: str, uid: str, now: datetime) -> dict:
    return {
        "agreement_date": artist_agreement.agreement_date(now),
        "licensor_party": artist_agreement.licensor_party(fields),
        "licensor_email": email,
        "platform_account_id": uid,
    }


@api_router.get("/agreement/status")
@limiter.limit("30/minute")
async def agreement_status(request: Request, clerk_payload: dict = Depends(require_artist)):
    uid = clerk_payload["sub"]
    version = artist_agreement.current_version()
    signed = await _current_agreement(uid)
    resp = {
        "current_version": version,
        "enforced": artist_agreement.enforced(),
        "required": _role(clerk_payload) != "admin",
        "signed": signed is not None,
        "agreement": signed,
        "prefill": None,
        "previous_signed": await db.artist_agreements.find_one(
            {"user_id": uid, "version": {"$ne": version}}, {"_id": 1}) is not None,
        "buyouts_supported": artist_agreement.supports_buyouts(version),
    }
    if signed is None:
        resp["prefill"] = await _agreement_prefill(uid)
    return resp


async def _agreement_prefill(uid: str) -> dict:
    """Best effort. Never fails the status call."""
    saved = await db.artist_legal_profiles.find_one({"user_id": uid}, {"_id": 0, "user_id": 0, "updated_at": 0})
    if saved:
        return saved
    prefill = {"entity_type": "individual"}
    profile = await db.sync_profiles.find_one({"user_id": uid}, {"_id": 0, "display_name": 1})
    if profile and profile.get("display_name"):
        prefill["artist_name"] = profile["display_name"]
    try:
        u = await fetch_clerk_user(uid)
        full = f"{u['first_name']} {u['last_name']}".strip()
        if full:
            prefill["legal_name"] = full
        prefill["email"] = u["email"]
    except HTTPException:
        pass
    return prefill


@api_router.post("/agreement/preview")
@limiter.limit("20/minute")
async def agreement_preview(request: Request, payload: AgreementFields,
                            clerk_payload: dict = Depends(require_artist)):
    uid = clerk_payload["sub"]
    version = artist_agreement.current_version()
    user = await fetch_clerk_user(uid)
    values = _agreement_values(payload.model_dump(), email=user["email"], uid=uid,
                               now=datetime.now(timezone.utc))
    text = artist_agreement.render_text(version, values)
    return {"version": version, "email": user["email"], "blocks": artist_agreement.blocks(text),
            "text_sha256": artist_agreement.text_sha256(text)}


@api_router.post("/agreement/sign")
@limiter.limit("5/minute")
async def agreement_sign(request: Request, payload: AgreementSignRequest,
                         clerk_payload: dict = Depends(require_artist)):
    uid = clerk_payload["sub"]
    version = artist_agreement.current_version()
    if await _current_agreement(uid):
        raise HTTPException(status_code=409, detail="You have already signed this agreement.")

    fields = payload.fields.model_dump()
    norm = lambda s: " ".join(s.split()).casefold()
    if norm(payload.typed_signature) != norm(fields["legal_name"]):
        raise HTTPException(status_code=422, detail="Type your full legal name exactly as entered above.")

    user = await fetch_clerk_user(uid)
    now = datetime.now(timezone.utc)
    text = artist_agreement.render_text(version, _agreement_values(fields, email=user["email"], uid=uid, now=now))
    text_hash = artist_agreement.text_sha256(text)
    if text_hash != payload.text_sha256:
        # Fields or the date changed since preview (e.g. preview before midnight UTC, sign after).
        raise HTTPException(status_code=409, detail="The agreement changed. Please review it again.")

    agreement_id = str(uuid.uuid4())
    signed_at = now.isoformat()
    ip = get_real_client_ip(request)
    sig = {"agreement_id": agreement_id, "version": version, "text_sha256": text_hash,
           "signed_at": signed_at, "typed_signature": " ".join(payload.typed_signature.split()),
           "licensor_email": user["email"], "platform_account_id": uid, "ip": ip, "fields": fields}
    pdf = await asyncio.to_thread(artist_agreement.render_pdf, text, sig)
    pdf_key = f"agreements/{uid}/{agreement_id}.pdf"
    try:
        await asyncio.to_thread(r2_client.put_object, Bucket=R2_BUCKET, Key=pdf_key, Body=pdf,
                                ContentType="application/pdf")
    except Exception as exc:
        logger.error("Agreement PDF upload failed for %s: %s", agreement_id, exc)
        raise HTTPException(status_code=503, detail="Could not save your agreement. Please try again.")

    doc = {
        "id": agreement_id, "user_id": uid, "version": version,
        "text_sha256": text_hash, "pdf_sha256": hashlib.sha256(pdf).hexdigest(), "pdf_key": pdf_key,
        "fields": fields, "licensor_email": user["email"],
        "licensor_party": artist_agreement.licensor_party(fields),
        "typed_signature": sig["typed_signature"], "consent_electronic": True, "agreed": True,
        "signed_at": signed_at, "ip": ip,
        "user_agent": (request.headers.get("user-agent") or "")[:300],
    }
    try:
        await db.artist_agreements.insert_one(doc)
    except DuplicateKeyError:
        # Double submit: the unique (user_id, version) index kept the first one.
        raise HTTPException(status_code=409, detail="You have already signed this agreement.")
    except Exception as exc:
        # The PDF in R2 is now an orphan. Harmless, and the key is logged for cleanup.
        logger.error("Agreement record insert failed for %s (orphan %s): %s", agreement_id, pdf_key, exc)
        raise HTTPException(status_code=503, detail="Could not save your agreement. Please try again.")

    try:
        await db.artist_legal_profiles.update_one(
            {"user_id": uid}, {"$set": {**fields, "updated_at": signed_at}}, upsert=True)
    except Exception as exc:
        logger.warning("Legal profile save failed for %s: %s", uid, exc)

    subject, html, body = artist_agreement.agreement_email(
        name=fields["legal_name"], signed_date=now.strftime("%B %d, %Y"))
    result = await send_email(to=user["email"], subject=subject, html=html, text=body,
                              attachments=[("oVoxi-Artist-Agreement.pdf", pdf)],
                              idempotency_key=f"agreement-{agreement_id}")
    logger.info("Agreement %s email: %s", agreement_id, result["status"])

    return {"agreement": {"id": agreement_id, "version": version, "signed_at": signed_at}}


@api_router.get("/agreement/pdf")
@limiter.limit("20/minute")
async def agreement_pdf(request: Request, clerk_payload: dict = Depends(require_artist)):
    doc = await db.artist_agreements.find_one(
        {"user_id": clerk_payload["sub"]}, {"_id": 0, "pdf_key": 1}, sort=[("signed_at", -1)])
    if not doc:
        raise HTTPException(status_code=404, detail="No signed agreement found.")
    url = await asyncio.to_thread(
        r2_client.generate_presigned_url, "get_object",
        Params={"Bucket": R2_BUCKET, "Key": doc["pdf_key"],
                "ResponseContentDisposition": 'attachment; filename="oVoxi-Artist-Agreement.pdf"'},
        ExpiresIn=300)
    return {"url": url}


# ---------------------------------------------------------------------------
# Upload pipeline routes
# ---------------------------------------------------------------------------

@api_router.post("/upload/presign")
@limiter.limit("5/minute")
async def presign_upload(request: Request, payload: PresignRequest, clerk_payload: dict = Depends(require_artist)):
    if os.environ.get("UPLOADS_ENABLED", "true") != "true":
        raise HTTPException(status_code=503, detail="Uploads are temporarily paused")
    agreement = await _require_signed_agreement(clerk_payload)
    if payload.genre not in VALID_GENRES:
        raise HTTPException(status_code=400, detail=f"Invalid genre")

    ext = Path(payload.filename).suffix.lower()
    if ext not in AUDIO_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Only MP3 or WAV files are accepted")
    if payload.file_size > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit",
        )

    if _role(clerk_payload) != "admin":
        MAX_UPLOADS_PER_DAY = int(os.environ.get("MAX_UPLOADS_PER_DAY", "20"))
        MAX_OPEN_SUBMISSIONS = int(os.environ.get("MAX_OPEN_SUBMISSIONS", "5"))
        uid = clerk_payload["sub"]
        since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        if await db.track_submissions.count_documents(
            {"clerk_user_id": uid, "upload_date": {"$gte": since}}
        ) >= MAX_UPLOADS_PER_DAY:
            raise HTTPException(status_code=429, detail="Daily upload limit reached")
        if await db.track_submissions.count_documents({
            "clerk_user_id": uid,
            "$or": [
                {"status": {"$in": ["uploaded", "scanning", "mastering", "processing"]}},
                {"status": "pending", "upload_date": {"$gte": one_hour_ago}},
            ],
        }) >= MAX_OPEN_SUBMISSIONS:
            raise HTTPException(status_code=429, detail="Too many uploads in progress")

    submission_id = str(uuid.uuid4())
    safe_artist = _slugify(payload.artist_name)
    safe_track = _slugify(payload.track_name)
    if not safe_artist or not safe_track:
        raise HTTPException(status_code=400, detail="Artist and track names must contain at least one letter or number")
    content_type = AUDIO_CONTENT_TYPES[ext]
    r2_key = f"catalog/{safe_artist}/{safe_track}/original/{submission_id}{ext}"

    def _presign():
        return r2_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": R2_BUCKET,
                "Key": r2_key,
                "ContentType": content_type,
                "ContentLength": payload.file_size,
            },
            # 1800s: bounded by upload time for MAX_UPLOAD_BYTES on a slow connection, not security preference.
            ExpiresIn=1800,
        )

    try:
        presigned_url = await asyncio.to_thread(_presign)
    except Exception as exc:
        logger.error("Failed to generate presigned URL: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to generate upload URL")

    clerk_user_id = clerk_payload.get('sub')
    now_iso = datetime.now(timezone.utc).isoformat()
    scopes = []
    if payload.consent_ai_training:
        scopes.append("ai_training")
    if payload.consent_sync:
        scopes.append("sync")
    try:
        await record_grants(
            db, user_id=clerk_user_id, track_id=submission_id, scopes=scopes,
            source="upload", ip=get_real_client_ip(request), agreement=agreement,
        )
    except Exception as exc:
        logger.error("Consent ledger write failed for %s: %s", submission_id, exc)
        raise HTTPException(status_code=503, detail="Could not record consent. Please try again.")

    submission = TrackSubmission(
        id=submission_id,
        artist_name=payload.artist_name,
        track_name=payload.track_name,
        genre=payload.genre,
        original_r2_path=r2_key,
        status='pending',
        pro_registered=payload.pro_registered,
        pro_org=payload.pro_org,
        pro_register_us=payload.pro_register_us,
        clerk_user_id=clerk_user_id,
    )
    doc = submission.model_dump()
    doc['upload_date'] = doc['upload_date'].isoformat()
    doc['expected_size'] = payload.file_size
    doc['consent'] = {"ai_training": payload.consent_ai_training, "sync": payload.consent_sync}
    doc['consent_grant_version'] = GRANT_VERSION
    doc['agreement_id'] = agreement["id"] if agreement else None
    doc['metadata'] = {
        "moods": payload.moods,
        "vocals": payload.vocals,
        "bpm": payload.bpm,
        "bpm_source": "artist" if payload.bpm is not None else None,
        "bpm_unsure": payload.bpm_unsure,
        "key": payload.key,
        "key_source": "artist" if payload.key is not None else None,
        "key_unsure": payload.key_unsure,
    }
    if payload.consent_sync:
        doc['intake'] = {
            "samples": payload.sync_intake.samples,
            "samples_attested_at": now_iso,
            "distributor": payload.sync_intake.distributor,
            "content_id": payload.sync_intake.content_id,
            "pro_not_affiliated": payload.sync_intake.pro_not_affiliated,
            "pro_name": payload.sync_intake.pro_name,
            "ipi": payload.sync_intake.ipi,
        }
    else:
        doc.pop('intake', None)
    doc['rights'] = build_rights(
        payload.rights, intake=payload.sync_intake,
        clerk_user_id=clerk_user_id, now_iso=now_iso,
    )
    await db.track_submissions.insert_one(doc)

    return {
        "presigned_url": presigned_url,
        "submission_id": submission_id,
        "r2_key": r2_key,
        "content_type": content_type,
    }


@api_router.post("/upload/complete")
@limiter.limit("5/minute")
async def complete_upload(request: Request, payload: CompleteUploadRequest, clerk_payload: dict = Depends(require_artist)):
    if os.environ.get("UPLOADS_ENABLED", "true") != "true":
        raise HTTPException(status_code=503, detail="Uploads are temporarily paused")
    sub = await db.track_submissions.find_one({"id": payload.submission_id}, {"_id": 0})
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if sub.get("clerk_user_id") != clerk_payload.get("sub"):
        raise HTTPException(status_code=403, detail="Not your submission")
    if sub["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Submission status is already '{sub['status']}'")

    def _head():
        return r2_client.head_object(Bucket=R2_BUCKET, Key=sub["original_r2_path"])

    try:
        head = await asyncio.to_thread(_head)
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
            raise HTTPException(status_code=400, detail="Upload not found")
        raise

    content_length = head.get("ContentLength", 0)
    expected = sub.get("expected_size")
    if content_length > MAX_UPLOAD_BYTES or (expected is not None and content_length != expected):
        try:
            await asyncio.to_thread(
                r2_client.delete_object, Bucket=R2_BUCKET, Key=sub["original_r2_path"]
            )
        except Exception as del_exc:
            logger.warning("Failed to delete rejected R2 object: %s", del_exc)
        await _set_status(payload.submission_id, "failed", {"error": "file_rejected_size"})
        raise HTTPException(status_code=400, detail="File exceeds size limit")

    await _set_status(payload.submission_id, "uploaded")
    logger.info("Queued for processing submission=%s", payload.submission_id)
    return {"status": "uploaded", "submission_id": payload.submission_id}


@api_router.get('/vault/tracks')
@limiter.limit("30/minute")
async def get_vault_tracks(request: Request, clerk_payload: dict = Depends(verify_clerk_token)):
    clerk_user_id = clerk_payload.get('sub')
    subs = await db.track_submissions.find(
        {'clerk_user_id': clerk_user_id},
        {'_id': 0, 'id': 1, 'artist_name': 1, 'track_name': 1, 'genre': 1,
         'upload_date': 1, 'status': 1, 'stem_paths': 1, 'mastered_r2_key': 1,
         'consent': 1, 'metadata': 1, 'sync_status': 1, 'checks': 1, 'on_sync_profile': 1},
    ).sort('upload_date', -1).to_list(1000)

    def _presign_get(key: str) -> str:
        return r2_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': R2_BUCKET, 'Key': key},
            ExpiresIn=3600,
        )

    result = []
    for s in subs:
        upload_date = s.get('upload_date')
        if isinstance(upload_date, str):
            upload_date = datetime.fromisoformat(upload_date)
        stem_urls = {}
        if s.get('stem_paths'):
            try:
                stem_urls = {
                    stem: await asyncio.to_thread(_presign_get, key)
                    for stem, key in s['stem_paths'].items()
                }
            except Exception:
                pass
        mastered_url = None
        if s.get('mastered_r2_key'):
            try:
                mastered_url = await asyncio.to_thread(_presign_get, s['mastered_r2_key'])
            except Exception:
                pass
        result.append({
            'id': s.get('id'),
            'artist_name': s.get('artist_name'),
            'track_name': s.get('track_name'),
            'genre': s.get('genre'),
            'upload_date': upload_date,
            'status': s.get('status'),
            'stem_urls': stem_urls,
            'mastered_url': mastered_url,
            **vault_track_view(s),
        })
    return result


# ---------------------------------------------------------------------------
# Vault: artist edits and consent changes (PRD-03 Phase 4a)
# ---------------------------------------------------------------------------

async def _owned_track(track_id: str, clerk_payload: dict) -> dict:
    """The artist's own track, or 404 (never reveals whether another artist's exists)."""
    doc = await db.track_submissions.find_one(
        {"id": track_id, "clerk_user_id": clerk_payload["sub"]},
        {"_id": 0, **{f: 0 for f in MATCH_DETAIL_FIELDS}},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Track not found")
    if is_legacy(doc):
        raise HTTPException(status_code=409, detail="This track was uploaded before usage options.")
    return doc


@api_router.patch("/vault/tracks/{track_id}/metadata")
@limiter.limit("30/minute")
async def patch_vault_metadata(request: Request, track_id: str, payload: VaultMetadataPatch,
                               clerk_payload: dict = Depends(require_artist)):
    await _owned_track(track_id, clerk_payload)
    fields = metadata_patch_fields(payload.bpm, payload.key, payload.moods, payload.genre)
    await db.track_submissions.update_one(
        {"id": track_id, "clerk_user_id": clerk_payload["sub"]}, {"$set": fields})
    await _run_clearance(track_id)
    doc = await _owned_track(track_id, clerk_payload)
    return {"id": track_id, "genre": doc.get("genre"), **vault_track_view(doc)}


@api_router.post("/vault/tracks/{track_id}/consent")
@limiter.limit("10/minute")
async def change_vault_consent(request: Request, track_id: str, payload: ConsentChange,
                               clerk_payload: dict = Depends(require_artist)):
    doc = await _owned_track(track_id, clerk_payload)
    want = payload.action == "grant"
    if (doc["consent"].get(payload.scope) is True) == want:
        label = {"ai_training": "AI training", "sync": "Sync",
                 "exclusive_buyout": "Exclusive buyout"}.get(payload.scope, payload.scope)
        raise HTTPException(status_code=409, detail=f"{label} is already {'on' if want else 'off'}.")

    # PRD-03 3.4: every change is a new consent event, written first. Grants are gated;
    # withdrawals never are, so an artist can always opt out.
    if payload.scope == "exclusive_buyout" and want:
        # Brief 16 section 4.2: three gates, in order. The signed-agreement check
        # applies even when enforcement is off.
        if doc["consent"].get("sync") is not True:
            raise HTTPException(status_code=409, detail="Turn on sync placements first.")
        agreement = await _current_agreement(clerk_payload["sub"])
        if agreement is None:
            raise HTTPException(status_code=403, detail="Sign the latest Artist Agreement first.")
        if not artist_agreement.supports_buyouts(artist_agreement.current_version()):
            raise HTTPException(status_code=409, detail="Exclusive buyouts are not available yet.")
    else:
        agreement = await _require_signed_agreement(clerk_payload) if want else None

    # Withdrawing sync also withdraws buyouts (one ledger write) when buyouts were on.
    cascade_buyout = (payload.scope == "sync" and not want
                      and doc["consent"].get("exclusive_buyout") is True)
    try:
        if want:
            await record_grants(db, user_id=clerk_payload["sub"], track_id=track_id,
                                 scopes=[payload.scope], source="vault",
                                 ip=get_real_client_ip(request), agreement=agreement)
        else:
            scopes = ["sync", "exclusive_buyout"] if cascade_buyout else [payload.scope]
            await record_withdrawals(db, user_id=clerk_payload["sub"], track_id=track_id,
                                     scopes=scopes, source="vault",
                                     ip=get_real_client_ip(request))
    except Exception as exc:
        logger.error("Consent ledger write failed for %s: %s", track_id, exc)
        raise HTTPException(status_code=503, detail="Could not record consent. Please try again.")

    now_iso = datetime.now(timezone.utc).isoformat()
    fields: dict = {f"consent.{payload.scope}": want}
    if payload.scope == "sync" and want:
        i = payload.sync_intake
        fields["intake"] = {
            "samples": i.samples, "samples_attested_at": now_iso,
            "distributor": i.distributor, "content_id": i.content_id,
            "pro_not_affiliated": i.pro_not_affiliated, "pro_name": i.pro_name, "ipi": i.ipi,
        }
    elif payload.scope == "sync":
        # Delisted for future sales; licenses already sold stay valid.
        fields.update({"on_sync_profile": False, "sync_delisted_at": now_iso,
                       "sync_status": None, "checks": None})
        if cascade_buyout:
            fields["consent.exclusive_buyout"] = False
    await db.track_submissions.update_one(
        {"id": track_id, "clerk_user_id": clerk_payload["sub"]}, {"$set": fields})
    if payload.scope == "sync" and want:
        await _run_clearance(track_id)
    doc = await _owned_track(track_id, clerk_payload)
    return {"id": track_id, **vault_track_view(doc)}


# ---------------------------------------------------------------------------
# Sync profile (PRD-03 4.3). Public page arrives in Phase 4b.
# ---------------------------------------------------------------------------

def _photo_keys(base: str) -> dict:
    return {size: f"{base}-{size}.webp" for size in PHOTO_SIZES}


def _signed_get(key: str, ttl: int = 3600) -> str:
    return r2_client.generate_presigned_url(
        "get_object", Params={"Bucket": R2_BUCKET, "Key": key}, ExpiresIn=ttl)


async def _r2_delete_quietly(key: str) -> None:
    try:
        await asyncio.to_thread(r2_client.delete_object, Bucket=R2_BUCKET, Key=key)
    except Exception as exc:
        logger.warning("Could not delete R2 object %s: %s", key, exc)


def _profile_view(p: Optional[dict]) -> dict:
    if not p:
        return {}
    view = {k: p.get(k) for k in PROFILE_PUBLIC_FIELDS}
    view["photo_url"] = view["photo_thumb_url"] = None
    if p.get("photo_key"):
        keys = _photo_keys(p["photo_key"])
        try:
            view["photo_url"] = _signed_get(keys[800])
            view["photo_thumb_url"] = _signed_get(keys[200])
        except Exception as exc:
            logger.warning("Could not sign photo URLs: %s", exc)
    return view


@api_router.get("/sync/profile")
@limiter.limit("30/minute")
async def get_sync_profile(request: Request, clerk_payload: dict = Depends(require_artist)):
    p = await db.sync_profiles.find_one({"user_id": clerk_payload["sub"]}, {"_id": 0})
    return _profile_view(p)


@api_router.put("/sync/profile")
@limiter.limit("10/minute")
async def put_sync_profile(request: Request, payload: SyncProfileUpdate,
                           clerk_payload: dict = Depends(require_artist)):
    uid = clerk_payload["sub"]
    now_iso = datetime.now(timezone.utc).isoformat()
    fields = {**payload.model_dump(), "updated_at": now_iso}

    existing = await db.sync_profiles.find_one({"user_id": uid}, {"_id": 0, "slug": 1})
    if existing:
        await db.sync_profiles.update_one({"user_id": uid}, {"$set": fields})
    else:
        # Slug is set once from the display name and never changed by the artist.
        base = slugify_profile(payload.display_name) or "artist"
        for n in range(1, 51):
            slug = base if n == 1 else f"{base}-{n}"
            try:
                await db.sync_profiles.insert_one({
                    "user_id": uid, "slug": slug, **fields, "created_at": now_iso,
                    "sales_count": 0, "hidden_by_admin": False, "photo_key": None,
                })
                break
            except DuplicateKeyError as exc:
                if "user_id" in str(exc):  # created by a parallel request: update it instead
                    await db.sync_profiles.update_one({"user_id": uid}, {"$set": fields})
                    break
        else:
            raise HTTPException(status_code=503, detail="Could not save your profile. Please try again.")

    p = await db.sync_profiles.find_one({"user_id": uid}, {"_id": 0})
    return _profile_view(p)


# ---------------------------------------------------------------------------
# Public sync pages (PRD-03 6.2, 6.3; decisions 17, 18). Gated by
# SYNC_PUBLIC_PAGES_ENABLED; the owning artist and admins can always see them.
# Every "not visible" answer is a 404, so nothing reveals what exists.
# ---------------------------------------------------------------------------

MAX_WAVEFORM_BYTES = 200 * 1024
PREVIEW_URL_TTL = int(os.environ.get("SYNC_PREVIEW_URL_TTL_SECONDS", "300"))


def _public_pages_enabled() -> bool:
    return os.environ.get("SYNC_PUBLIC_PAGES_ENABLED", "false") == "true"


def _viewer(viewer: Optional[dict]) -> tuple:
    if not viewer:
        return None, False
    return viewer.get("sub"), _role(viewer) == "admin"


def _not_found():
    return HTTPException(status_code=404, detail="Not found")


async def _visible_track(track_id: str, viewer: Optional[dict]) -> tuple:
    """(track doc, profile or None, is_privileged) or 404."""
    doc = await db.track_submissions.find_one(
        {"id": track_id}, {"_id": 0, **{f: 0 for f in MATCH_DETAIL_FIELDS}})
    if not doc or (doc.get("consent") or {}).get("sync") is not True:
        raise _not_found()
    uid, is_admin = _viewer(viewer)
    privileged = is_admin or (uid is not None and uid == doc.get("clerk_user_id"))
    if not privileged and not (_public_pages_enabled() and is_listed(doc)):
        raise _not_found()
    profile = await db.sync_profiles.find_one({"user_id": doc.get("clerk_user_id")}, {"_id": 0})
    return doc, profile, privileged


def _public_profile_with_photo(profile: dict, show_hidden: bool) -> dict:
    view = public_profile_view(profile, show_hidden)
    view["photo_url"] = None
    if photo_visible(profile, show_hidden):
        try:
            view["photo_url"] = _signed_get(_photo_keys(profile["photo_key"])[800])
        except Exception as exc:
            logger.warning("Could not sign photo URL: %s", exc)
    return view


@api_router.get("/sync/artists/{slug}")
@limiter.limit("60/minute")
async def get_public_artist(request: Request, slug: str, viewer: Optional[dict] = Depends(optional_clerk)):
    profile = await db.sync_profiles.find_one({"slug": slug}, {"_id": 0})
    if not profile:
        raise _not_found()
    uid, is_admin = _viewer(viewer)
    is_owner = uid is not None and uid == profile.get("user_id")
    docs = await db.track_submissions.find(
        {"clerk_user_id": profile["user_id"], **LISTING_FILTER},
        {"_id": 0, **{f: 0 for f in MATCH_DETAIL_FIELDS}},
    ).sort("upload_date", -1).to_list(500)
    public = _public_pages_enabled() and len(docs) > 0
    if not (is_owner or is_admin or public):
        raise _not_found()
    return {
        "profile": _public_profile_with_photo(profile, show_hidden=is_admin),
        "tracks": [public_track_view(d, profile) for d in docs],
        "viewer": {"is_owner": is_owner, "is_admin": is_admin, "public": public},
    }


def _library_enabled() -> bool:
    return os.environ.get("SYNC_LIBRARY_ENABLED", "false") == "true"


@api_router.get("/sync/tracks")
@limiter.limit("60/minute")
async def search_library(request: Request, viewer: Optional[dict] = Depends(optional_clerk)):
    """The sync library (PRD-03 6.1). Admins always; everyone else only when
    SYNC_LIBRARY_ENABLED is exactly "true" (decision 21)."""
    _, is_admin = _viewer(viewer)
    if not (is_admin or _library_enabled()):
        raise _not_found()
    try:
        q = parse_params(request.query_params)
    except SearchParamError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Decision 22: Newest until the first paid sale exists, then Popular.
    sort = q.sort
    if sort is None:
        any_sale = await db.sync_profiles.find_one({"sales_count": {"$gt": 0}}, {"_id": 1})
        sort = "popular" if any_sale else "newest"

    rows = await db.track_submissions.aggregate(build_pipeline(q, sort)).to_list(PAGE_SIZE + 1)
    has_more = len(rows) > PAGE_SIZE
    rows = rows[:PAGE_SIZE]
    total = None
    if not q.cursor:
        total = await db.track_submissions.count_documents(build_filter(q))
    return {
        "tracks": [public_track_view(r, (r.get("_profiles") or [None])[0]) for r in rows],
        "next_cursor": encode_cursor(sort, rows[-1]) if has_more and rows else None,
        "sort": sort,
        "total": total,
        "viewer": {"is_admin": is_admin, "public": _library_enabled()},
    }


@api_router.get("/sync/tracks/{track_id}")
@limiter.limit("60/minute")
async def get_public_track(request: Request, track_id: str, viewer: Optional[dict] = Depends(optional_clerk)):
    doc, profile, privileged = await _visible_track(track_id, viewer)
    uid, is_admin = _viewer(viewer)
    return {
        "track": public_track_view(doc, profile),
        "artist": _public_profile_with_photo(profile, show_hidden=is_admin) if profile else None,
        "listed": is_listed(doc),
        "viewer": {"is_owner": privileged and not is_admin, "is_admin": is_admin,
                   "public": _public_pages_enabled() and is_listed(doc)},
    }


@api_router.get("/sync/tracks/{track_id}/waveform")
@limiter.limit("120/minute")
async def get_public_waveform(request: Request, track_id: str, viewer: Optional[dict] = Depends(optional_clerk)):
    doc, _, _ = await _visible_track(track_id, viewer)
    key = doc.get("waveform_key")
    if not key:
        raise _not_found()
    try:
        obj = await asyncio.to_thread(r2_client.get_object, Bucket=R2_BUCKET, Key=key)
        if (obj.get("ContentLength") or 0) > MAX_WAVEFORM_BYTES:
            raise ValueError("waveform too large")
        data = json.loads(await asyncio.to_thread(obj["Body"].read, MAX_WAVEFORM_BYTES + 1))
        peaks = data.get("peaks")
        if not isinstance(peaks, list) or len(peaks) > 5000:
            raise ValueError("bad waveform")
        peaks = [max(0.0, min(1.0, float(p))) for p in peaks]
    except Exception as exc:
        logger.warning("Waveform unavailable for %s: %s", track_id, exc)
        raise _not_found()
    return JSONResponse({"version": 1, "points": len(peaks), "peaks": peaks},
                        headers={"Cache-Control": "private, max-age=3600"})


@api_router.post("/sync/tracks/{track_id}/preview")
@limiter.limit("30/minute")
async def get_public_preview(request: Request, track_id: str, viewer: Optional[dict] = Depends(optional_clerk)):
    doc, _, _ = await _visible_track(track_id, viewer)
    key = doc.get("preview_key")
    if not key:
        raise _not_found()
    try:
        url = await asyncio.to_thread(
            r2_client.generate_presigned_url, "get_object",
            Params={"Bucket": R2_BUCKET, "Key": key, "ResponseContentDisposition": "inline",
                    "ResponseContentType": "audio/mpeg"},
            ExpiresIn=PREVIEW_URL_TTL,
        )
    except Exception as exc:
        logger.error("Preview sign failed for %s: %s", track_id, exc)
        raise HTTPException(status_code=503, detail="Preview unavailable. Please try again.")
    return {"url": url, "expires_in": PREVIEW_URL_TTL}


# ---------------------------------------------------------------------------
# Admin sync controls (PRD-03 9). Every action is appended to admin_actions.
# ---------------------------------------------------------------------------

async def _log_admin_action(admin: dict, action: str, target: str, reason: str) -> None:
    await db.admin_actions.insert_one({
        "admin_id": admin.get("sub"), "action": action, "target": target,
        "reason": reason, "created_at": datetime.now(timezone.utc).isoformat(),
    })


@api_router.post("/admin/sync/tracks/{track_id}/delist")
@limiter.limit("30/minute")
async def admin_delist_track(request: Request, track_id: str, payload: AdminDelist,
                             admin: dict = Depends(require_admin)):
    doc = await db.track_submissions.find_one({"id": track_id}, {"_id": 0, "id": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="Track not found")
    now_iso = datetime.now(timezone.utc).isoformat()
    if payload.delisted:
        fields = {"sync_delisted_by_admin": True, "on_sync_profile": False,
                  "sync_delisted_at": now_iso}
    else:
        fields = {"sync_delisted_by_admin": False}
    await db.track_submissions.update_one({"id": track_id}, {"$set": fields})
    await _log_admin_action(admin, "delist" if payload.delisted else "relist", track_id, payload.reason)
    if not payload.delisted:
        await _run_clearance(track_id)   # re-lists only if it still clears
    doc = await db.track_submissions.find_one(
        {"id": track_id}, {"_id": 0, "id": 1, "sync_status": 1, "on_sync_profile": 1,
                           "sync_delisted_by_admin": 1})
    return doc


@api_router.post("/admin/sync/profiles/{slug}/hide")
@limiter.limit("30/minute")
async def admin_hide_profile(request: Request, slug: str, payload: AdminHideProfile,
                             admin: dict = Depends(require_admin)):
    p = await db.sync_profiles.find_one({"slug": slug}, {"_id": 0, "slug": 1})
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")
    await db.sync_profiles.update_one({"slug": slug}, {"$set": {
        "hidden_by_admin": payload.hidden, "updated_at": datetime.now(timezone.utc).isoformat()}})
    await _log_admin_action(admin, "hide_profile" if payload.hidden else "unhide_profile",
                            slug, payload.reason)
    return {"slug": slug, "hidden_by_admin": payload.hidden}


@api_router.get("/admin/sync/profiles")
@limiter.limit("30/minute")
async def admin_list_profiles(request: Request, admin: dict = Depends(require_admin)):
    profiles = await db.sync_profiles.find(
        {}, {"_id": 0, "slug": 1, "display_name": 1, "hidden_by_admin": 1, "created_at": 1, "updated_at": 1},
    ).sort("created_at", -1).to_list(2000)
    return profiles


@api_router.post("/sync/profile/photo/presign")
@limiter.limit("10/minute")
async def presign_profile_photo(request: Request, payload: PhotoPresignRequest,
                                clerk_payload: dict = Depends(require_artist)):
    uid = clerk_payload["sub"]
    p = await db.sync_profiles.find_one({"user_id": uid}, {"_id": 0, "slug": 1})
    if not p:
        raise HTTPException(status_code=409, detail="Save your profile first.")
    upload_id = str(uuid.uuid4())
    key = f"profiles/{p['slug']}/incoming/{upload_id}"
    try:
        url = await asyncio.to_thread(
            r2_client.generate_presigned_url, "put_object",
            Params={"Bucket": R2_BUCKET, "Key": key, "ContentType": payload.content_type,
                    "ContentLength": payload.file_size},
            ExpiresIn=600,
        )
    except Exception as exc:
        logger.error("Photo presign failed: %s", exc)
        raise HTTPException(status_code=500, detail="Could not start the upload.")
    await db.sync_profiles.update_one({"user_id": uid}, {"$set": {"photo_pending": {
        "upload_id": upload_id, "key": key, "content_type": payload.content_type,
        "size": payload.file_size, "created_at": datetime.now(timezone.utc).isoformat(),
    }}})
    return {"presigned_url": url, "upload_id": upload_id, "content_type": payload.content_type}


@api_router.post("/sync/profile/photo/complete")
@limiter.limit("10/minute")
async def complete_profile_photo(request: Request, payload: PhotoCompleteRequest,
                                 clerk_payload: dict = Depends(require_artist)):
    uid = clerk_payload["sub"]
    p = await db.sync_profiles.find_one({"user_id": uid}, {"_id": 0})
    pending = (p or {}).get("photo_pending") or {}
    if not p or pending.get("upload_id") != payload.upload_id:
        raise HTTPException(status_code=404, detail="Upload not found.")
    incoming = pending["key"]
    try:
        try:
            head = await asyncio.to_thread(r2_client.head_object, Bucket=R2_BUCKET, Key=incoming)
            if head.get("ContentLength") != pending.get("size"):
                raise PhotoRejected(REJECT_MESSAGE)
            obj = await asyncio.to_thread(r2_client.get_object, Bucket=R2_BUCKET, Key=incoming)
            data = await asyncio.to_thread(obj["Body"].read)
            images = await asyncio.to_thread(process_photo, data)
        except PhotoRejected as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Photo processing failed for %s: %s", p.get("slug"), exc)
            raise HTTPException(status_code=422, detail=REJECT_MESSAGE)

        base = f"profiles/{p['slug']}/photo/{uuid.uuid4()}"
        keys = _photo_keys(base)
        for size, body in images.items():
            await asyncio.to_thread(r2_client.put_object, Bucket=R2_BUCKET, Key=keys[size],
                                    Body=body, ContentType="image/webp")
        await db.sync_profiles.update_one({"user_id": uid}, {
            "$set": {"photo_key": base, "updated_at": datetime.now(timezone.utc).isoformat()}})
        if p.get("photo_key"):
            for key in _photo_keys(p["photo_key"]).values():
                await _r2_delete_quietly(key)
    finally:
        # The original upload never stays in R2, whatever happened above.
        await _r2_delete_quietly(incoming)
        await db.sync_profiles.update_one({"user_id": uid}, {"$unset": {"photo_pending": ""}})

    p = await db.sync_profiles.find_one({"user_id": uid}, {"_id": 0})
    return _profile_view(p)


@api_router.delete("/sync/profile/photo")
@limiter.limit("10/minute")
async def delete_profile_photo(request: Request, clerk_payload: dict = Depends(require_artist)):
    uid = clerk_payload["sub"]
    p = await db.sync_profiles.find_one({"user_id": uid}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found.")
    if p.get("photo_key"):
        await db.sync_profiles.update_one({"user_id": uid}, {
            "$set": {"photo_key": None, "updated_at": datetime.now(timezone.utc).isoformat()}})
        for key in _photo_keys(p["photo_key"]).values():
            await _r2_delete_quietly(key)
    p = await db.sync_profiles.find_one({"user_id": uid}, {"_id": 0})
    return _profile_view(p)


@api_router.get("/submissions")
@limiter.limit("30/minute")
async def get_submissions(request: Request, admin: dict = Depends(require_admin)):
    logger.info("admin_access user=%s path=%s", admin.get("sub"), request.url.path)
    subs = await db.track_submissions.find(
        {}, {"_id": 0, **{f: 0 for f in MATCH_DETAIL_FIELDS}}
    ).sort("upload_date", -1).to_list(1000)

    def _presign_get(key: str) -> str:
        return r2_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": R2_BUCKET, "Key": key},
            ExpiresIn=3600,
        )

    for s in subs:
        if isinstance(s.get("upload_date"), str):
            s["upload_date"] = datetime.fromisoformat(s["upload_date"])
        if s.get("stem_paths"):
            try:
                s["stem_urls"] = {
                    stem: await asyncio.to_thread(_presign_get, key)
                    for stem, key in s["stem_paths"].items()
                }
            except Exception as exc:
                logger.warning("Could not generate stem presigned URLs: %s", exc)
                s["stem_urls"] = {}
        if s.get("mastered_r2_key"):
            try:
                s["mastered_url"] = await asyncio.to_thread(_presign_get, s["mastered_r2_key"])
            except Exception as exc:
                logger.warning("Could not generate mastered presigned URL: %s", exc)
                s["mastered_url"] = None
    return subs


# ---------------------------------------------------------------------------
# Appeal routes
# ---------------------------------------------------------------------------

@api_router.post("/appeal/presign")
@limiter.limit("5/minute")
async def presign_appeal(
    request: Request,
    payload: AppealPresignRequest,
    clerk_payload: dict = Depends(verify_clerk_token),
):
    sub = await db.track_submissions.find_one({"id": payload.submission_id}, {"_id": 0})
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    clerk_user_id = clerk_payload.get("sub")
    if sub.get("clerk_user_id") != clerk_user_id:
        raise HTTPException(status_code=403, detail="Not your submission")
    if sub.get("status") != "CONFLICT":
        raise HTTPException(status_code=400, detail="Appeals can only be filed for tracks with a conflict status")

    ext = Path(payload.filename).suffix.lower()
    if ext not in PROOF_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Proof file must be PDF, JPG, PNG, DOC, or DOCX",
        )

    appeal_id = str(uuid.uuid4())
    orig_parts = sub.get("original_r2_path", "").split("/")
    if len(orig_parts) >= 3:
        track_folder = "/".join(orig_parts[:3])  # catalog/{safe_artist}/{safe_track}
    else:
        track_folder = f"catalog/{_slugify(payload.artist_name)}/{_slugify(payload.track_name)}"
    r2_key = f"{track_folder}/appeals/{appeal_id}{ext}"
    content_type = PROOF_CONTENT_TYPES[ext]

    def _presign():
        return r2_client.generate_presigned_url(
            "put_object",
            Params={"Bucket": R2_BUCKET, "Key": r2_key, "ContentType": content_type},
            ExpiresIn=3600,
        )

    try:
        presigned_url = await asyncio.to_thread(_presign)
    except Exception as exc:
        logger.error("Failed to generate appeal presigned URL: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to generate upload URL")

    appeal = Appeal(
        id=appeal_id,
        submission_id=payload.submission_id,
        clerk_user_id=clerk_user_id,
        artist_name=payload.artist_name,
        track_name=payload.track_name,
        filename=payload.filename,
        proof_r2_key=r2_key,
        message=payload.message,
        status="pending_upload",
    )
    doc = appeal.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.appeals.insert_one(doc)

    return {
        "presigned_url": presigned_url,
        "appeal_id": appeal_id,
        "r2_key": r2_key,
        "content_type": content_type,
    }


@api_router.post("/appeal/complete")
@limiter.limit("5/minute")
async def complete_appeal(
    request: Request,
    payload: AppealCompleteRequest,
    clerk_payload: dict = Depends(verify_clerk_token),
):
    appeal = await db.appeals.find_one({"id": payload.appeal_id}, {"_id": 0})
    if not appeal:
        raise HTTPException(status_code=404, detail="Appeal not found")
    clerk_user_id = clerk_payload.get("sub")
    if appeal.get("clerk_user_id") != clerk_user_id:
        raise HTTPException(status_code=403, detail="Not your appeal")
    if appeal["status"] != "pending_upload":
        raise HTTPException(status_code=400, detail=f"Appeal status is already '{appeal['status']}'")

    await db.appeals.update_one(
        {"id": payload.appeal_id},
        {"$set": {"status": "pending"}},
    )
    logger.info("Appeal submitted appeal=%s submission=%s", payload.appeal_id, appeal["submission_id"])
    return {"status": "pending", "appeal_id": payload.appeal_id}


@api_router.get("/appeals")
@limiter.limit("30/minute")
async def get_appeals(request: Request, admin: dict = Depends(require_admin)):
    logger.info("admin_access user=%s path=%s", admin.get("sub"), request.url.path)

    appeals = await db.appeals.find(
        {"status": {"$ne": "pending_upload"}}, {"_id": 0}
    ).sort("created_at", -1).to_list(1000)

    def _presign_get(key: str) -> str:
        return r2_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": R2_BUCKET, "Key": key},
            ExpiresIn=3600,
        )

    for a in appeals:
        if isinstance(a.get("created_at"), str):
            a["created_at"] = datetime.fromisoformat(a["created_at"])
        if a.get("proof_r2_key"):
            try:
                a["proof_url"] = await asyncio.to_thread(_presign_get, a["proof_r2_key"])
            except Exception as exc:
                logger.warning("Could not generate proof presigned URL: %s", exc)
                a["proof_url"] = None
    return appeals


@api_router.post("/internal/stems/callback")
async def stems_callback(request: Request):
    # Read the raw body before JSON-parsing. The HMAC is computed over the
    # exact bytes received; parsing and re-serializing would produce different
    # bytes and every hmac.compare_digest call would fail silently.
    body = await request.body()
    sig_header = request.headers.get("X-Ovoxi-Signature", "")
    secret = os.environ.get("STEM_WEBHOOK_SECRET", "")
    if not secret:
        raise HTTPException(status_code=500, detail="STEM_WEBHOOK_SECRET not configured")
    expected = "sha256=" + hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, sig_header):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = json.loads(body)
    sid    = payload.get("submission_id")
    status = payload.get("status")
    ts     = payload.get("ts")

    if not sid:
        raise HTTPException(status_code=400, detail="Missing submission_id")
    if not isinstance(ts, (int, float)):
        raise HTTPException(status_code=400, detail="Missing or invalid timestamp")
    if abs(time.time() - ts) > CALLBACK_TIMESTAMP_TOLERANCE:
        raise HTTPException(status_code=400, detail="Request timestamp too old")
    if status not in ("completed", "failed"):
        raise HTTPException(status_code=400, detail=f"Unknown status: {status!r}")

    doc = await db.track_submissions.find_one(
        {"id": sid}, {"_id": 0, "status": 1, "original_r2_path": 1, "metadata": 1}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Submission not found")
    if doc["status"] != "processing":
        logger.warning(
            "Callback for %s: doc status=%s (expected processing) — ignored",
            sid, doc["status"],
        )
        return {"ok": True}

    if status == "completed":
        stem_paths = payload.get("stem_paths")
        if not isinstance(stem_paths, dict):
            raise HTTPException(status_code=400, detail="stem_paths must be an object")
        unknown_keys = set(stem_paths.keys()) - KNOWN_STEM_NAMES
        if unknown_keys:
            raise HTTPException(status_code=400,
                                detail=f"Unknown stem name(s): {sorted(unknown_keys)}")

        r2_path = doc.get("original_r2_path", "")
        parts = r2_path.split("/")
        if len(parts) < 4:
            raise HTTPException(status_code=400,
                                detail="Submission has malformed original_r2_path")
        # original_r2_path: catalog/{artist}/{track}/original/{id}{ext}
        expected_prefix = f"{parts[0]}/{parts[1]}/{parts[2]}/stems/{sid}/"
        for key in stem_paths.values():
            if not key.startswith(expected_prefix):
                raise HTTPException(status_code=400,
                                    detail="stem_paths key outside expected prefix")

        extra: dict = {
            "stem_paths":          stem_paths,
            "stem_schema_version": payload.get("stem_schema_version", 2),
        }
        if "source_sample_rate" in payload:
            extra["source_sample_rate"] = payload["source_sample_rate"]
        # Stem storage format, recorded explicitly so the catalog is
        # self-describing for licensees. "wav24" from schema v3 onward;
        # absent on v1 (LALAL pcm_s24le) and v2 (MP3 320) documents.
        if "stem_format" in payload:
            extra["stem_format"] = payload["stem_format"]

        # PRD-03 phase 3 fields. Optional, and never a reason to reject the
        # callback: a 400 here would leave the track stuck in "processing"
        # (the worker does not retry). Anything invalid is logged and dropped.
        preview_base = f"{parts[0]}/{parts[1]}/{parts[2]}/previews/{sid}"
        for field, suffix in (("preview_key", ".mp3"), ("waveform_key", ".waveform.json")):
            value = payload.get(field)
            if value is None:
                continue
            if value == preview_base + suffix:
                extra[field] = value
            else:
                logger.error("Callback %s: %s outside expected path, dropped", sid, field)

        bpm_detected = None
        bpm = payload.get("bpm")
        if bpm is not None:
            if isinstance(bpm, (int, float)) and not isinstance(bpm, bool) and BPM_MIN <= bpm <= BPM_MAX:
                bpm_detected = round(float(bpm), 1)
            else:
                logger.warning("Callback %s: bpm %r out of range, dropped", sid, bpm)

        key_detected = None
        key = payload.get("key")
        if key is not None:
            if key in MUSICAL_KEYS:
                key_detected = key
                conf = payload.get("key_confidence")
                if isinstance(conf, (int, float)) and not isinstance(conf, bool) and 0 <= conf <= 1:
                    extra["metadata.key_detected_confidence"] = float(conf)
            else:
                logger.warning("Callback %s: key %r not recognised, dropped", sid, key)

        # PRD-03 4.4: the artist's answer wins; detection only confirms or holds it.
        extra.update(reconcile_metadata(doc.get("metadata") or {}, bpm_detected, key_detected))
        matched = await _set_status(sid, "completed", extra, match={"status": "processing"})
        if matched == 0:
            logger.warning("Callback completed for %s but document no longer processing — ignored", sid)
        else:
            logger.info("Stem callback completed submission=%s", sid)
            await _run_clearance(sid)

    else:  # failed
        matched = await _set_status(
            sid, "failed",
            {"error": payload.get("error", "Unknown failure")},
            match={"status": "processing"},
        )
        if matched == 0:
            logger.warning("Callback failed for %s but document no longer processing — ignored", sid)
        else:
            logger.error("Stem callback failed submission=%s error=%s", sid, payload.get("error"))

    return {"ok": True}


# ---------------------------------------------------------------------------
# Sync checkout (PRD-03 Phase 6)
# ---------------------------------------------------------------------------

@api_router.get("/sync/checkout/config")
@limiter.limit("60/minute")
async def sync_checkout_config(request: Request, viewer: Optional[dict] = Depends(optional_clerk)):
    """Prices, stems and terms for the license modal; {"can_checkout": false} otherwise."""
    _, is_admin = _viewer(viewer)
    cfg = sync_orders.checkout_config(is_admin=is_admin, terms_text=LICENSE_TERMS)
    if cfg.get("can_checkout"):
        # subscriptions_enabled is true only with the flag set AND all six prices resolved (13a).
        # Warm the price cache here while it is empty (13b); on failure log ERROR and report false.
        enabled = sync_orders.subscriptions_enabled()
        if enabled and not subscriptions.prices_ready():
            try:
                await asyncio.to_thread(subscriptions.ensure_prices, sync_orders.stripe_client())
            except Exception as exc:
                logger.error("subscription price load from config failed: %s", exc)
        enabled = enabled and subscriptions.prices_ready()
        cfg["subscriptions_enabled"] = enabled
        if enabled:
            now_iso = datetime.now(timezone.utc).isoformat()
            plans = []
            for pid, p in PLANS.items():
                # Plan scope shown in the license pop-up, from the same license_scope the certificate
                # uses (one source of truth). media_summary/term_label are static for sub_* types.
                scope = licenses.license_scope(licenses.SUB_TYPES[pid], now_iso)
                plans.append({
                    "id": pid, "label": p["label"], "month_cents": p["month_cents"],
                    "year_cents": p["year_cents"], "month_cap": p["month_cap"], "day_cap": SUB_DAY_CAP,
                    # Server-computed loyalty monthly prices (15% from month 3, 20% from 7) so the
                    # client never does discount math; one formula via loyalty_price_cents.
                    "month_cents_loyalty15": subscriptions.loyalty_price_cents(p["month_cents"], 15),
                    "month_cents_loyalty20": subscriptions.loyalty_price_cents(p["month_cents"], 20),
                    "scope_summary": scope["media_summary"], "term_label": scope["term_label"],
                })
            cfg["plans"] = plans
    return cfg


@api_router.get("/sync/terms/{version}")
@limiter.limit("60/minute")
async def sync_terms(request: Request, version: str):
    """Public License Terms blocks for a version. Not behind the public-pages flag."""
    blocks = LICENSE_TERMS.get(version)
    if not blocks:
        raise HTTPException(status_code=404, detail="Unknown terms version")
    return {"version": version, "blocks": blocks}


@api_router.post("/sync/quotes")
@limiter.limit("5/hour")
async def sync_quote(request: Request, payload: QuoteRequest):
    """Enterprise and buyout quote requests. Stored, then emailed to QUOTE_INBOX."""
    if payload.website:                      # honeypot filled: pretend success, discard
        return {"ok": True}
    now = datetime.now(timezone.utc)
    track = None
    if payload.track_id:
        track = await db.track_submissions.find_one(
            {"id": payload.track_id}, {"_id": 0, **{f: 0 for f in MATCH_DETAIL_FIELDS}})
    if payload.kind == "buyout":
        if (not track or not is_listed(track)
                or (track.get("consent") or {}).get("exclusive_buyout") is not True):
            raise HTTPException(status_code=409, detail="Exclusive buyout is not offered for this track.")
    q = quotes.build_quote(payload.model_dump(), ip=get_real_client_ip(request),
                           user_agent=request.headers.get("user-agent") or "", track=track, now=now)
    try:
        await db.quote_requests.insert_one(dict(q))
    except Exception as exc:
        logger.error("quote store failed: %s", exc)
        raise HTTPException(status_code=503, detail="Could not send your request. Please try again.")
    subject, html, text = quote_email(q)
    result = await send_email(to=quotes.quote_inbox(), subject=subject, html=html, text=text,
                              reply_to=payload.email)
    if result["status"] == "failed":
        logger.error("quote email failed id=%s: %s", q["id"], result.get("error"))
    return {"ok": True}


@api_router.post("/sync/checkout")
@limiter.limit("10/minute")
async def sync_checkout(request: Request, payload: CheckoutRequest,
                        viewer: Optional[dict] = Depends(optional_clerk)):
    """Create a pending order and a Stripe Checkout Session; return the Stripe URL."""
    _, is_admin = _viewer(viewer)
    try:
        if not sync_orders.can_checkout(is_admin):
            raise HTTPException(status_code=403, detail="Licensing is not available yet")
        sync_orders.token_secret()  # fail before charging anyone if delivery could not work
        test_mode = sync_orders.is_test_key()
        current_terms = sync_orders.terms_version()
    except sync_orders.ConfigError as exc:
        logger.error("checkout config error: %s", exc)
        raise HTTPException(status_code=503, detail="Licensing is temporarily unavailable")

    if not payload.accept_terms:
        raise HTTPException(status_code=422, detail="You must accept the license terms")
    if payload.terms_version != current_terms:
        raise HTTPException(status_code=409, detail="The license terms have changed. Reload and review them.")

    track = await db.track_submissions.find_one(
        {"id": payload.track_id}, {"_id": 0, **{f: 0 for f in MATCH_DETAIL_FIELDS}})
    if not track or not is_listed(track):
        raise _not_found()
    profile = await db.sync_profiles.find_one({"user_id": track.get("clerk_user_id")}, {"_id": 0})
    now = datetime.now(timezone.utc)
    include_stems = payload.include_stems and sync_orders.deliver_stems()
    try:
        order = sync_orders.build_order(
            track=track, tier=payload.tier, term=payload.term, territory=payload.territory,
            include_stems=include_stems,
            buyer_name=payload.buyer_name, buyer_company=payload.buyer_company,
            buyer_email=str(payload.buyer_email), test_mode=test_mode, now=now,
            track_title=track.get("track_name") or "",
            artist_display_name=(profile or {}).get("display_name") or track.get("artist_name") or "",
            project_name=payload.project_name, project_client=payload.project_client)
        params = sync_orders.checkout_session_params(order, now=now)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except sync_orders.ConfigError as exc:
        logger.error("checkout config error: %s", exc)
        raise HTTPException(status_code=503, detail="Licensing is temporarily unavailable")

    await db.orders.insert_one(dict(order))
    try:
        client = sync_orders.stripe_client()
        session = await asyncio.to_thread(
            client.v1.checkout.sessions.create, params, {"idempotency_key": f"checkout-{order['order_id']}"})
    except Exception as exc:
        logger.error("stripe session create failed order=%s error=%s", order["order_id"], exc)
        await sync_orders.mark_failed(db, order["order_id"], now=now)
        raise HTTPException(status_code=502, detail="Could not start checkout. Please try again.")

    await db.orders.update_one({"order_id": order["order_id"]}, {"$set": {"stripe_session_id": session.id}})
    logger.info("checkout order=%s track=%s tier=%s stems=%s test=%s",
                order["order_id"], order["track_id"], order["tier"], order["include_stems"], test_mode)
    return {"checkout_url": session.url, "order_id": order["order_id"]}


async def _render_license(order: dict, track_title: str, artist_name: str, lic: dict | None = None) -> bytes:
    verify_url = f"{sync_orders.site_url()}/verify/{order['license_id']}"
    return await asyncio.to_thread(render_license_pdf, order, track_title=track_title,
                                   artist_name=artist_name, license=lic, verify_url=verify_url)


async def _send_license_email(order: dict, pdf: bytes | None = None, *, reissued: bool = False,
                              idempotency_key: str | None = None) -> dict:
    """License email with the certificate attached. Test orders get a [TEST] subject.

    The default idempotency key blocks duplicate delivery emails for the same link version.
    A deliberate admin resend must pass its own unique key, or Resend treats it as a
    duplicate of the original and silently sends nothing (it keeps keys for 24 hours)."""
    token = sync_orders.current_token(order)
    if not token:
        return {"status": "failed", "id": None, "error": "order has no live download link"}
    if pdf is None:
        pdf = await _r2_get(order["license_pdf_key"])
    subject, html, text = license_email(order, download_url=f"{sync_orders.site_url()}/license/{token}",
                                        reissued=reissued)
    result = await send_email(
        to=order["buyer_email"], subject=subject, html=html, text=text,
        attachments=[(f"oVoxi-license-{order['license_id']}.pdf", pdf)],
        idempotency_key=idempotency_key or (
            f"license-{order['order_id']}-v{order.get('token_version')}" + ("-reissue" if reissued else "")))
    logger.info("license email order=%s status=%s error=%s", order["order_id"], result["status"], result.get("error"))
    return result


async def _fulfil_order(order_id: str) -> None:
    """Background delivery. Failures are logged; the order stays `paid` and is retried
    by a repeated webhook or by the success-page fallback."""
    try:
        status = await sync_orders.fulfil_order(db, order_id, render_pdf=_render_license, put_object=_r2_put,
                                                now=datetime.now(timezone.utc), send_license=_send_license_email,
                                                build_license=licenses.build_license_from_order)
        logger.info("fulfil order=%s status=%s", order_id, status)
    except Exception as exc:
        logger.error("fulfil failed order=%s error=%s", order_id, exc)


async def _reconcile_fulfilment(now: datetime) -> None:
    """One pass: re-run idempotent fulfilment for paid-but-unfulfilled orders. Delivery and
    the buyer email only ever happen through fulfil_order's normal path."""
    cutoff = (now - timedelta(minutes=FULFIL_MIN_AGE_MIN)).isoformat()
    stuck = await db.orders.find({
        "status": "paid",
        "paid_at": {"$lt": cutoff},
        "$or": [{"fulfil_attempts": {"$exists": False}}, {"fulfil_attempts": {"$lt": FULFIL_MAX_ATTEMPTS}}],
    }, {"_id": 0, "order_id": 1, "fulfil_attempts": 1}).sort("paid_at", 1).to_list(100)
    for doc in stuck:
        oid = doc["order_id"]
        attempts = (doc.get("fulfil_attempts") or 0) + 1
        await db.orders.update_one({"order_id": oid},
            {"$inc": {"fulfil_attempts": 1}, "$set": {"last_fulfil_attempt_at": now.isoformat()}})
        try:
            status = await sync_orders.fulfil_order(
                db, oid, render_pdf=_render_license, put_object=_r2_put,
                now=datetime.now(timezone.utc), send_license=_send_license_email,
                build_license=licenses.build_license_from_order)
            await db.orders.update_one({"order_id": oid}, {"$set": {"last_fulfil_error": None}})
            logger.info("reconcile fulfil order=%s status=%s attempt=%d", oid, status, attempts)
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"[:300]
            await db.orders.update_one({"order_id": oid}, {"$set": {"last_fulfil_error": err}})
            if attempts >= FULFIL_MAX_ATTEMPTS:
                logger.error("fulfilment stuck order=%s attempts=%d error=%s", oid, attempts, err)
            else:
                logger.warning("reconcile fulfil failed order=%s attempt=%d error=%s", oid, attempts, err)


async def _run_fulfilment_reconciler() -> None:
    logger.info("Fulfilment reconciler started instance=%s", INSTANCE_ID)
    while True:
        await asyncio.sleep(FULFIL_RECONCILE_INTERVAL)
        try:
            await _reconcile_fulfilment(datetime.now(timezone.utc))
        except Exception as exc:
            logger.error("fulfilment reconciler error: %s", exc)


STRIPE_HANDLED_EVENTS = {"checkout.session.completed", "checkout.session.async_payment_succeeded",
                         "checkout.session.expired", "charge.refunded",
                         "customer.subscription.created", "customer.subscription.updated",
                         "customer.subscription.deleted", "invoice.paid", "invoice.payment_failed",
                         "charge.dispute.created", "charge.dispute.closed"}


@api_router.post("/stripe/webhook")
async def stripe_webhook(request: Request, background: BackgroundTasks):
    """Stripe events. Signature verified on the raw body. An event is recorded only after it
    was handled, so a failure returns 500 and Stripe retries it."""
    import stripe
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(payload, request.headers.get("stripe-signature"),
                                               sync_orders.stripe_webhook_secret())
    except sync_orders.ConfigError as exc:
        logger.error("stripe webhook config error: %s", exc)
        raise HTTPException(status_code=503, detail="Not configured")
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event.type not in STRIPE_HANDLED_EVENTS:
        return {"ok": True, "ignored": event.type}
    if await sync_orders.event_seen(db, event.id):
        return {"ok": True, "duplicate": True}

    obj = event.data.object.to_dict()
    now = datetime.now(timezone.utc)
    try:
        client = sync_orders.stripe_client()                 # subscription handlers re-fetch from Stripe
    except sync_orders.ConfigError:
        client = None                                        # single-track-only envs (and tests) have no API key
    if event.type in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        if obj.get("mode") == "subscription":
            if client:
                await subscriptions.on_checkout_completed(db, client, obj, now)
            else:
                logger.error("subscription checkout %s arrived but no Stripe API key is configured", obj.get("id"))
        else:
            order_id = await sync_orders.apply_session_paid(db, obj, now=now)
            if order_id:
                background.add_task(_fulfil_order, order_id)
    elif event.type == "checkout.session.expired":
        await sync_orders.apply_session_expired(db, obj, now=now)
    elif event.type == "charge.refunded":
        order_id = await sync_orders.apply_refund(db, obj, now=now)          # single-track first
        if order_id:
            logger.info("charge.refunded %s is single-track order %s; no subscription action",
                        obj.get("id"), order_id)
        elif client:
            sub_invoice = await subscriptions.on_charge_refunded(db, client, obj, now)
            if not sub_invoice:
                logger.error("charge.refunded %s matched neither a single-track order nor an invoice",
                             obj.get("id"))
        else:
            logger.error("charge.refunded %s matched no single-track order and no Stripe API key is configured",
                         obj.get("id"))
    elif event.type in ("customer.subscription.created", "customer.subscription.updated",
                        "customer.subscription.deleted"):
        if client:
            await subscriptions.on_subscription_event(db, client, obj["id"], now)
        else:
            logger.error("subscription event %s arrived but no Stripe API key is configured", event.type)
    elif event.type == "invoice.paid":
        if client:
            await subscriptions.on_invoice_paid(db, client, obj, now)
        else:
            logger.error("invoice.paid arrived but no Stripe API key is configured")
    elif event.type == "invoice.payment_failed":
        await subscriptions.on_invoice_payment_failed(db, obj, now)
    elif event.type in ("charge.dispute.created", "charge.dispute.closed"):
        if client:
            pi = obj.get("payment_intent")
            order = await db.orders.find_one({"stripe_payment_intent": pi}) if pi else None
            if order:
                # Single-track dispute. Brief 17/18 define no dispute handling, so nothing changes
                # here; the point is that the subscription void path never runs on a single-track charge.
                logger.info("charge.dispute %s is single-track order %s; no subscription action",
                            obj.get("id"), order.get("order_id"))
            else:
                sub_invoice = await subscriptions.on_dispute(db, client, obj, now,
                                                             closed=event.type.endswith("closed"))
                if not sub_invoice:
                    logger.error("charge.dispute %s matched neither a single-track order nor an invoice",
                                 obj.get("id"))
        else:
            logger.error("dispute event %s arrived but no Stripe API key is configured", event.type)

    await sync_orders.record_event(db, event.id, event.type, now=now)   # only after handlers succeed
    return {"ok": True}


# ---------------------------------------------------------------------------
# Subscriptions (Brief 19). Plans live in Stripe; the client sends only plan + interval.
# ---------------------------------------------------------------------------

_REGISTER_BLOCK = {
    "no_plan": (403, "You need an active plan to register projects."),
    "payment": (403, "Your payment is past due. Update your card to keep registering."),
    "dispute": (403, "Registration is paused while a payment dispute is open."),
    "month_cap": (429, "You have reached this month's project limit for your plan."),
    "day_cap": (429, "You have reached today's download limit. Try again tomorrow."),
}


def _register_block(reason) -> tuple:
    return _REGISTER_BLOCK.get(reason, (403, "You cannot register a project right now."))


async def _subscriptions_ready() -> bool:
    if os.environ.get("SUBSCRIPTIONS_ENABLED", "").strip().lower() != "true":
        return False
    try:
        return await asyncio.to_thread(subscriptions.ensure_prices, sync_orders.stripe_client())
    except Exception as exc:
        logger.warning("subscription gate price check failed: %s", exc)
        return False


async def _require_subscriptions() -> None:
    if not await _subscriptions_ready():
        raise HTTPException(status_code=503, detail="Subscriptions are not available right now.")


async def _sub_gate(clerk_payload: dict) -> None:
    """Write-endpoint gate: the flag and all six prices (via _require_subscriptions), plus the
    same admin-only gating single-track checkout uses while public checkout is still closed."""
    await _require_subscriptions()
    if not sync_orders.can_checkout(_role(clerk_payload) == "admin"):
        raise HTTPException(status_code=403, detail="Subscriptions are not open yet.")


async def _stripe_customer_for(uid: str, client) -> str:
    """The user's Stripe customer id, created and persisted once."""
    prof = await db.buyer_profiles.find_one({"user_id": uid})
    if prof and prof.get("stripe_customer_id"):
        return prof["stripe_customer_id"]
    user = await fetch_clerk_user(uid)
    cust = await asyncio.to_thread(client.v1.customers.create,
                                   {"email": user["email"], "metadata": {"user_id": uid}})
    now = datetime.now(timezone.utc).isoformat()
    await db.buyer_profiles.update_one(
        {"user_id": uid},
        {"$set": {"stripe_customer_id": cust.id, "updated_at": now},
         "$setOnInsert": {"user_id": uid, "created_at": now}}, upsert=True)
    return cust.id


async def _subscription_me(uid: str, now: datetime) -> dict:
    access = await subscriptions.plan_access(db, uid, now)
    sub = await db.subscriptions.find_one({"user_id": uid}, sort=[("created_at", -1)])
    registered_count = await db.licenses.count_documents({"source": "subscription", "owner_user_id": uid})
    view = {"state": access["state"], "plan": access["plan"], "interval": access["interval"],
            "can_register": access["can_register"], "reason": access["reason"],
            "month_used": access["month_used"], "month_cap": access["month_cap"],
            "day_used": access["day_used"], "day_cap": access["day_cap"],
            "registered_count": registered_count, "subscription": None}
    if sub:
        # All loyalty and grace figures are computed here so the client only formats them.
        lv = subscriptions.loyalty_view(sub.get("plan"), sub.get("interval"),
                                        sub.get("loyalty_pct") or 0, sub.get("subscribed_since"))
        view["subscription"] = {
            "status": sub.get("status"), "plan": sub.get("plan"), "interval": sub.get("interval"),
            "plan_label": PLANS.get(sub.get("plan"), {}).get("label"),
            "cancel_at_period_end": bool(sub.get("cancel_at_period_end")),
            "loyalty_pct": sub.get("loyalty_pct") or 0,
            "subscribed_since": sub.get("subscribed_since"),
            "next_payment_date": sub.get("current_period_end"),
            "grace_ends_at": subscriptions.grace_ends_at(sub),
            **lv}
    return view


def _license_as_order(lic: dict) -> dict:
    """Shape a subscription license as the dict render_license_pdf and delivery_files expect."""
    return {
        "order_id": f"sub-{lic['license_id']}", "license_id": lic["license_id"],
        "track_id": lic["track_id"], "tier": lic["license_label"], "terms_version": lic["terms_version"],
        "created_at": lic["issued_at"], "paid_at": lic["issued_at"], "currency": "usd",
        "buyer_name": lic.get("licensee_name") or "", "buyer_company": lic.get("licensee_company") or "",
        "buyer_email": lic["buyer_email"], "include_stems": bool(lic["include_stems"]),
        "price_cents": None, "tax_cents": None, "amount_total_cents": None, "test_mode": False,
        "license_pdf_key": lic.get("pdf_key"), "project": lic.get("project") or {}}


async def _register_result(lic: dict, now: datetime) -> dict:
    token = sync_orders.derive_token(lic["license_id"], 1)
    access = await subscriptions.plan_access(db, lic["owner_user_id"], now)
    return {"license_id": lic["license_id"], "track_title": lic["track_title"],
            "plan_label": lic["license_label"], "download_url": f"/license/{token}",
            "certificate_url": f"/api/account/licenses/{lic['license_id']}/certificate",
            "remaining": max(access["month_cap"] - access["month_used"], 0)}


def _norm_project(name: str) -> str:
    """Normalize a project name for the duplicate-submit guard: collapsed whitespace, case-folded."""
    return " ".join((name or "").split()).casefold()


async def _release_slot(uid: str, now: datetime) -> None:
    await db.sub_usage.update_one({"user_id": uid, "period": subscriptions.month_key(now)}, {"$inc": {"count": -1}})
    await db.sub_usage.update_one({"user_id": uid, "period": subscriptions.day_key(now)}, {"$inc": {"count": -1}})


@api_router.post("/subscriptions/checkout")
@limiter.limit("10/minute")
async def subscriptions_checkout(request: Request, payload: SubscribeRequest,
                                 clerk_payload: dict = Depends(verify_clerk_token)):
    """Start a Stripe Checkout Session in subscription mode. Price comes from Stripe by plan+interval."""
    await _sub_gate(clerk_payload)
    uid = clerk_payload["sub"]
    now = datetime.now(timezone.utc)
    access = await subscriptions.plan_access(db, uid, now)
    if access["state"] in subscriptions.ACTIVE_STATES:
        raise HTTPException(status_code=409, detail="You already have a plan. Use Manage billing to change it.")
    pid = subscriptions.price_id(payload.plan, payload.interval)
    if not pid:
        raise HTTPException(status_code=503, detail="Plans are temporarily unavailable.")
    client = sync_orders.stripe_client()
    customer_id = await _stripe_customer_for(uid, client)
    # Stripe is the source of truth: 409 on a plan that exists in Stripe but has not mirrored yet,
    # and expire any stale open Checkout Sessions so a customer cannot run two at once.
    existing = await asyncio.to_thread(client.v1.subscriptions.list,
                                       {"customer": customer_id, "status": "all", "limit": 100})
    if any(s.status in ("active", "trialing", "past_due", "unpaid") for s in existing.data):
        raise HTTPException(status_code=409, detail="You already have a plan. Use Manage billing to change it.")
    for s in (await asyncio.to_thread(client.v1.checkout.sessions.list,
                                      {"customer": customer_id, "status": "open", "limit": 100})).data:
        await asyncio.to_thread(client.v1.checkout.sessions.expire, s.id)
    site = sync_orders.site_url()
    params = {
        "mode": "subscription", "customer": customer_id,
        "line_items": [{"price": pid, "quantity": 1}],
        "client_reference_id": uid,
        "subscription_data": {"metadata": {"user_id": uid}},
        "automatic_tax": {"enabled": True},
        "customer_update": {"address": "auto", "name": "auto"},
        "billing_address_collection": "required", "tax_id_collection": {"enabled": True},
        "allow_promotion_codes": False,
        "success_url": f"{site}/account?tab=subscription&checkout=success",
        "cancel_url": f"{site}/account?tab=subscription"}
    try:
        session = await asyncio.to_thread(
            client.v1.checkout.sessions.create, params,
            {"idempotency_key": f"sub-checkout-{uid}-{payload.plan}-{payload.interval}-{int(now.timestamp() // 3600)}"})
    except Exception as exc:
        logger.error("subscription checkout create failed uid=%s error=%s", uid, exc)
        raise HTTPException(status_code=502, detail="Could not start checkout. Please try again.")
    logger.info("subscription checkout uid=%s plan=%s interval=%s", uid, payload.plan, payload.interval)
    return {"checkout_url": session.url}


@api_router.post("/subscriptions/portal")
@limiter.limit("10/minute")
async def subscriptions_portal(request: Request, clerk_payload: dict = Depends(verify_clerk_token)):
    """A Stripe Billing Portal link so the user can change card, plan or cancel."""
    config_id = os.environ.get("STRIPE_PORTAL_CONFIG_ID", "").strip()
    if not config_id:
        raise HTTPException(status_code=503, detail="Billing management is temporarily unavailable.")
    uid = clerk_payload["sub"]
    prof = await db.buyer_profiles.find_one({"user_id": uid})
    if not prof or not prof.get("stripe_customer_id"):
        raise HTTPException(status_code=404, detail="No billing account yet.")
    client = sync_orders.stripe_client()
    try:
        session = await asyncio.to_thread(
            client.v1.billing_portal.sessions.create,
            {"customer": prof["stripe_customer_id"], "configuration": config_id,
             "return_url": f"{sync_orders.site_url()}/account"})
    except Exception as exc:
        logger.error("portal session create failed uid=%s error=%s", uid, exc)
        raise HTTPException(status_code=502, detail="Could not open billing. Please try again.")
    return {"portal_url": session.url}


@api_router.post("/subscriptions/resume")
@limiter.limit("10/minute")
async def subscriptions_resume(request: Request, clerk_payload: dict = Depends(verify_clerk_token)):
    """Undo a scheduled cancellation before the period ends."""
    uid = clerk_payload["sub"]
    now = datetime.now(timezone.utc)
    sub = await db.subscriptions.find_one({"user_id": uid}, sort=[("created_at", -1)])
    if not sub or not sub.get("cancel_at_period_end"):
        raise HTTPException(status_code=409, detail="There is nothing to resume.")
    if subscriptions._state(sub, now) not in ("ending", "active", "grace"):
        raise HTTPException(status_code=409, detail="This plan cannot be resumed.")
    client = sync_orders.stripe_client()
    try:
        await asyncio.to_thread(client.v1.subscriptions.update,
                                sub["stripe_subscription_id"], {"cancel_at_period_end": False})
    except Exception as exc:
        logger.error("resume failed uid=%s error=%s", uid, exc)
        raise HTTPException(status_code=502, detail="Could not resume. Please try again.")
    await subscriptions.on_subscription_event(db, client, sub["stripe_subscription_id"], now)
    return await _subscription_me(uid, now)


@api_router.get("/subscriptions/me")
@limiter.limit("30/minute")
async def subscriptions_me(request: Request, clerk_payload: dict = Depends(verify_clerk_token)):
    return await _subscription_me(clerk_payload["sub"], datetime.now(timezone.utc))


@api_router.post("/subscriptions/register")
@limiter.limit("20/minute")
async def subscriptions_register(request: Request, payload: RegisterRequest,
                                 clerk_payload: dict = Depends(verify_clerk_token)):
    """License one track under the signed-in user's plan. One registration = one spent download slot."""
    await _sub_gate(clerk_payload)
    if not payload.accept_terms:
        raise HTTPException(status_code=422, detail="You must accept the license terms")
    current_terms = sync_orders.terms_version()
    if payload.terms_version != current_terms:
        raise HTTPException(status_code=409, detail="The license terms have changed. Reload and review them.")
    uid = clerk_payload["sub"]
    now = datetime.now(timezone.utc)

    # Double-submit guard: the same user + track + normalized project name within 10 minutes
    # returns the existing license, with no new count.
    cutoff = (now - timedelta(minutes=10)).isoformat()
    target_name = _norm_project(payload.project_name)
    recent = await db.licenses.find(
        {"source": "subscription", "owner_user_id": uid, "track_id": payload.track_id,
         "created_at": {"$gte": cutoff}}).sort("created_at", -1).to_list(20)
    for existing in recent:
        if _norm_project((existing.get("project") or {}).get("name")) == target_name:
            return await _register_result(existing, now)

    access = await subscriptions.plan_access(db, uid, now)
    if not access["can_register"]:
        status, msg = _register_block(access["reason"])
        raise HTTPException(status_code=status, detail=msg)

    track = await db.track_submissions.find_one(
        {"id": payload.track_id}, {"_id": 0, **{f: 0 for f in MATCH_DETAIL_FIELDS}})
    if not track or not is_listed(track):
        raise _not_found()
    include_stems = payload.include_stems and sync_orders.deliver_stems()
    sub = await db.subscriptions.find_one({"user_id": uid}, sort=[("created_at", -1)])
    plan = access["plan"]
    user = await fetch_clerk_user(uid)

    ok, reason = await subscriptions.claim_download_slot(db, uid, PLANS[plan]["month_cap"], SUB_DAY_CAP, now)
    if not ok:
        status, msg = _register_block(reason)
        raise HTTPException(status_code=status, detail=msg)

    # A slot is now spent; release it on any failure before the license is stored.
    try:
        lic = licenses.build_subscription_license(
            license_id=sync_orders.new_license_id(), user_id=uid, buyer_email=user["email"], plan=plan,
            subscription_id=(sub or {}).get("stripe_subscription_id"), invoice_id=(sub or {}).get("latest_invoice"),
            track=track, project_name=payload.project_name, client=payload.project_client,
            include_stems=include_stems, terms_version=current_terms, now=now)
        name = " ".join(p for p in (user.get("first_name"), user.get("last_name")) if p).strip()
        lic["licensee_name"] = name
        pdf_key = f"licenses/sub/{lic['license_id']}.pdf"
        lic["pdf_key"] = pdf_key
        token = sync_orders.derive_token(lic["license_id"], 1)
        lic["download_token_hash"] = sync_orders.hash_token(token)
        lic["email_status"] = None
        order_like = _license_as_order(lic)
        sync_orders.delivery_files(order_like, track)   # DeliveryError before any upload
        pdf = await _render_license(order_like, track_title=lic["track_title"],
                                    artist_name=lic["artist_display_name"], lic=lic)
        await _r2_put(pdf_key, pdf, "application/pdf")
        await db.licenses.insert_one(dict(lic))
    except sync_orders.DeliveryError as exc:
        await _release_slot(uid, now)
        logger.error("subscription register delivery error uid=%s track=%s: %s", uid, payload.track_id, exc)
        raise HTTPException(status_code=409, detail="This track's files are not ready yet. Try again shortly.")
    except Exception:
        await _release_slot(uid, now)
        raise

    try:
        subject, html, text = subscription_license_email(
            lic, download_url=f"{sync_orders.site_url()}/license/{token}")
        res = await send_email(to=lic["buyer_email"], subject=subject, html=html, text=text,
                               attachments=[(f"oVoxi-license-{lic['license_id']}.pdf", pdf)],
                               idempotency_key=f"sub-license-{lic['license_id']}")
        await db.licenses.update_one({"license_id": lic["license_id"]},
                                     {"$set": {"email_status": res["status"]}})
    except Exception as exc:
        logger.error("subscription license email failed license=%s error=%s", lic["license_id"], exc)
    logger.info("subscription register uid=%s license=%s track=%s plan=%s",
                uid, lic["license_id"], payload.track_id, plan)
    return await _register_result(lic, now)


@api_router.get("/sync/orders/by-session/{session_id}")
@limiter.limit("30/minute")
async def sync_order_by_session(request: Request, session_id: str):
    """Success page polling. If the webhook has not arrived yet, ask Stripe directly
    (at most every few seconds per order) and deliver when the payment is complete."""
    if not sync_orders.SESSION_ID_RE.match(session_id):
        raise _not_found()
    order = await db.orders.find_one({"stripe_session_id": session_id}, {"_id": 0})
    if not order:
        raise _not_found()
    now = datetime.now(timezone.utc)
    if order["status"] == "pending" and await sync_orders.claim_stripe_recheck(db, order["order_id"], now=now):
        try:
            client = sync_orders.stripe_client()
            session = await asyncio.to_thread(client.v1.checkout.sessions.retrieve, session_id)
            await sync_orders.apply_session_paid(db, session.to_dict(), now=now)
        except Exception as exc:
            logger.warning("stripe recheck failed order=%s error=%s", order["order_id"], exc)
    if order["status"] in ("pending", "paid"):
        await _fulfil_order(order["order_id"])  # no-op unless the order is now paid
        order = await db.orders.find_one({"order_id": order["order_id"]}, {"_id": 0})
    return sync_orders.success_view(order)


async def _order_for_token(token: str) -> dict:
    order = await sync_orders.find_by_token(db, token, now=datetime.now(timezone.utc))
    if order:
        return order
    # Subscription licenses mint the same style of token (Brief 19); gate on plan state at download time.
    lic = await db.licenses.find_one({"download_token_hash": sync_orders.hash_token(token),
                                      "source": "subscription"})
    if lic:
        if lic.get("status") in ("refunded", "void"):
            raise HTTPException(status_code=404, detail="This download link is invalid or has expired.")
        access = await subscriptions.plan_access(db, lic["owner_user_id"])
        if access["state"] not in subscriptions.ACTIVE_STATES:
            raise HTTPException(status_code=403,
                                detail="Your plan has ended. Projects you registered stay licensed.")
        return {"_subscription_license": lic, "license_id": lic["license_id"], "track_id": lic["track_id"],
                "include_stems": lic["include_stems"], "license_pdf_key": lic["pdf_key"],
                "track_title": lic["track_title"], "artist_display_name": lic["artist_display_name"]}
    raise HTTPException(status_code=404, detail="This download link is invalid or has expired.")


async def _files_for(order: dict) -> dict:
    track = await db.track_submissions.find_one({"id": order["track_id"]}, {"_id": 0}) or {}
    try:
        return sync_orders.delivery_files(order, track)
    except sync_orders.DeliveryError as exc:
        logger.error("download files missing: %s", exc)
        raise HTTPException(status_code=409,
                            detail="Your files are temporarily unavailable. Contact tyler@ovoxi.net with your License ID.")


@api_router.get("/sync/downloads/{token}")
@limiter.limit("30/minute")
async def sync_download_listing(request: Request, token: str):
    order = await _order_for_token(token)
    files = await _files_for(order)
    lic = order.get("_subscription_license")
    if lic:
        # Subscription downloads are not metered per file (the project is already registered).
        return {"license_id": lic["license_id"], "track_title": lic["track_title"],
                "artist_display_name": lic["artist_display_name"], "tier": lic["license_label"],
                "include_stems": bool(lic["include_stems"]), "expires_at": None, "test_mode": False,
                "source": "subscription",
                "files": [{"name": n, "label": sync_orders.FILE_LABELS.get(n, n), "remaining": None}
                          for n in files]}
    return sync_orders.download_listing(order, files)


@api_router.post("/sync/downloads/{token}/{file_name}")
@limiter.limit("20/minute")
async def sync_download_file(request: Request, token: str, file_name: str):
    """Count one download and return a 5-minute signed link that saves the file."""
    order = await _order_for_token(token)
    files = await _files_for(order)
    if file_name not in files:
        raise _not_found()
    is_sub = bool(order.get("_subscription_license"))
    if not is_sub and not await sync_orders.claim_download(db, order, file_name):
        raise HTTPException(status_code=429, detail="Download limit reached for this file.")
    key = files[file_name]
    filename = sync_orders.download_filename(order, file_name, key)
    try:
        url = await asyncio.to_thread(
            r2_client.generate_presigned_url, "get_object",
            Params={"Bucket": R2_BUCKET, "Key": key,
                    "ResponseContentDisposition": f'attachment; filename="{filename}"'},
            ExpiresIn=sync_orders.DOWNLOAD_URL_TTL_SECONDS,
        )
    except Exception as exc:
        logger.error("download sign failed order=%s file=%s error=%s", order.get("order_id"), file_name, exc)
        if not is_sub:
            await db.orders.update_one({"order_id": order["order_id"]}, {"$inc": {f"download_counts.{file_name}": -1}})
        raise HTTPException(status_code=503, detail="Download unavailable. Please try again.")
    logger.info("download order=%s file=%s sub=%s", order.get("order_id"), file_name, is_sub)
    return {"url": url, "filename": filename, "expires_in": sync_orders.DOWNLOAD_URL_TTL_SECONDS}


# ---------------------------------------------------------------------------
# Buyer account and public verification (Brief 17). Any signed-in user; no buyer role.
# ---------------------------------------------------------------------------

async def _license_files(lic: dict) -> list:
    """[{name, label}] the owner can download. Subscription projects deliver from the license
    itself (there is no order); single-track from the backing order. Empty when unavailable."""
    if lic.get("source") == "subscription":
        order = _license_as_order(lic)
        track = await db.track_submissions.find_one({"id": lic.get("track_id")}, {"_id": 0}) or {}
    else:
        order = await db.orders.find_one({"order_id": lic.get("order_id")}) if lic.get("order_id") else None
        if not order:
            return []
        track = await db.track_submissions.find_one({"id": order["track_id"]}, {"_id": 0}) or {}
    try:
        files = sync_orders.delivery_files(order, track)
    except sync_orders.DeliveryError:
        return []
    return [{"name": n, "label": sync_orders.FILE_LABELS.get(n, n)} for n in files]


@api_router.get("/account/licenses")
@limiter.limit("30/minute")
async def account_licenses(request: Request, clerk_payload: dict = Depends(verify_clerk_token)):
    uid = clerk_payload["sub"]
    now = datetime.now(timezone.utc)
    linking = "ok"
    try:
        user = await fetch_clerk_user(uid)
        if user.get("email_verified") and user.get("email"):
            await db.licenses.update_many(
                {"owner_user_id": None, "buyer_email": user["email"].lower()},
                {"$set": {"owner_user_id": uid}})
    except HTTPException:
        linking = "unavailable"
    docs = await db.licenses.find({"owner_user_id": uid}, {"_id": 0}).sort("issued_at", -1).to_list(500)
    out = [licenses.owner_view(lic, now, files=await _license_files(lic)) for lic in docs]
    return {"licenses": out, "linking": linking}


@api_router.get("/account/licenses/{license_id}/certificate")
@limiter.limit("30/minute")
async def account_certificate(request: Request, license_id: str,
                              clerk_payload: dict = Depends(verify_clerk_token)):
    lic = await db.licenses.find_one({"license_id": license_id, "owner_user_id": clerk_payload["sub"]})
    if not lic or not lic.get("pdf_key"):
        raise _not_found()  # 404 for a non-owner too, so IDs cannot be probed
    url = await asyncio.to_thread(
        r2_client.generate_presigned_url, "get_object",
        Params={"Bucket": R2_BUCKET, "Key": lic["pdf_key"],
                "ResponseContentDisposition": f'attachment; filename="oVoxi-license-{license_id}.pdf"'},
        ExpiresIn=300)
    return {"url": url}


@api_router.post("/account/licenses/{license_id}/files/{file_name}")
@limiter.limit("20/minute")
async def account_license_file(request: Request, license_id: str, file_name: str,
                               clerk_payload: dict = Depends(verify_clerk_token)):
    lic = await db.licenses.find_one({"license_id": license_id, "owner_user_id": clerk_payload["sub"]})
    if not lic:
        raise _not_found()
    if lic.get("status") in ("refunded", "void"):
        raise HTTPException(status_code=409, detail="This license is no longer valid.")
    if lic.get("source") == "subscription":
        # Re-downloading an already-registered project is free: gate on plan state only, and never
        # claim_download or touch sub_usage. Mirrors the token path (_order_for_token).
        access = await subscriptions.plan_access(db, lic["owner_user_id"])
        if access["state"] not in subscriptions.ACTIVE_STATES:
            raise HTTPException(status_code=403,
                                detail="Your plan has ended. Projects you registered stay licensed.")
        order = _license_as_order(lic)
        order["track_title"] = lic.get("track_title", "")
        order["artist_display_name"] = lic.get("artist_display_name", "")
        files = await _files_for(order)
        if file_name not in files:
            raise _not_found()
    else:
        order = await db.orders.find_one({"order_id": lic.get("order_id")})
        if not order:
            raise _not_found()
        files = await _files_for(order)
        if file_name not in files:
            raise _not_found()
        if not await sync_orders.claim_download(db, order, file_name):
            raise HTTPException(status_code=429, detail="Download limit reached for this file.")
    key = files[file_name]
    filename = sync_orders.download_filename(order, file_name, key)
    url = await asyncio.to_thread(
        r2_client.generate_presigned_url, "get_object",
        Params={"Bucket": R2_BUCKET, "Key": key,
                "ResponseContentDisposition": f'attachment; filename="{filename}"'},
        ExpiresIn=sync_orders.DOWNLOAD_URL_TTL_SECONDS)
    return {"url": url, "filename": filename, "expires_in": sync_orders.DOWNLOAD_URL_TTL_SECONDS}


@api_router.get("/verify/{license_id}")
@limiter.limit("30/minute")
async def verify_license(request: Request, license_id: str):
    # Always available, never behind SYNC_PUBLIC_PAGES_ENABLED.
    if not licenses.LICENSE_ID_RE.match(license_id):
        raise HTTPException(status_code=404, detail="No license found")
    lic = await db.licenses.find_one({"license_id": license_id})
    if not lic:
        raise HTTPException(status_code=404, detail="No license found")
    return licenses.public_view(lic, datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Admin orders (PRD-03 9): list, CSV for manual payouts, resend email, reissue link
# ---------------------------------------------------------------------------

def _admin_filter(status, artist, date_from, date_to, include_test) -> dict:
    try:
        return sync_orders.admin_order_filter(status=status, artist=artist, date_from=date_from,
                                              date_to=date_to, include_test=include_test)
    except sync_orders.AdminFilterError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@api_router.get("/admin/sync/orders")
@limiter.limit("30/minute")
async def admin_list_orders(request: Request, status: Optional[str] = None, artist: Optional[str] = None,
                            date_from: Optional[str] = None, date_to: Optional[str] = None,
                            include_test: bool = False, admin: dict = Depends(require_admin)):
    f = _admin_filter(status, artist, date_from, date_to, include_test)
    cap = sync_orders.ADMIN_LIST_MAX
    docs = await db.orders.find(f, {"_id": 0}).sort("created_at", -1).to_list(cap + 1)
    artists = await db.orders.aggregate([
        {"$group": {"_id": "$artist_user_id", "name": {"$last": "$artist_display_name"}}},
        {"$sort": {"name": 1}},
    ]).to_list(1000)
    return {"orders": [sync_orders.admin_order_view(o) for o in docs[:cap]], "truncated": len(docs) > cap,
            "artists": [{"artist_user_id": a["_id"], "artist_display_name": a.get("name") or a["_id"]}
                        for a in artists if a.get("_id")]}


@api_router.get("/admin/sync/orders.csv")
@limiter.limit("10/minute")
async def admin_orders_csv(request: Request, status: Optional[str] = None, artist: Optional[str] = None,
                           date_from: Optional[str] = None, date_to: Optional[str] = None,
                           include_test: bool = False, admin: dict = Depends(require_admin)):
    f = _admin_filter(status, artist, date_from, date_to, include_test)
    docs = await db.orders.find(f, {"_id": 0}).sort("created_at", 1).to_list(sync_orders.CSV_MAX_ROWS)
    name = f"ovoxi-orders-{date_from or 'all'}-to-{date_to or 'now'}.csv"
    await _log_admin_action(admin, "export_orders_csv", name, f"{len(docs)} rows")
    return Response(content=sync_orders.orders_csv(docs), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


async def _fulfilled_order_or_409(order_id: str) -> dict:
    order = await db.orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        raise _not_found()
    if order["status"] != "fulfilled":
        raise HTTPException(status_code=409,
                            detail=f"Only fulfilled orders can be changed (this one is {order['status']}).")
    return order


@api_router.post("/admin/sync/orders/{order_id}/resend-email")
@limiter.limit("10/minute")
async def admin_resend_email(request: Request, order_id: str, admin: dict = Depends(require_admin)):
    order = await _fulfilled_order_or_409(order_id)
    try:
        result = await _send_license_email(
            order, idempotency_key=f"license-{order['order_id']}-resend-{uuid.uuid4().hex}")
    except Exception as exc:
        result = {"status": "failed", "id": None, "error": f"{type(exc).__name__}: {exc}"[:300]}
    await sync_orders.record_email(db, order_id, result, now=datetime.now(timezone.utc))
    await _log_admin_action(admin, "resend_license_email", order["license_id"], result["status"])
    return {"email_status": result["status"], "email_error": result.get("error")}


@api_router.post("/admin/sync/orders/{order_id}/reissue-link")
@limiter.limit("10/minute")
async def admin_reissue_link(request: Request, order_id: str, payload: AdminReissue,
                             admin: dict = Depends(require_admin)):
    await _fulfilled_order_or_409(order_id)
    now = datetime.now(timezone.utc)
    token = await sync_orders.reissue_token(db, order_id, now=now)
    if not token:
        raise HTTPException(status_code=409, detail="The order changed while reissuing. Reload and try again.")
    order = await db.orders.find_one({"order_id": order_id}, {"_id": 0})
    result = {"status": "skipped", "id": None, "error": "not requested"}
    if payload.send_email:
        try:
            result = await _send_license_email(order, reissued=True)
        except Exception as exc:
            result = {"status": "failed", "id": None, "error": f"{type(exc).__name__}: {exc}"[:300]}
        await sync_orders.record_email(db, order_id, result, now=now)
    await _log_admin_action(admin, "reissue_download_link", order["license_id"],
                            f"email={result['status']}")
    return {"download_url": f"{sync_orders.site_url()}/license/{token}",
            "token_expires_at": order.get("token_expires_at"), "email_status": result["status"],
            "email_error": result.get("error")}


# ---------------------------------------------------------------------------
# App wiring
# ---------------------------------------------------------------------------

app.include_router(api_router)

_cors_origins = [
    o.strip()
    for o in os.environ.get('CORS_ORIGINS', 'https://ovoxi.net,https://www.ovoxi.net,http://localhost:3000').split(',')
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def create_indexes():
    try:
        await db.track_submissions.create_index([("clerk_user_id", 1), ("upload_date", -1)])
        await db.track_submissions.create_index([("status", 1), ("upload_date", 1)])
        await db.track_submissions.create_index([("id", 1)])
        await db.appeals.create_index([("id", 1)])
        await db.consent_events.create_index([("track_id", 1)])
        await db.consent_events.create_index([("user_id", 1), ("created_at", 1)])
        await db.sync_profiles.create_index([("user_id", 1)], unique=True)
        await db.sync_profiles.create_index([("slug", 1)], unique=True)
        await db.track_submissions.create_index(
            [("sync_status", 1), ("on_sync_profile", 1), ("sync_listed_at", -1), ("id", -1)])
        await db.sync_profiles.create_index([("sales_count", -1)])
        await db.artist_agreements.create_index([("user_id", 1), ("version", 1)], unique=True)
        await db.artist_agreements.create_index([("id", 1)], unique=True)
        await db.artist_agreements.create_index([("user_id", 1), ("signed_at", -1)])
        await db.artist_legal_profiles.create_index([("user_id", 1)], unique=True)
        await sync_orders.ensure_indexes(db)
        await licenses.ensure_indexes(db)
        await subscriptions.ensure_indexes(db)
        await db.buyer_profiles.create_index([("user_id", 1)], unique=True)
        await db.buyer_profiles.create_index([("stripe_customer_id", 1)])
    except Exception as exc:
        logger.warning("Index creation failed (non-fatal): %s", exc)
    try:
        await asyncio.to_thread(subscriptions.load_prices, sync_orders.stripe_client())
    except Exception as exc:
        logger.warning("subscription price load skipped: %s", exc)
    if RUN_WORKER:
        for _ in range(WORKER_CONCURRENCY):
            asyncio.ensure_future(_worker_loop())
        asyncio.ensure_future(_run_sweeper())
        asyncio.ensure_future(_run_fulfilment_reconciler())
        logger.info("Started %d worker(s), sweeper and reconciler instance=%s", WORKER_CONCURRENCY, INSTANCE_ID)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
