import asyncio
import hashlib
import hmac
import json
import os
import logging
import re
import secrets
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
    DISTRIBUTORS, PRO_ORGS, IPI_PATTERN, IPI_MESSAGE, OTHER_TEXT_MAX, clean_ipi, MUSICAL_KEYS, BPM_MIN, BPM_MAX, COUNTRIES,
    PLANS, SUB_DAY_CAP,
    COSIGN_TOKEN_TTL_DAYS, COSIGN_MAX_RESENDS, COSIGN_RESEND_COOLDOWN_MIN,
    AI_TOOLS, AI_TOOLS_DETAIL_MAX, AI_TOOLS_FULL_MESSAGE,
    UPLOAD_SAMPLE_CHOICES, MAX_LOOPS, LOOP_SOURCES, LOOP_LICENSE_TYPES, LOOP_LICENSE_MAX_BYTES,
    SAMPLES_NOT_ALLOWED_MESSAGE, LOOPS_NO_AI_MESSAGE, PRO_REQUIRED_MESSAGE, SYNC_SOLE_MESSAGE,
)
from consent_ledger import record_grants, record_withdrawals, GRANT_VERSION
import privacy
import wallet
import payouts
import statements
import artist_agreement
import cosign
from profile_photo import (
    MAX_PHOTO_BYTES, PHOTO_CONTENT_TYPES, PHOTO_SIZES, PhotoRejected, REJECT_MESSAGE, process_photo,
)
from sync_public import (
    LISTING_FILTER, is_listed, listed_for, photo_visible, public_profile_view, public_track_view,
)
import sync_orders
import licenses
import quotes
import exclusive
from license_pdf import TERMS as LICENSE_TERMS, render_license_pdf
from email_sender import send_email
from sync_emails import license_email, quote_email, subscription_license_email
import subscriptions
from sync_search import PAGE_SIZE, SearchParamError, build_filter, build_pipeline, encode_cursor, parse_params
from sync_vault import (
    INSTAGRAM_URL, SPOTIFY_ARTIST_URL, is_legacy, metadata_patch_fields,
    slugify_profile, vault_track_view,
)
from rights import TrackRightsIn, build_rights, EMAIL_PATTERN as RIGHTS_EMAIL_PATTERN
from clearance import clearance_fields, writers_missing_pro, _creator_emails as rights_emails
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


def _artist_approval_required() -> bool:
    """ARTIST_APPROVAL_REQUIRED (default "true"). Set to "false" to let any signed-in
    account with no role act as an artist (upload, Vault), skipping the manual
    role=artist approval in Clerk. Admin-only routes are unaffected."""
    return os.environ.get("ARTIST_APPROVAL_REQUIRED", "true").strip().lower() != "false"


async def require_artist(payload: dict = Depends(verify_clerk_token)) -> dict:
    """Artist routes. Approved artists and admins, plus signed-in accounts awaiting approval
    (Oct 26): they may upload and use the Vault, but their songs are held, unprocessed and
    unlisted, until they are approved (is_approved). Any other role is refused."""
    if _role(payload) in ("artist", "admin", None):
        return payload
    raise HTTPException(status_code=403, detail="Forbidden")


def is_approved(payload: dict) -> bool:
    """role=artist or admin; or anyone, when ARTIST_APPROVAL_REQUIRED=false."""
    return _role(payload) in ("artist", "admin") or not _artist_approval_required()


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
    """PRD-03 section 5 / Brief 25b D1. Evaluate a track for each opted use and store it.
    Never raises: a clearance error must not break the pipeline or a callback."""
    try:
        doc = await db.track_submissions.find_one({"id": submission_id}, {"_id": 0})
        if not doc:
            return
        fields = clearance_fields(doc, datetime.now(timezone.utc).isoformat())
        await db.track_submissions.update_one({"id": submission_id}, {"$set": fields})
        logger.info("Clearance submission=%s sync_status=%s ai_status=%s",
                    submission_id, fields["sync_status"], fields["ai_status"])
    except Exception as exc:
        logger.error("Clearance evaluation failed for %s: %s", submission_id, exc)


async def _claim_next() -> Optional[dict]:
    now = datetime.now(timezone.utc).isoformat()
    return await db.track_submissions.find_one_and_update(
        {"status": "uploaded", "awaiting_approval": {"$ne": True}},
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
            acr_result = await asyncio.to_thread(acrcloud_check.scan_file, scan_path, duration_s)

        acr_status = acr_result["status"]
        logger.info("ACRCloud result submission=%s status=%s", submission_id, acr_status)

        # PRD-03 section 5 check 2 needs the scan result kept after `status` moves on.
        scan_fields = {
            "fingerprint_result": acr_status,
            "metadata.duration_s": round(duration_s, 2),
        }

        if acr_status != "CLEARED":
            extra = {f: acr_result[f] for f in ("matched_title", "matched_artist",
                     "matched_label", "matched_isrc", "confidence", "acrid", "raw_code",
                     "matched_offset_s")
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
    genre_other: Optional[str] = Field(default=None, max_length=OTHER_TEXT_MAX)
    bio: str = Field(..., min_length=1, max_length=2000)
    website: str = Field(default="")

    @field_validator('genre')
    @classmethod
    def validate_genre(cls, v: str) -> str:
        if v not in VALID_GENRES:
            raise ValueError(f'genre must be one of: {", ".join(sorted(VALID_GENRES))}')
        return v

    @model_validator(mode="after")
    def _genre_other(self):
        self.genre_other = other_answer(self.genre, self.genre_other, GENRE_OTHER_MESSAGE)
        return self


class Artist(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    email: str
    spotify_url: str
    genre: str
    genre_other: Optional[str] = None
    bio: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tracks: List[dict] = []


GENRE_OTHER_MESSAGE = "Enter which genre."
DISTRIBUTOR_OTHER_MESSAGE = "Enter which distributor you use."


def other_answer(choice, text, message):
    """The typed answer for an "Other" choice: required when Other is picked, dropped otherwise."""
    text = (text or "").strip()
    if choice != "Other":
        return None
    if not text:
        raise ValueError(message)
    return text


def _one_of(value, allowed, label):
    if value not in allowed:
        raise ValueError(f"Invalid {label}.")
    return value


class SyncIntake(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Samples moved to Declarations (Brief 25b D1). Still accepted here from the Vault's
    # add-sync flow for tracks that never answered; ignored at upload.
    samples: Optional[str] = None
    samples_attested: bool = False
    distributor: str
    distributor_other: Optional[str] = Field(default=None, max_length=OTHER_TEXT_MAX)  # required when "Other"
    content_id: str
    pro_not_affiliated: bool = False        # kept for old clients; refused for sync (3.5)
    pro_name: Optional[str] = None
    pro_other: Optional[str] = Field(default=None, max_length=80)   # required when pro_name is "Other"
    ipi: Optional[str] = None
    sync_sole_attested: bool = False        # Agreement 3.1 / 3.3: sync is exclusive to OVOXI

    @field_validator("samples")
    @classmethod
    def _samples(cls, v):
        if v == "cleared_sample":
            raise ValueError(SAMPLES_NOT_ALLOWED_MESSAGE)
        return None if v is None else _one_of(v, UPLOAD_SAMPLE_CHOICES, "samples declaration")

    @model_validator(mode="after")
    def _attested(self):
        if self.samples is not None and not self.samples_attested:
            raise ValueError("Confirm the samples declaration to use sync.")
        return self

    @field_validator("distributor")
    @classmethod
    def _distributor(cls, v):
        return _one_of(v, DISTRIBUTORS, "distributor")

    @model_validator(mode="after")
    def _distributor_other(self):
        self.distributor_other = other_answer(self.distributor, self.distributor_other,
                                              DISTRIBUTOR_OTHER_MESSAGE)
        return self

    @field_validator("content_id")
    @classmethod
    def _content_id(cls, v):
        return _one_of(v, CONTENT_ID_ANSWERS, "Content ID answer")

    @model_validator(mode="after")
    def _pro_rules(self):
        if self.pro_not_affiliated or not self.pro_name:
            raise ValueError(PRO_REQUIRED_MESSAGE)
        _one_of(self.pro_name, PRO_ORGS, "PRO")
        other = (self.pro_other or "").strip()
        if self.pro_name == "Other" and not other:
            raise ValueError("Enter which PRO you use.")
        self.pro_other = other if self.pro_name == "Other" else None
        self.ipi = clean_ipi(self.ipi)
        if not self.ipi or not re.fullmatch(IPI_PATTERN, self.ipi):
            raise ValueError(IPI_MESSAGE)
        if not self.sync_sole_attested:
            raise ValueError(SYNC_SOLE_MESSAGE)
        return self


class LoopIn(BaseModel):
    """One royalty-free loop in a song (Agreement 3.6). The creator must also be in the splits."""
    model_config = ConfigDict(extra="forbid")

    creator_name: str = Field(..., min_length=1, max_length=120)
    creator_email: str = Field(..., min_length=3, max_length=200)
    source: str
    loop_name: str = Field(..., min_length=1, max_length=200)

    @field_validator("creator_name", "loop_name")
    @classmethod
    def _strip(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Enter the loop creator and the loop name.")
        return v

    @field_validator("creator_email")
    @classmethod
    def _email(cls, v):
        v = v.strip().lower()
        if not RIGHTS_EMAIL_PATTERN.fullmatch(v):
            raise ValueError("Enter a valid email for each loop creator.")
        return v

    @field_validator("source")
    @classmethod
    def _source(cls, v):
        return _one_of(v, LOOP_SOURCES, "loop source")


class Declarations(BaseModel):
    """Asked on every upload and in the Vault (Brief 25b D1): samples, loops and AI tools."""
    model_config = ConfigDict(extra="forbid")

    samples: str
    samples_attested: bool
    loops: List[LoopIn] = Field(default_factory=list)
    ai_tools: str
    ai_tools_detail: str = Field(default="", max_length=AI_TOOLS_DETAIL_MAX)
    ai_tools_attested: bool

    @field_validator("samples")
    @classmethod
    def _samples(cls, v):
        if v == "cleared_sample":
            raise ValueError(SAMPLES_NOT_ALLOWED_MESSAGE)
        return _one_of(v, UPLOAD_SAMPLE_CHOICES, "samples declaration")

    @field_validator("ai_tools")
    @classmethod
    def _ai_tools(cls, v):
        v = _one_of(v, AI_TOOLS, "AI tools answer")
        if v == "full":
            raise ValueError(AI_TOOLS_FULL_MESSAGE)
        return v

    @model_validator(mode="after")
    def _rules(self):
        if not self.samples_attested:
            raise ValueError("Confirm the samples declaration.")
        if not self.ai_tools_attested:
            raise ValueError("Confirm your AI tools answer.")
        detail = self.ai_tools_detail.strip()
        if self.ai_tools == "partial" and not detail:
            raise ValueError("Tell us which parts used AI, and which tool.")
        self.ai_tools_detail = detail if self.ai_tools == "partial" else ""
        if self.samples == "royalty_free_loop":
            if not 1 <= len(self.loops) <= MAX_LOOPS:
                raise ValueError(f"List each loop you used (1 to {MAX_LOOPS}).")
        elif self.loops:
            raise ValueError("Only list loops when the song uses royalty-free loops.")
        return self

    def intake_fields(self, now_iso: str, previous_loops: Optional[list] = None) -> dict:
        """previous_loops: the stored loops, so an unchanged loop keeps its license file."""
        prev = {(p.get("creator_email"), p.get("loop_name")): p for p in (previous_loops or [])}
        loops = []
        for lp in self.loops:
            old = prev.get((lp.creator_email, lp.loop_name)) or {}
            loops.append({**lp.model_dump(), "license_key": old.get("license_key"),
                          "license_uploaded_at": old.get("license_uploaded_at")})
        return {"samples": self.samples, "samples_attested_at": now_iso, "loops": loops,
                "ai_tools": self.ai_tools, "ai_tools_detail": self.ai_tools_detail or None,
                "ai_tools_attested_at": now_iso}


class PresignRequest(BaseModel):
    artist_name: str = Field(..., min_length=1, max_length=120)
    track_name: str = Field(..., min_length=1, max_length=120)
    genre: str
    genre_other: Optional[str] = Field(default=None, max_length=OTHER_TEXT_MAX)  # required when "Other"
    filename: str = Field(..., min_length=1, max_length=200)
    file_size: int = Field(..., gt=0)
    pro_registered: bool = False
    pro_org: str = ''
    pro_register_us: bool = False
    consent_ai_training: bool = False
    consent_sync: bool = False
    consent_exclusive: bool = False         # Brief 25b: song-level exclusive choice
    consent_ai_exclusive: bool = False      # deprecated (Brief 25); accepted and ignored
    moods: List[str]                        # required, no default
    vocals: str                             # required, no default
    sync_intake: Optional[SyncIntake] = None
    declarations: Optional[Declarations] = None   # required on every upload; see _consent_rules
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
        if self.declarations is None:
            raise ValueError("Answer the samples and AI tools questions.")
        if self.declarations.samples == "royalty_free_loop" and self.consent_ai_training:
            raise ValueError(LOOPS_NO_AI_MESSAGE)
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
    genre_other: Optional[str] = Field(default=None, max_length=OTHER_TEXT_MAX)

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
        if self.genre is not None:
            self.genre_other = other_answer(self.genre, self.genre_other, GENRE_OTHER_MESSAGE)
        return self


CONSENT_SCOPES = ("ai_training", "sync", "exclusive")
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
    kind: Literal["enterprise", "exclusive", "ai_training"]
    track_id: Optional[str] = Field(default=None, max_length=64)
    uses: List[Literal["sync", "ai"]] = Field(default_factory=list, max_length=2)   # kind "exclusive"
    name: str = Field(min_length=1, max_length=120)
    company: str = Field(default="", max_length=120)
    email: EmailStr
    use: Literal["Exclusive license", "National TV campaign", "Feature film", "Game", "Other"]
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

    @model_validator(mode="after")
    def _uses_rule(self):
        self.uses = [u for u in ("sync", "ai") if u in self.uses]
        if self.kind == "exclusive" and not self.uses:
            raise ValueError("Choose sync, AI training or both.")
        if self.kind != "exclusive":
            self.uses = []
        return self


class AdminReissue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    send_email: bool = True


class AdminDelist(BaseModel):
    model_config = ConfigDict(extra="forbid")
    delisted: bool = Field(..., strict=True)
    reason: str = Field(default="", max_length=500)


class AdminAiToolsReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    result: Literal["approved", "rejected"]
    reason: str = Field(default="", max_length=500)


class AdminHideProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hidden: bool = Field(..., strict=True)
    reason: str = Field(default="", max_length=500)


PROFILE_PUBLIC_FIELDS = ("slug", "display_name", "bio", "location",
                         "spotify_url", "instagram_url", "created_at", "updated_at")


class CompleteUploadRequest(BaseModel):
    submission_id: str


class CosignPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_type: Literal["individual", "company"] = "individual"
    legal_name: str = Field(default="", max_length=120)
    signer_name: Optional[str] = Field(default=None, max_length=120)
    signer_title: Optional[str] = Field(default=None, max_length=120)


class CosignSignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_type: Literal["individual", "company"]
    legal_name: str = Field(..., min_length=1, max_length=120)
    signer_name: Optional[str] = Field(default=None, max_length=120)
    signer_title: Optional[str] = Field(default=None, max_length=120)
    typed_signature: str = Field(..., min_length=1, max_length=120)
    adult_confirmed: bool
    text_sha256: str = Field(..., min_length=64, max_length=64)

    @model_validator(mode="after")
    def _check(self):
        if not self.adult_confirmed:
            raise ValueError("Confirm you are 18 or older.")
        if self.entity_type == "company" and not (self.signer_name and self.signer_title):
            raise ValueError("A company signature needs a signer name and title.")
        return self


class CosignDeclineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Optional[str] = Field(default=None, max_length=500)


class CosignEmailUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(..., max_length=254)

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        v = (v or "").strip().lower()
        if not RIGHTS_EMAIL_PATTERN.fullmatch(v):
            raise ValueError("Enter a valid email.")
        return v


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
                       "matched_isrc", "confidence", "acrid", "raw_code", "matched_offset_s")


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


async def set_clerk_public_metadata(user_id: str, patch: dict) -> None:
    """Merge keys into a user's Clerk public_metadata via the Backend API. Clerk merges the
    top-level public_metadata keys, so existing keys (e.g. role) are preserved."""
    if not CLERK_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Account update is not configured.")
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.patch(f"https://api.clerk.com/v1/users/{quote(user_id, safe='')}/metadata",
                              headers={"Authorization": f"Bearer {CLERK_SECRET_KEY}"},
                              json={"public_metadata": patch})
    except Exception as exc:
        logger.warning("Clerk metadata update failed: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Could not update your account. Please try again.")
    if r.status_code != 200:
        logger.warning("Clerk metadata update returned %s", r.status_code)
        raise HTTPException(status_code=503, detail="Could not update your account. Please try again.")


async def _current_agreement(uid: str) -> Optional[dict]:
    return await db.artist_agreements.find_one(
        {"user_id": uid, "version": artist_agreement.current_version()},
        {"_id": 0, "id": 1, "version": 1, "signed_at": 1, "fields": 1})


def account_legal_name(agreement: Optional[dict]) -> Optional[str]:
    """The licensor named on the signed Artist Agreement: the company for company accounts,
    otherwise the person's legal name. Splits must use this exact name for the uploader."""
    f = (agreement or {}).get("fields") or {}
    name = f.get("company_name") if f.get("entity_type") == "company" else f.get("legal_name")
    return (name or "").strip() or None


def _norm_name(v: str) -> str:
    return " ".join((v or "").split()).casefold()


LEGAL_NAME_MISMATCH = "This does not match the legal name on your account."


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
async def agreement_status(request: Request, clerk_payload: dict = Depends(verify_clerk_token)):
    uid = clerk_payload["sub"]
    version = artist_agreement.current_version()
    signed = await _current_agreement(uid)
    resp = {
        "current_version": version,
        "enforced": artist_agreement.enforced(),
        "required": _role(clerk_payload) != "admin",
        "signed": signed is not None,
        "agreement": {k: v for k, v in (signed or {}).items() if k != "fields"} or None,
        "legal_name": account_legal_name(signed),
        "prefill": None,
        "previous_signed": await db.artist_agreements.find_one(
            {"user_id": uid, "version": {"$ne": version}}, {"_id": 1}) is not None,
        "exclusive_supported": artist_agreement.supports_exclusive(version),
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
                            clerk_payload: dict = Depends(verify_clerk_token)):
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
                         clerk_payload: dict = Depends(verify_clerk_token)):
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
                              attachments=[("OVOXI-Artist-Agreement.pdf", pdf)],
                              idempotency_key=f"agreement-{agreement_id}")
    logger.info("Agreement %s email: %s", agreement_id, result["status"])

    return {"agreement": {"id": agreement_id, "version": version, "signed_at": signed_at}}


@api_router.get("/agreement/pdf")
@limiter.limit("20/minute")
async def agreement_pdf(request: Request, clerk_payload: dict = Depends(verify_clerk_token)):
    doc = await db.artist_agreements.find_one(
        {"user_id": clerk_payload["sub"]}, {"_id": 0, "pdf_key": 1}, sort=[("signed_at", -1)])
    if not doc:
        raise HTTPException(status_code=404, detail="No signed agreement found.")
    url = await asyncio.to_thread(
        r2_client.generate_presigned_url, "get_object",
        Params={"Bucket": R2_BUCKET, "Key": doc["pdf_key"],
                "ResponseContentDisposition": 'attachment; filename="OVOXI-Artist-Agreement.pdf"'},
        ExpiresIn=300)
    return {"url": url}


# ---------------------------------------------------------------------------
# Upload pipeline routes
# ---------------------------------------------------------------------------

@api_router.post("/upload/presign")
@limiter.limit("20/minute")
async def presign_upload(request: Request, payload: PresignRequest, clerk_payload: dict = Depends(require_artist)):
    if os.environ.get("UPLOADS_ENABLED", "true") != "true":
        raise HTTPException(status_code=503, detail="Uploads are temporarily paused")
    agreement = await _require_signed_agreement(clerk_payload)
    if payload.genre not in VALID_GENRES:
        raise HTTPException(status_code=400, detail=f"Invalid genre")
    try:
        genre_other = other_answer(payload.genre, payload.genre_other, GENRE_OTHER_MESSAGE)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    # The uploader's name in the splits must be the licensor on their signed agreement.
    account_name = account_legal_name(agreement)
    if account_name and payload.rights and _norm_name(payload.rights.self_legal_name) != _norm_name(account_name):
        raise HTTPException(status_code=422, detail=LEGAL_NAME_MISMATCH)
    approved = is_approved(clerk_payload)

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
        MAX_OPEN_SUBMISSIONS = int(os.environ.get("MAX_OPEN_SUBMISSIONS", "15"))
        uid = clerk_payload["sub"]
        since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        if await db.track_submissions.count_documents(
            {"clerk_user_id": uid, "upload_date": {"$gte": since}}
        ) >= MAX_UPLOADS_PER_DAY:
            raise HTTPException(status_code=429, detail="Daily upload limit reached")
        if approved and await db.track_submissions.count_documents({
            "clerk_user_id": uid,
            "awaiting_approval": {"$ne": True},
            "$or": [
                {"status": {"$in": ["uploaded", "scanning", "mastering", "processing"]}},
                {"status": "pending", "upload_date": {"$gte": one_hour_ago}},
            ],
        }) >= MAX_OPEN_SUBMISSIONS:
            raise HTTPException(status_code=429, detail="Too many uploads in progress")
        MAX_HELD = int(os.environ.get("MAX_PENDING_APPROVAL_UPLOADS", "25"))
        if not approved and await db.track_submissions.count_documents({
            "clerk_user_id": uid, "awaiting_approval": True, "status": {"$ne": "failed"},
        }) >= MAX_HELD:
            raise HTTPException(status_code=429, detail=(
                f"You can upload up to {MAX_HELD} songs before your account is approved."))

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
    if payload.consent_exclusive:
        # Exclusive needs an agreement with the Exclusive Election clause (v5 and later).
        # Admins upload without a signature, so they are checked against the current version.
        version = (agreement["version"] if agreement
                   else artist_agreement.current_version() if _role(clerk_payload) == "admin" else None)
        if not (version and artist_agreement.supports_exclusive(version)):
            raise HTTPException(status_code=409, detail="Exclusive songs are not available yet.")
        scopes.append("exclusive")
    preview_rights = build_rights(
        payload.rights, intake=payload.sync_intake, clerk_user_id=clerk_user_id, now_iso=now_iso)
    if payload.consent_sync:
        missing_pro = writers_missing_pro(preview_rights)
        if missing_pro:
            raise HTTPException(status_code=422, detail=(
                "Every writer needs a PRO and IPI for sync placements. Missing: "
                + ", ".join(missing_pro) + "."))
    if payload.declarations.loops:
        # Agreement 3.6(a): every loop creator must be a rights holder in the splits,
        # so the Co-owner Consent goes to them like any co-owner.
        listed = rights_emails({"rights": preview_rights})
        missing = [lp.creator_name for lp in payload.declarations.loops if lp.creator_email not in listed]
        if missing:
            raise HTTPException(status_code=422, detail=(
                "Add each loop creator to the splits with the same email: " + ", ".join(missing) + "."))
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
    doc['consent'] = {"ai_training": payload.consent_ai_training, "sync": payload.consent_sync,
                      "exclusive": payload.consent_exclusive}
    doc['consent_grant_version'] = GRANT_VERSION
    doc['agreement_id'] = agreement["id"] if agreement else None
    # Held until the artist is approved: not processed, not listed, no co-owner emails.
    doc['awaiting_approval'] = not approved
    doc['genre_other'] = genre_other
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
    # Samples and AI tools are answered on every upload (Brief 25b D1); sync adds its own.
    doc['intake'] = payload.declarations.intake_fields(now_iso)
    if payload.consent_sync:
        doc['intake'].update({
            "distributor": payload.sync_intake.distributor,
            "distributor_other": payload.sync_intake.distributor_other,
            "content_id": payload.sync_intake.content_id,
            "pro_not_affiliated": payload.sync_intake.pro_not_affiliated,
            "pro_name": payload.sync_intake.pro_name,
            "pro_other": payload.sync_intake.pro_other,
            "ipi": payload.sync_intake.ipi,
            "sync_sole_attested_at": now_iso,
        })
    doc['rights'] = build_rights(
        payload.rights, intake=payload.sync_intake,
        clerk_user_id=clerk_user_id, now_iso=now_iso,
    )
    # Co-owner sign-off (Brief 22 C2). A track needs every non-uploader rights holder to
    # sign before it can be licensed. The absence of these fields is what grandfathers
    # tracks uploaded before this shipped.
    has_coowner = any(
        not p.get("is_self")
        for side in ("writers", "publishers", "master_owners")
        for p in (doc['rights'].get(side) or [])
    )
    doc['cosign_required'] = has_coowner
    doc['cosign_status'] = "pending" if has_coowner else "not_required"
    await db.track_submissions.insert_one(doc)

    return {
        "presigned_url": presigned_url,
        "submission_id": submission_id,
        "r2_key": r2_key,
        "content_type": content_type,
    }


@api_router.post("/upload/complete")
@limiter.limit("20/minute")
async def complete_upload(request: Request, payload: CompleteUploadRequest, background: BackgroundTasks,
                          clerk_payload: dict = Depends(require_artist)):
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

    # Co-owner Consent requests (Brief 22 C3). Sent after the response (Brief 25b C6):
    # each email could take up to 10 s, and the upload must not wait for them. Safe to
    # repeat: existing requests are left alone, and an email failure never fails the upload.
    if sub.get("cosign_required") and not sub.get("awaiting_approval"):
        background.add_task(_dispatch_cosign_quietly, sub)

    return {"status": "uploaded", "submission_id": payload.submission_id}


@api_router.get('/vault/tracks')
@limiter.limit("30/minute")
async def get_vault_tracks(request: Request, clerk_payload: dict = Depends(verify_clerk_token)):
    clerk_user_id = clerk_payload.get('sub')
    # Backup release path: an artist approved by hand in Clerk gets their held songs
    # processed the next time they open the Vault.
    if is_approved(clerk_payload):
        await _release_held_uploads(clerk_user_id)
    subs = await db.track_submissions.find(
        {'clerk_user_id': clerk_user_id},
        {'_id': 0, 'id': 1, 'artist_name': 1, 'track_name': 1, 'genre': 1,
         'upload_date': 1, 'status': 1, 'stem_paths': 1, 'mastered_r2_key': 1,
         'consent': 1, 'metadata': 1, 'sync_status': 1, 'checks': 1, 'on_sync_profile': 1,
         'cosign_required': 1, 'cosign_status': 1, 'awaiting_approval': 1},
    ).sort('upload_date', -1).to_list(1000)

    cosign_by_track = await _cosign_views_for_tracks([s.get('id') for s in subs])

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
            'cosign': cosign_by_track.get(s.get('id'), []),
            'awaiting_approval': s.get('awaiting_approval') is True,
            **vault_track_view(s),
        })
    return result


# ---------------------------------------------------------------------------
# Co-owner Consent (Brief 22, Part C)
# ---------------------------------------------------------------------------

REPLY_TO_COSIGN = "tyler@ovoxi.net"
COSIGN_LINK_BASE = "https://ovoxi.net/cosign"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _new_cosign_token() -> tuple:
    token = secrets.token_urlsafe(32)
    return token, _hash_token(token)


def _cosign_expired(req: dict, now: datetime) -> bool:
    exp = req.get("token_expires_at")
    if not exp:
        return False
    try:
        return datetime.fromisoformat(exp) < now
    except ValueError:
        return False


def _cosign_uses(sub: dict) -> list:
    consent = sub.get("consent") or {}
    uses = []
    if consent.get("ai_training"):
        uses.append("AI training")
    if consent.get("sync"):
        uses.append("Sync licensing")
    return uses


def _uploader_name(sub: dict) -> str:
    return (sub.get("rights") or {}).get("self_legal_name") or sub.get("artist_name") or ""


def _cosign_interests_by_email(sub: dict) -> dict:
    """email -> list of interest dicts, one per non-self rights row with that email."""
    rights = sub.get("rights") or {}
    by_email: dict = {}
    for side in ("writers", "publishers", "master_owners"):
        for p in (rights.get(side) or []):
            if p.get("is_self"):
                continue
            email = (p.get("email") or "").strip().lower()
            if not email:
                continue
            by_email.setdefault(email, []).append({
                "side": side, "legal_name": p.get("legal_name"),
                "role": p.get("role"), "share_bp": p.get("share_bp"),
            })
    return by_email


async def _uploader_agreement_version(sub: dict) -> str:
    aid = sub.get("agreement_id")
    if aid:
        a = await db.artist_agreements.find_one({"id": aid}, {"_id": 0, "version": 1})
        if a and a.get("version"):
            return a["version"]
    return artist_agreement.current_version()


async def _uploader_email(sub: dict) -> Optional[str]:
    uid = (sub or {}).get("clerk_user_id")
    if not uid:
        return None
    try:
        return (await fetch_clerk_user(uid)).get("email")
    except Exception:
        return None


async def _send_cosign_request(req: dict, token: str, uploader_name: str,
                               work_title: str, interests: list, uses: list) -> None:
    """Send the invite and record it. Never raises; a failure leaves sent_at null so the
    Vault shows "Not sent"."""
    link = f"{COSIGN_LINK_BASE}/{token}"
    subject, html, text = cosign.request_email(
        uploader_name=uploader_name, work_title=work_title,
        interests=interests, uses=uses, link=link)
    try:
        result = await send_email(to=req["email"], subject=subject, html=html, text=text,
                                  reply_to=REPLY_TO_COSIGN,
                                  idempotency_key=f"cosign-req-{req['id']}-{req.get('send_count', 0)}")
    except Exception as exc:
        logger.warning("cosign invite send raised for %s: %s", req["id"], exc)
        return
    if result.get("status") == "sent":
        now = datetime.now(timezone.utc).isoformat()
        await db.cosign_requests.update_one(
            {"id": req["id"]},
            {"$set": {"sent_at": now, "last_sent_at": now}, "$inc": {"send_count": 1}})
    else:
        logger.warning("cosign invite not sent req=%s status=%s", req["id"], result.get("status"))


async def _release_held_uploads(uid: str) -> int:
    """Start processing an approved artist's held songs (Oct 26). Songs whose file already
    arrived (status "uploaded") join the worker queue; their co-owner emails go out now.
    Returns how many were released. Safe to repeat."""
    held = await db.track_submissions.find(
        {"clerk_user_id": uid, "awaiting_approval": True}, {"_id": 0}).to_list(500)
    if not held:
        return 0
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.track_submissions.update_many(
        {"clerk_user_id": uid, "awaiting_approval": True},
        {"$set": {"awaiting_approval": False, "approved_at": now_iso}})
    for sub in held:
        if sub.get("status") == "uploaded" and sub.get("cosign_required"):
            await _dispatch_cosign_quietly(sub)
    logger.info("Released %d held uploads for %s", len(held), uid)
    return len(held)


async def _dispatch_cosign_quietly(sub: dict) -> None:
    try:
        await _dispatch_cosign_requests(sub)
    except Exception as exc:
        logger.error("cosign dispatch failed for %s: %s", sub.get("id"), exc)


async def _dispatch_cosign_requests(sub: dict) -> None:
    """Create one request per unique co-owner email and email each. Idempotent: an
    existing (track_id, email) request is left untouched, so a repeated complete is safe."""
    track_id = sub["id"]
    uploader_name = _uploader_name(sub)
    uses = _cosign_uses(sub)
    now = datetime.now(timezone.utc)
    for email, interests in _cosign_interests_by_email(sub).items():
        existing = await db.cosign_requests.find_one(
            {"track_id": track_id, "email": email}, {"_id": 0, "id": 1})
        if existing:
            continue
        token, token_hash = _new_cosign_token()
        req = {
            "id": str(uuid.uuid4()), "track_id": track_id,
            "uploader_clerk_user_id": sub.get("clerk_user_id"),
            "email": email, "interests": interests,
            "token_sha256": token_hash,
            "token_expires_at": (now + timedelta(days=COSIGN_TOKEN_TTL_DAYS)).isoformat(),
            "status": "pending", "created_at": now.isoformat(),
            "sent_at": None, "send_count": 0, "last_sent_at": None,
            "signed_at": None, "typed_signature": None, "entity_type": None,
            "signer_name": None, "signer_title": None, "legal_name": None,
            "ip": None, "consent_version": cosign.current_version(),
            "text_sha256": None, "pdf_key": None,
            "declined_at": None, "decline_reason": None,
        }
        try:
            await db.cosign_requests.insert_one(req)
        except DuplicateKeyError:
            continue  # created concurrently
        await _send_cosign_request(req, token, uploader_name, sub.get("track_name"), interests, uses)


async def _cosign_views_for_tracks(track_ids: list) -> dict:
    """track_id -> list of public cosign rows for the Vault (never token data)."""
    ids = [t for t in track_ids if t]
    if not ids:
        return {}
    reqs = await db.cosign_requests.find(
        {"track_id": {"$in": ids}},
        {"_id": 0, "id": 1, "track_id": 1, "interests": 1, "email": 1, "status": 1,
         "sent_at": 1, "signed_at": 1, "declined_at": 1},
    ).to_list(1000)
    out: dict = {}
    for r in reqs:
        names = []
        for it in (r.get("interests") or []):
            n = it.get("legal_name")
            if n and n not in names:
                names.append(n)
        out.setdefault(r["track_id"], []).append({
            "request_id": r["id"], "legal_names": names, "email": r.get("email"),
            "status": r.get("status"), "sent_at": r.get("sent_at"),
            "signed_at": r.get("signed_at"), "declined_at": r.get("declined_at"),
        })
    return out


async def _email_cosign_complete(sub: dict) -> None:
    from xml.sax.saxutils import escape
    track = sub.get("track_name") or "your track"
    body = f'Everyone has signed for "{track}". It can now be licensed.'
    to = await _uploader_email(sub)
    if to:
        await send_email(to=to, subject=f'Everyone signed for "{track}"',
                         html=f"<p>{escape(body)}</p>", text=body, reply_to=REPLY_TO_COSIGN,
                         idempotency_key=f"cosign-complete-{sub['id']}")


async def _email_cosign_declined(req: dict, sub: dict) -> None:
    from xml.sax.saxutils import escape
    track = (sub or {}).get("track_name") or "your track"
    names = ", ".join(dict.fromkeys(
        it.get("legal_name") for it in (req.get("interests") or []) if it.get("legal_name"))
    ) or req.get("email")
    body = (f'{names} declined to sign for "{track}". The song stays off the catalog. '
            "Check the splits and contact them.")
    for to in filter(None, [await _uploader_email(sub), REPLY_TO_COSIGN]):
        await send_email(to=to, subject=f'A co-owner declined to sign for "{track}"',
                         html=f"<p>{escape(body)}</p>", text=body, reply_to=REPLY_TO_COSIGN,
                         idempotency_key=f"cosign-declined-{req['id']}-{to}")


async def _refresh_cosign_status(track_id: str) -> None:
    """Roll the per-request statuses up to the track, re-run clearance, and tell the
    uploader when the last signature lands."""
    reqs = await db.cosign_requests.find(
        {"track_id": track_id}, {"_id": 0, "status": 1}).to_list(1000)
    statuses = [r.get("status") for r in reqs]
    if any(s == "declined" for s in statuses):
        new_status = "declined"
    elif statuses and all(s == "signed" for s in statuses):
        new_status = "complete"
    else:
        new_status = "pending"
    sub = await db.track_submissions.find_one(
        {"id": track_id}, {"_id": 0, "id": 1, "cosign_status": 1, "track_name": 1, "clerk_user_id": 1})
    if not sub:
        return
    prev = sub.get("cosign_status")
    if prev != new_status:
        await db.track_submissions.update_one({"id": track_id}, {"$set": {"cosign_status": new_status}})
    await _run_clearance(track_id)
    if new_status == "complete" and prev != "complete":
        try:
            await _email_cosign_complete(sub)
        except Exception as exc:
            logger.warning("cosign complete email failed for %s: %s", track_id, exc)


async def _cosign_request_for_token(token: str) -> Optional[dict]:
    return await db.cosign_requests.find_one({"token_sha256": _hash_token(token)}, {"_id": 0})


async def _cosign_public_payload(req: dict, now: datetime, *, entity_type="individual",
                                 legal_name=None, signer_name="", signer_title="") -> dict:
    sub = await db.track_submissions.find_one({"id": req["track_id"]}, {"_id": 0})
    if not sub:
        raise HTTPException(status_code=404,
                            detail="This link has expired or is not valid. Ask the artist to resend it.")
    aa_version = await _uploader_agreement_version(sub)
    name = legal_name if legal_name is not None else (
        req["interests"][0]["legal_name"] if req.get("interests") else "")
    values = cosign.build_values(
        now=now, entity_type=entity_type, legal_name=name, coowner_email=req["email"],
        uploader_name=_uploader_name(sub), artist_agreement_version=aa_version,
        work_title=sub.get("track_name"), work_artist=sub.get("artist_name"),
        work_id=sub.get("id"), interests=req["interests"],
        signer_name=signer_name or "", signer_title=signer_title or "")
    text = cosign.render_text(values)
    agreement_text = artist_agreement.load_template(aa_version)
    return {
        "track_title": sub.get("track_name"),
        "artist_name": sub.get("artist_name"),
        "uploader_name": _uploader_name(sub),
        "interests": req["interests"],
        "uses": _cosign_uses(sub),
        "consent_version": cosign.current_version(),
        "consent_blocks": cosign.blocks(text),
        "text_sha256": cosign.text_sha256(text),
        "agreement_version": aa_version,
        "agreement_blocks": artist_agreement.blocks(agreement_text),
    }


def _cosign_resolved(req: dict):
    if req["status"] in ("signed", "declined"):
        raise HTTPException(status_code=409, detail={
            "status": req["status"], "date": req.get("signed_at") or req.get("declined_at")})


@api_router.get("/cosign/{token}")
@limiter.limit("10/minute")
async def cosign_get(request: Request, token: str):
    req = await _cosign_request_for_token(token)
    now = datetime.now(timezone.utc)
    if not req or _cosign_expired(req, now):
        raise HTTPException(status_code=404,
                            detail="This link has expired or is not valid. Ask the artist to resend it.")
    _cosign_resolved(req)
    return await _cosign_public_payload(req, now)


@api_router.post("/cosign/{token}/preview")
@limiter.limit("10/minute")
async def cosign_preview(request: Request, token: str, payload: CosignPreviewRequest):
    req = await _cosign_request_for_token(token)
    now = datetime.now(timezone.utc)
    if not req or _cosign_expired(req, now):
        raise HTTPException(status_code=404,
                            detail="This link has expired or is not valid. Ask the artist to resend it.")
    _cosign_resolved(req)
    data = await _cosign_public_payload(
        req, now, entity_type=payload.entity_type, legal_name=payload.legal_name,
        signer_name=payload.signer_name or "", signer_title=payload.signer_title or "")
    return {"consent_blocks": data["consent_blocks"], "text_sha256": data["text_sha256"]}


@api_router.post("/cosign/{token}/sign")
@limiter.limit("10/minute")
async def cosign_sign(request: Request, token: str, payload: CosignSignRequest):
    req = await _cosign_request_for_token(token)
    now = datetime.now(timezone.utc)
    if not req or _cosign_expired(req, now):
        raise HTTPException(status_code=404,
                            detail="This link has expired or is not valid. Ask the artist to resend it.")
    _cosign_resolved(req)

    norm = lambda s: " ".join(s.split()).casefold()
    expected = payload.signer_name if payload.entity_type == "company" else payload.legal_name
    if norm(payload.typed_signature) != norm(expected or ""):
        raise HTTPException(status_code=422, detail="Type your full name exactly as entered above.")

    sub = await db.track_submissions.find_one({"id": req["track_id"]}, {"_id": 0})
    if not sub:
        raise HTTPException(status_code=404,
                            detail="This link has expired or is not valid. Ask the artist to resend it.")
    aa_version = await _uploader_agreement_version(sub)
    values = cosign.build_values(
        now=now, entity_type=payload.entity_type, legal_name=payload.legal_name,
        coowner_email=req["email"], uploader_name=_uploader_name(sub),
        artist_agreement_version=aa_version, work_title=sub.get("track_name"),
        work_artist=sub.get("artist_name"), work_id=sub.get("id"), interests=req["interests"],
        signer_name=payload.signer_name or "", signer_title=payload.signer_title or "")
    text = cosign.render_text(values)
    text_hash = cosign.text_sha256(text)
    if text_hash != payload.text_sha256:
        raise HTTPException(status_code=409, detail="The document changed. Please review it again.")

    signed_at = now.isoformat()
    ip = get_real_client_ip(request)
    sig = {"request_id": req["id"], "version": cosign.current_version(), "work_id": sub.get("id"),
           "text_sha256": text_hash, "signed_at": signed_at,
           "typed_signature": " ".join(payload.typed_signature.split()),
           "entity_type": payload.entity_type, "legal_name": payload.legal_name,
           "signer_name": payload.signer_name or "", "signer_title": payload.signer_title or "",
           "coowner_email": req["email"], "ip": ip}
    pdf = await asyncio.to_thread(cosign.render_pdf, text, sig)
    pdf_key = f"cosigns/{req['track_id']}/{req['id']}.pdf"
    try:
        await asyncio.to_thread(r2_client.put_object, Bucket=R2_BUCKET, Key=pdf_key, Body=pdf,
                                ContentType="application/pdf")
    except Exception as exc:
        logger.error("cosign PDF upload failed for %s: %s", req["id"], exc)
        raise HTTPException(status_code=503, detail="Could not save your signature. Please try again.")

    updated = await db.cosign_requests.update_one(
        {"id": req["id"], "status": "pending"},
        {"$set": {"status": "signed", "signed_at": signed_at, "typed_signature": sig["typed_signature"],
                  "entity_type": payload.entity_type, "signer_name": payload.signer_name,
                  "signer_title": payload.signer_title, "legal_name": payload.legal_name,
                  "ip": ip, "consent_version": cosign.current_version(),
                  "text_sha256": text_hash, "pdf_key": pdf_key}})
    if updated.matched_count == 0:
        raise HTTPException(status_code=409, detail={"status": "signed", "date": signed_at})

    subject, html, body = cosign.signed_copy_email(work_title=sub.get("track_name"))
    try:
        await send_email(to=req["email"], subject=subject, html=html, text=body,
                         attachments=[("OVOXI-Co-owner-Consent.pdf", pdf)],
                         reply_to=REPLY_TO_COSIGN, idempotency_key=f"cosign-signed-{req['id']}")
    except Exception as exc:
        logger.warning("cosign signed-copy email failed for %s: %s", req["id"], exc)

    await _refresh_cosign_status(req["track_id"])
    return {"status": "signed"}


@api_router.post("/cosign/{token}/decline")
@limiter.limit("10/minute")
async def cosign_decline(request: Request, token: str, payload: CosignDeclineRequest):
    req = await _cosign_request_for_token(token)
    now = datetime.now(timezone.utc)
    if not req or _cosign_expired(req, now):
        raise HTTPException(status_code=404,
                            detail="This link has expired or is not valid. Ask the artist to resend it.")
    _cosign_resolved(req)
    declined_at = now.isoformat()
    updated = await db.cosign_requests.update_one(
        {"id": req["id"], "status": "pending"},
        {"$set": {"status": "declined", "declined_at": declined_at, "decline_reason": payload.reason}})
    if updated.matched_count == 0:
        raise HTTPException(status_code=409, detail={"status": "declined", "date": declined_at})
    sub = await db.track_submissions.find_one(
        {"id": req["track_id"]}, {"_id": 0, "track_name": 1, "clerk_user_id": 1})
    try:
        await _email_cosign_declined(req, sub)
    except Exception as exc:
        logger.warning("cosign decline email failed for %s: %s", req["id"], exc)
    await _refresh_cosign_status(req["track_id"])
    return {"status": "declined"}


@api_router.post("/vault/tracks/{track_id}/cosign/{request_id}/resend")
@limiter.limit("30/minute")
async def cosign_resend(request: Request, track_id: str, request_id: str,
                        clerk_payload: dict = Depends(require_artist)):
    sub = await _owned_track(track_id, clerk_payload)
    req = await db.cosign_requests.find_one(
        {"id": request_id, "track_id": track_id}, {"_id": 0})
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req["status"] != "pending":
        raise HTTPException(status_code=409, detail="This request is already resolved.")
    now = datetime.now(timezone.utc)
    if max(req.get("send_count", 0) - 1, 0) >= COSIGN_MAX_RESENDS:
        raise HTTPException(status_code=429, detail="This invite has been resent the maximum number of times.")
    last = req.get("last_sent_at")
    if last and (now - datetime.fromisoformat(last)) < timedelta(minutes=COSIGN_RESEND_COOLDOWN_MIN):
        raise HTTPException(status_code=429, detail="You can resend this invite once an hour.")
    token, token_hash = _new_cosign_token()
    await db.cosign_requests.update_one({"id": request_id}, {"$set": {
        "token_sha256": token_hash,
        "token_expires_at": (now + timedelta(days=COSIGN_TOKEN_TTL_DAYS)).isoformat()}})
    await _send_cosign_request({**req, "token_sha256": token_hash}, token, _uploader_name(sub),
                               sub.get("track_name"), req["interests"], _cosign_uses(sub))
    return {"status": "sent"}


@api_router.patch("/vault/tracks/{track_id}/cosign/{request_id}")
@limiter.limit("30/minute")
async def cosign_edit_email(request: Request, track_id: str, request_id: str,
                            payload: CosignEmailUpdate, clerk_payload: dict = Depends(require_artist)):
    sub = await _owned_track(track_id, clerk_payload)
    req = await db.cosign_requests.find_one(
        {"id": request_id, "track_id": track_id}, {"_id": 0})
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req["status"] != "pending":
        raise HTTPException(status_code=409, detail="This request is already resolved.")
    new_email = payload.email
    dupe = await db.cosign_requests.find_one(
        {"track_id": track_id, "email": new_email, "id": {"$ne": request_id}}, {"_id": 0, "id": 1})
    if dupe:
        raise HTTPException(status_code=409, detail="Another co-owner on this track already has that email.")
    old_email = req["email"]
    now = datetime.now(timezone.utc)
    token, token_hash = _new_cosign_token()
    await db.cosign_requests.update_one({"id": request_id}, {"$set": {
        "email": new_email, "token_sha256": token_hash,
        "token_expires_at": (now + timedelta(days=COSIGN_TOKEN_TTL_DAYS)).isoformat()}})
    await _update_rights_email(track_id, old_email, new_email)
    await _send_cosign_request({**req, "email": new_email, "token_sha256": token_hash}, token,
                               _uploader_name(sub), sub.get("track_name"),
                               req["interests"], _cosign_uses(sub))
    return {"status": "sent", "email": new_email}


async def _update_rights_email(track_id: str, old_email: str, new_email: str) -> None:
    doc = await db.track_submissions.find_one({"id": track_id}, {"_id": 0, "rights": 1})
    rights = (doc or {}).get("rights") or {}
    changed = False
    for side in ("writers", "publishers", "master_owners"):
        for p in (rights.get(side) or []):
            if (p.get("email") or "").strip().lower() == old_email:
                p["email"] = new_email
                changed = True
    if changed:
        await db.track_submissions.update_one({"id": track_id}, {"$set": {"rights": rights}})


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
    fields = metadata_patch_fields(payload.bpm, payload.key, payload.moods, payload.genre,
                                   payload.genre_other)
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

    # Brief 25b: one song-level Exclusive choice (Agreement 3.4). Turning it off applies
    # to future deals at once (3.4(j)); a use already sold exclusively stays exclusive.
    if payload.scope == "exclusive":
        want = payload.action == "grant"
        if exclusive.is_exclusive(doc) == want:
            raise HTTPException(status_code=409,
                                detail=f"Exclusive is already {'on' if want else 'off'}.")
        agreement = None
        if want:
            if not exclusive.opted_uses(doc):
                raise HTTPException(status_code=409, detail="Turn on AI training or sync placements first.")
            if not artist_agreement.supports_exclusive(artist_agreement.current_version()):
                raise HTTPException(status_code=409, detail="Exclusive songs are not available yet.")
            agreement = await _current_agreement(clerk_payload["sub"])
            if agreement is None and _role(clerk_payload) != "admin":
                raise HTTPException(status_code=403, detail="Sign the latest Artist Agreement first.")
        elif exclusive.fully_sold(doc):
            raise HTTPException(
                status_code=409,
                detail=(f"This song is already licensed exclusively for "
                        f"{exclusive.uses_label(exclusive.sold_uses(doc))}. Exclusive can't be turned off."))
        try:
            if want:
                await record_grants(db, user_id=clerk_payload["sub"], track_id=track_id,
                                     scopes=["exclusive"], source="vault",
                                     ip=get_real_client_ip(request), agreement=agreement)
            else:
                await record_withdrawals(db, user_id=clerk_payload["sub"], track_id=track_id,
                                         scopes=["exclusive"], source="vault",
                                         ip=get_real_client_ip(request))
        except Exception as exc:
            logger.error("Consent ledger write failed for %s: %s", track_id, exc)
            raise HTTPException(status_code=503, detail="Could not record consent. Please try again.")
        await db.track_submissions.update_one(
            {"id": track_id, "clerk_user_id": clerk_payload["sub"]}, {"$set": {"consent.exclusive": want}})
        doc = await _owned_track(track_id, clerk_payload)
        return {"id": track_id, **vault_track_view(doc)}

    want = payload.action == "grant"
    if (doc["consent"].get(payload.scope) is True) == want:
        label = {"ai_training": "AI training", "sync": "Sync"}.get(payload.scope, payload.scope)
        raise HTTPException(status_code=409, detail=f"{label} is already {'on' if want else 'off'}.")

    # PRD-03 3.4: every change is a new consent event, written first. Grants are gated;
    # withdrawals never are, so an artist can always opt out.
    if (payload.scope == "ai_training" and want
            and (doc.get("intake") or {}).get("samples") in ("royalty_free_loop", "cleared_sample")):
        raise HTTPException(status_code=409, detail=LOOPS_NO_AI_MESSAGE)
    shortcut_rights = None
    if payload.scope == "sync" and want:
        rights = doc.get("rights") or {}
        if rights.get("owns_everything") and (rights.get("writers") or []):
            # The 100% shortcut takes the uploader's PRO from the sync answers.
            rights = {**rights, "writers": [{**w, "society": payload.sync_intake.pro_name,
                                             "society_other": payload.sync_intake.pro_other,
                                             "ipi_name_number": payload.sync_intake.ipi}
                                            if w.get("is_self") else w for w in rights["writers"]]}
            shortcut_rights = rights
        missing_pro = writers_missing_pro(rights)
        if missing_pro:
            raise HTTPException(status_code=422, detail=(
                "Every writer needs a PRO and IPI for sync placements. Missing: "
                + ", ".join(missing_pro) + "."))
    agreement = await _require_signed_agreement(clerk_payload) if want else None

    try:
        if want:
            await record_grants(db, user_id=clerk_payload["sub"], track_id=track_id,
                                 scopes=[payload.scope], source="vault",
                                 ip=get_real_client_ip(request), agreement=agreement)
        else:
            await record_withdrawals(db, user_id=clerk_payload["sub"], track_id=track_id,
                                     scopes=[payload.scope], source="vault",
                                     ip=get_real_client_ip(request))
    except Exception as exc:
        logger.error("Consent ledger write failed for %s: %s", track_id, exc)
        raise HTTPException(status_code=503, detail="Could not record consent. Please try again.")

    now_iso = datetime.now(timezone.utc).isoformat()
    fields: dict = {f"consent.{payload.scope}": want}
    if payload.scope == "sync" and want:
        # Dotted paths: the samples and AI-tools answers already on the track are kept.
        i = payload.sync_intake
        fields.update({
            "intake.distributor": i.distributor, "intake.distributor_other": i.distributor_other,
            "intake.content_id": i.content_id,
            "intake.pro_not_affiliated": False, "intake.pro_name": i.pro_name,
            "intake.pro_other": i.pro_other,
            "intake.ipi": i.ipi, "intake.sync_sole_attested_at": now_iso,
        })
        if shortcut_rights is not None:
            fields["rights"] = shortcut_rights
        if i.samples is not None:
            fields.update({"intake.samples": i.samples, "intake.samples_attested_at": now_iso})
    elif payload.scope == "sync":
        # Off the catalog for sync sales; licenses already sold stay valid. Clearance
        # below keeps the track listed if it is still cleared for AI training.
        fields.update({"sync_delisted_at": now_iso, "sync_status": None})
    await db.track_submissions.update_one(
        {"id": track_id, "clerk_user_id": clerk_payload["sub"]}, {"$set": fields})
    await _run_clearance(track_id)      # every use change re-evaluates both uses
    doc = await _owned_track(track_id, clerk_payload)
    return {"id": track_id, **vault_track_view(doc)}


def _loop_keys(loops) -> list:
    return [(lp.get("creator_email"), lp.get("loop_name"), lp.get("license_key")) for lp in (loops or [])]


class LoopLicensePresign(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str = Field(..., min_length=1, max_length=200)
    content_type: str
    file_size: int = Field(..., gt=0)


def _owned_loop(doc: dict, index: int) -> dict:
    loops = (doc.get("intake") or {}).get("loops") or []
    if not 0 <= index < len(loops):
        raise HTTPException(status_code=404, detail="Loop not found")
    return loops[index]


@api_router.post("/vault/tracks/{track_id}/loops/{index}/license/presign")
@limiter.limit("20/minute")
async def presign_loop_license(request: Request, track_id: str, index: int, payload: LoopLicensePresign,
                               clerk_payload: dict = Depends(require_artist)):
    """Agreement 3.6(c): upload the license for one loop (PDF, PNG or JPG, up to 10 MB)."""
    doc = await _owned_track(track_id, clerk_payload)
    _owned_loop(doc, index)
    ext = LOOP_LICENSE_TYPES.get(payload.content_type)
    if not ext:
        raise HTTPException(status_code=422, detail="Upload the license as a PDF, PNG or JPG.")
    if payload.file_size > LOOP_LICENSE_MAX_BYTES:
        raise HTTPException(status_code=422, detail="The license file must be 10 MB or smaller.")
    key = f"loop-licenses/{track_id}/{index}-{uuid.uuid4().hex}{ext}"
    await db.track_submissions.update_one(
        {"id": track_id, "clerk_user_id": clerk_payload["sub"]},
        {"$set": {f"intake.loops.{index}.pending_license_key": key,
                  f"intake.loops.{index}.pending_license_size": payload.file_size}})
    url = r2_client.generate_presigned_url(
        "put_object", Params={"Bucket": R2_BUCKET, "Key": key, "ContentType": payload.content_type},
        ExpiresIn=900)
    return {"presigned_url": url, "content_type": payload.content_type}


@api_router.post("/vault/tracks/{track_id}/loops/{index}/license/complete")
@limiter.limit("20/minute")
async def complete_loop_license(request: Request, track_id: str, index: int,
                                clerk_payload: dict = Depends(require_artist)):
    doc = await _owned_track(track_id, clerk_payload)
    loop = _owned_loop(doc, index)
    key = loop.get("pending_license_key")
    if not key:
        raise HTTPException(status_code=409, detail="Start the license upload first.")
    try:
        head = await asyncio.to_thread(r2_client.head_object, Bucket=R2_BUCKET, Key=key)
    except ClientError:
        raise HTTPException(status_code=400, detail="License file not found. Upload it again.")
    if head.get("ContentLength", 0) > LOOP_LICENSE_MAX_BYTES:
        raise HTTPException(status_code=400, detail="The license file must be 10 MB or smaller.")
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.track_submissions.update_one(
        {"id": track_id, "clerk_user_id": clerk_payload["sub"]},
        {"$set": {f"intake.loops.{index}.license_key": key,
                  f"intake.loops.{index}.license_uploaded_at": now_iso,
                  f"intake.loops.{index}.pending_license_key": None,
                  "loop_licenses_reviewed": None}})    # a new file needs a new review
    await _run_clearance(track_id)
    doc = await _owned_track(track_id, clerk_payload)
    return {"id": track_id, **vault_track_view(doc)}


@api_router.post("/vault/tracks/{track_id}/declarations")
@limiter.limit("10/minute")
async def set_vault_declarations(request: Request, track_id: str, payload: Declarations,
                                 clerk_payload: dict = Depends(require_artist)):
    """Brief 25b D1: answer (or update) the samples and AI-tools questions for a track,
    for older uploads that never asked them. A changed AI-tools answer needs a new
    admin review when it is "partial"."""
    doc = await _owned_track(track_id, clerk_payload)
    if is_legacy(doc):
        raise HTTPException(status_code=409, detail="This track has no usage choices recorded.")
    if payload.samples == "royalty_free_loop" and (doc.get("consent") or {}).get("ai_training"):
        raise HTTPException(status_code=409, detail=LOOPS_NO_AI_MESSAGE + " Turn off AI training first.")
    if payload.loops:
        listed = rights_emails(doc)
        missing = [lp.creator_name for lp in payload.loops if lp.creator_email not in listed]
        if missing:
            raise HTTPException(status_code=422, detail=(
                "Add each loop creator to the splits with the same email: " + ", ".join(missing) + "."))
    now_iso = datetime.now(timezone.utc).isoformat()
    old = doc.get("intake") or {}
    new = payload.intake_fields(now_iso, previous_loops=old.get("loops"))
    fields = {f"intake.{k}": v for k, v in new.items()}
    if (old.get("ai_tools"), old.get("ai_tools_detail")) != (new["ai_tools"], new["ai_tools_detail"]):
        fields["ai_tools_reviewed"] = None
    if _loop_keys(old.get("loops")) != _loop_keys(new["loops"]):
        fields["loop_licenses_reviewed"] = None
    await db.track_submissions.update_one(
        {"id": track_id, "clerk_user_id": clerk_payload["sub"]}, {"$set": fields})
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


def _preview_rate_key(request: Request) -> str:
    """Rate-limit bucket for the preview endpoint. Signed-in callers (any
    bearer token present) get a higher tier than anonymous ones; real token
    verification still happens in the endpoint via optional_clerk."""
    ip = get_real_client_ip(request)
    signed_in = bool((request.headers.get("authorization") or "").strip())
    return f"{'in' if signed_in else 'out'}:{ip}"


def _preview_rate_limit(key: str) -> str:
    return "60/minute;1000/day" if key.startswith("in:") else "20/minute;200/day"


@api_router.post("/sync/tracks/{track_id}/preview")
@limiter.limit(_preview_rate_limit, key_func=_preview_rate_key)
async def get_public_preview(request: Request, track_id: str, viewer: Optional[dict] = Depends(optional_clerk)):
    doc, _, _ = await _visible_track(track_id, viewer)
    # Signed in (incl. owner/admin): full song. Signed out: 60-second excerpt
    # only, and never a fallback to the full file.
    signed_in = viewer is not None
    key = doc.get("preview_key") if signed_in else doc.get("preview_short_key")
    if not key:
        raise HTTPException(status_code=404, detail="Preview unavailable")
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
    return {"url": url, "expires_in": PREVIEW_URL_TTL, "excerpt": not signed_in}


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


@api_router.post("/admin/sync/tracks/{track_id}/ai-tools-review")
@limiter.limit("30/minute")
async def admin_ai_tools_review(request: Request, track_id: str, payload: AdminAiToolsReview,
                                admin: dict = Depends(require_admin)):
    """Brief 25b D1: approve or reject a track whose artist said AI generated part of it.
    Rejecting fails the ai_tools check, which takes the track off the catalog."""
    doc = await db.track_submissions.find_one({"id": track_id}, {"_id": 0, "id": 1, "intake": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="Track not found")
    if (doc.get("intake") or {}).get("ai_tools") != "partial":
        raise HTTPException(status_code=409, detail="This track does not need an AI tools review.")
    review = {"result": payload.result, "by": admin.get("sub"),
              "at": datetime.now(timezone.utc).isoformat()}
    await db.track_submissions.update_one({"id": track_id}, {"$set": {"ai_tools_reviewed": review}})
    await _log_admin_action(admin, f"ai_tools_{payload.result}", track_id, payload.reason)
    await _run_clearance(track_id)
    doc = await db.track_submissions.find_one(
        {"id": track_id}, {"_id": 0, "id": 1, "sync_status": 1, "ai_status": 1,
                           "on_sync_profile": 1, "ai_tools_reviewed": 1})
    return doc


@api_router.get("/admin/sync/tracks/{track_id}/loops/{index}/license")
@limiter.limit("60/minute")
async def admin_loop_license(request: Request, track_id: str, index: int,
                             admin: dict = Depends(require_admin)):
    """A short-lived link to view one uploaded loop license."""
    doc = await db.track_submissions.find_one({"id": track_id}, {"_id": 0, "intake": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="Track not found")
    loop = _owned_loop(doc, index)
    if not loop.get("license_key"):
        raise HTTPException(status_code=404, detail="No license uploaded for this loop")
    return {"url": _signed_get(loop["license_key"], ttl=600), **{k: loop.get(k) for k in (
        "creator_name", "creator_email", "source", "loop_name", "license_uploaded_at")}}


class AdminExclusiveLicense(BaseModel):
    """Brief 25b D5: record an exclusive license sold by quote."""
    model_config = ConfigDict(extra="forbid")
    uses: List[Literal["sync", "ai"]] = Field(..., min_length=1, max_length=2)
    buyer_name: str = Field(..., min_length=1, max_length=120)
    buyer_company: str = Field(default="", max_length=120)
    buyer_email: EmailStr
    price_cents_sync: Optional[int] = Field(default=None, ge=1)
    price_cents_ai: Optional[int] = Field(default=None, ge=1)
    term: str = Field(default=exclusive.DEFAULT_TERM, max_length=120)
    territory: str = Field(default=exclusive.DEFAULT_TERRITORY, max_length=120)
    quote_id: Optional[str] = Field(default=None, max_length=64)

    @field_validator("buyer_name", "buyer_company", "term", "territory")
    @classmethod
    def _clean_inline(cls, v: str) -> str:
        return quotes.clean(v, 120)


def _money(cents: Optional[int]) -> str:
    return f"${cents / 100:,.2f}" if cents else ""


async def _email_exclusive_license(doc: dict, lic: dict) -> None:
    """Agreement 3.4(e): tell the artist and every co-owner, with fields of use, term,
    territory and price. No percentage (decision 6). An email failure never undoes the sale."""
    from xml.sax.saxutils import escape
    track = doc.get("track_name") or "Your song"
    uses = exclusive.uses_label(lic["uses"])
    lines = [f"{track} was licensed exclusively for {uses}.",
             f"Term: {lic['term']}", f"Territory: {lic['territory']}"]
    if lic.get("price_cents_sync"):
        lines.append(f"Price for sync: {_money(lic['price_cents_sync'])}")
    if lic.get("price_cents_ai"):
        lines.append(f"Price for AI training: {_money(lic['price_cents_ai'])}")
    lines.append(f"Total price: {_money(lic['total_cents'])}")
    lines.append("While this license lasts, the song is not licensed to anyone else for these uses. "
                 "Your share is paid to your OVOXI Wallet as set out in your agreement.")
    text = "\n".join(lines)
    html = "".join(f"<p style='margin:4px 0'>{escape(x)}</p>" for x in lines)
    recipients = [await _uploader_email(doc), *(_cosign_interests_by_email(doc).keys())]
    for to in dict.fromkeys(filter(None, recipients)):
        try:
            await send_email(to=to, subject=f"{track} was licensed exclusively for {uses}",
                             html=html, text=text, reply_to=REPLY_TO_COSIGN,
                             idempotency_key=f"exclusive-{lic['id']}-{to}")
        except Exception as exc:
            logger.error("exclusive license email failed for %s: %s", lic["id"], exc)


@api_router.post("/admin/sync/tracks/{track_id}/exclusive-licenses")
@limiter.limit("30/minute")
async def admin_record_exclusive_license(request: Request, track_id: str, payload: AdminExclusiveLicense,
                                         admin: dict = Depends(require_admin)):
    """Brief 25b D5: record an exclusive license. The song comes down at once for the
    licensed use(s), the sale is logged, and the artist and co-owners are emailed."""
    doc = await db.track_submissions.find_one({"id": track_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Track not found")
    try:
        lic = exclusive.build_exclusive_license(
            track=doc, uses=payload.uses, buyer_name=payload.buyer_name,
            buyer_company=payload.buyer_company, buyer_email=payload.buyer_email,
            price_cents_sync=payload.price_cents_sync, price_cents_ai=payload.price_cents_ai,
            granted_by=admin.get("sub"), now=datetime.now(timezone.utc),
            term=payload.term, territory=payload.territory, quote_id=payload.quote_id)
        await exclusive.record_exclusive_license(db, lic)
    except exclusive.ExclusiveError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    await _log_admin_action(admin, "exclusive_license", track_id,
                            f"{exclusive.uses_label(lic['uses'])}, {_money(lic['total_cents'])}, {lic['id']}")
    await _email_exclusive_license(doc, lic)
    return {k: v for k, v in lic.items() if k != "_id"}


class ExclusivePaymentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount_cents: int = Field(..., gt=0, le=100_000_000)
    fee_cents: int = Field(0, ge=0)
    tax_cents: int = Field(0, ge=0)
    received_at: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    reference: str = Field(..., min_length=1, max_length=120)   # invoice or wire reference

    @model_validator(mode="after")
    def _net(self):
        if self.fee_cents + self.tax_cents >= self.amount_cents:
            raise ValueError("Fees and tax must be less than the amount received.")
        return self


@api_router.post("/admin/sync/exclusive-licenses/{license_id}/payments")
@limiter.limit("20/minute")
async def admin_record_exclusive_payment(request: Request, license_id: str, payload: ExclusivePaymentIn,
                                         clerk_payload: dict = Depends(require_admin)):
    """Brief 27: money received for an Exclusive License (paid outside checkout) credits
    the Wallets at 40% of Net Revenue. The reference makes a repeat entry harmless."""
    lic = await db.exclusive_licenses.find_one({"id": license_id}, {"_id": 0})
    if not lic:
        raise HTTPException(status_code=404, detail="Exclusive license not found.")
    track = await db.track_submissions.find_one({"id": lic["track_id"]}, {"_id": 0})
    if not track:
        raise HTTPException(status_code=404, detail="Track not found.")
    now = datetime.now(timezone.utc)
    pid = f"{license_id}:{payload.reference.strip()}"
    n = await wallet.credit_exclusive_payment(
        db, lic, track, payment_id=pid, amount_cents=payload.amount_cents, fee_cents=payload.fee_cents,
        tax_cents=payload.tax_cents, received_at=f"{payload.received_at}T00:00:00+00:00",
        test_mode=_wallet_test_mode(), now=now)
    await db.admin_actions.insert_one({"action": "exclusive_payment_recorded", "admin": clerk_payload["sub"],
                                       "license_id": license_id, "payment_id": pid, "amount_cents": payload.amount_cents,
                                       "fee_cents": payload.fee_cents, "tax_cents": payload.tax_cents,
                                       "lines": n, "at": now.isoformat()})
    return {"recorded": n > 0, "duplicate": n == 0,
            "revenue_share_cents": wallet.revenue_share(
                wallet.net_revenue(payload.amount_cents, fee_cents=payload.fee_cents, tax_cents=payload.tax_cents),
                wallet.RATE_EXCLUSIVE_BP)}


@api_router.get("/admin/sync/exclusive-licenses")
@limiter.limit("60/minute")
async def admin_list_exclusive_licenses(request: Request, admin: dict = Depends(require_admin)):
    rows = await db.exclusive_licenses.find({}, {"_id": 0}).sort("granted_at", -1).to_list(500)
    return rows


class AdminLoopReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    result: Literal["approved", "rejected"]
    reason: str = Field(default="", max_length=500)


@api_router.post("/admin/sync/tracks/{track_id}/loop-licenses-review")
@limiter.limit("30/minute")
async def admin_loop_licenses_review(request: Request, track_id: str, payload: AdminLoopReview,
                                     admin: dict = Depends(require_admin)):
    """Agreement 3.6(c): approve or reject all loop licenses on a track. Approving needs a
    license on file for every loop; any later change to the loops or files resets it."""
    doc = await db.track_submissions.find_one({"id": track_id}, {"_id": 0, "id": 1, "intake": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="Track not found")
    loops = (doc.get("intake") or {}).get("loops") or []
    if (doc.get("intake") or {}).get("samples") != "royalty_free_loop" or not loops:
        raise HTTPException(status_code=409, detail="This track has no loops to review.")
    if payload.result == "approved" and any(not lp.get("license_key") for lp in loops):
        raise HTTPException(status_code=409, detail="Every loop needs a license file before approval.")
    review = {"result": payload.result, "by": admin.get("sub"),
              "at": datetime.now(timezone.utc).isoformat(),
              "license_keys": [lp.get("license_key") for lp in loops]}
    await db.track_submissions.update_one({"id": track_id}, {"$set": {"loop_licenses_reviewed": review}})
    await _log_admin_action(admin, f"loop_licenses_{payload.result}", track_id, payload.reason)
    await _run_clearance(track_id)
    return await db.track_submissions.find_one(
        {"id": track_id}, {"_id": 0, "id": 1, "sync_status": 1, "ai_status": 1,
                           "on_sync_profile": 1, "loop_licenses_reviewed": 1})


@api_router.post("/admin/artists/{user_id}/approve")
@limiter.limit("30/minute")
async def admin_approve_artist(request: Request, user_id: str, admin: dict = Depends(require_admin)):
    """Oct 26: approve an artist in one step. Sets role=artist in Clerk, starts processing
    their held songs and emails them."""
    if not re.fullmatch(r"user_[A-Za-z0-9]+", user_id):
        raise HTTPException(status_code=422, detail="Invalid user id")
    await set_clerk_public_metadata(user_id, {"role": "artist"})
    released = await _release_held_uploads(user_id)
    await _log_admin_action(admin, "approve_artist", user_id, f"released {released}")
    try:
        u = await fetch_clerk_user(user_id)
        body = ("Your OVOXI artist account is approved. Your songs are being processed now, and "
                "you can check each one in your Vault. Songs that clear our checks are listed in "
                "the OVOXI Catalog.")
        await send_email(to=u["email"], subject="Your OVOXI artist account is approved",
                         html=f"<p>{body}</p><p><a href=\"https://ovoxi.net/vault\">Open your Vault</a></p>",
                         text=body + "\n\nhttps://ovoxi.net/vault", reply_to=REPLY_TO_COSIGN,
                         idempotency_key=f"approved-{user_id}")
    except Exception as exc:
        logger.error("approval email failed for %s: %s", user_id, exc)
    return {"user_id": user_id, "role": "artist", "released": released}


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

    now = datetime.now(timezone.utc)
    for s in subs:
        s["exclusive"] = exclusive.is_exclusive(s)
        s["exclusive_sold"] = exclusive.sold_uses(s)
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
        for field, suffixes in (("preview_key", (".full128.mp3", ".mp3")),
                                ("preview_short_key", (".short.mp3",)),
                                ("waveform_key", (".waveform.json",))):
            value = payload.get(field)
            if value is None:
                continue
            if value in {preview_base + s for s in suffixes}:
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


@api_router.get("/sync/pricing")
@limiter.limit("60/minute")
async def sync_pricing(request: Request, viewer: Optional[dict] = Depends(optional_clerk)):
    """Public pricing for the Pricing page (Brief 20 B1). Read-only: no Stripe call and no
    price-cache warming. Plan prices come from the PLANS constants and single-track prices
    from sync_orders; subscriptions_enabled mirrors the checkout rule but only reads the
    already-loaded price cache (startup and the admin checkout config warm it)."""
    _, is_admin = _viewer(viewer)
    plans = [{
        "id": pid, "label": p["label"],
        "month_cents": p["month_cents"], "year_cents": p["year_cents"],
        "month_cap": p["month_cap"], "day_cap": SUB_DAY_CAP,
        "month_cents_loyalty15": subscriptions.loyalty_price_cents(p["month_cents"], 15),
        "month_cents_loyalty20": subscriptions.loyalty_price_cents(p["month_cents"], 20),
    } for pid, p in PLANS.items()]
    singles = [{
        "id": tid, "label": label,
        "price_cents": sync_orders.price_cents(tid, "1y" if tid in sync_orders.TERM_OPTIONS else None),
        "by_quote": False,
    } for tid, (label, _, _) in sync_orders.TIERS.items()]
    singles.append({"id": "enterprise", "label": "Enterprise", "price_cents": None, "by_quote": True})
    return {
        "visible": _public_pages_enabled() or is_admin,
        "library_visible": _library_enabled() or is_admin,
        "subscriptions_enabled": sync_orders.subscriptions_enabled() and subscriptions.prices_ready(),
        "plans": plans,
        "singles": singles,
    }


@api_router.get("/sync/terms/{version}")
@limiter.limit("60/minute")
async def sync_terms(request: Request, version: str):
    """Public License Terms blocks for a version. "current" resolves to the active
    SYNC_TERMS_VERSION. Not behind the public-pages flag."""
    if version == "current":
        version = sync_orders.terms_version()
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
    if payload.kind == "exclusive":
        # Brief 25b D4: only for an exclusive song, and only for uses still available.
        if (not track or not is_listed(track) or not exclusive.is_exclusive(track)
                or not all(exclusive.use_available(track, u) and listed_for(track, u) for u in payload.uses)):
            raise HTTPException(status_code=409, detail="This exclusive license is not available for this song.")
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
    if not track or not listed_for(track, "sync"):
        raise _not_found()
    if exclusive.is_exclusive(track):
        raise HTTPException(status_code=409, detail=exclusive.EXCLUSIVE_ONLY_DETAIL)
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
        attachments=[(f"OVOXI-license-{order['license_id']}.pdf", pdf)],
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


async def _order_fee_cents(order: dict) -> int:
    """Stripe's processing fee for a single-track order, from its charge's balance
    transaction (the same read as subscriptions). Raises when Stripe has not posted it yet."""
    client = sync_orders.stripe_client()
    pi = await asyncio.to_thread(client.v1.payment_intents.retrieve, order["stripe_payment_intent"])
    pi = pi.to_dict() if hasattr(pi, "to_dict") else dict(pi)
    charge = pi.get("latest_charge")
    charge_id = charge.get("id") if isinstance(charge, dict) else charge
    return await subscriptions._charge_fee(client, charge_id)


async def _credit_order(order_id: str) -> None:
    """Brief 27: credit the OVOXI Wallets for a paid single-track order. Best effort here;
    Close month credits any paid order this missed (for example, a fee not posted yet)."""
    try:
        order = await db.orders.find_one({"order_id": order_id}, {"_id": 0})
        if not order or order.get("status") not in ("paid", "fulfilled") or not order.get("stripe_payment_intent"):
            return
        track = await db.track_submissions.find_one({"id": order["track_id"]}, {"_id": 0})
        if not track:
            logger.error("wallet credit: order %s has no track %s", order_id, order.get("track_id"))
            return
        fee = await _order_fee_cents(order)
        n = await wallet.credit_order(db, order, track, fee_cents=fee)
        logger.info("wallet credit order=%s lines=%s", order_id, n)
    except Exception as exc:
        logger.warning("wallet credit deferred order=%s error=%s", order_id, type(exc).__name__)


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


async def _wallet_catch_up(period: Optional[str] = None, *, min_age_min: int = 10, limit: int = 200) -> int:
    """Credit paid single-track orders the webhook missed, and apply any refund the
    ledger has not reversed yet. Safe to run any time: every ledger write is idempotent."""
    now = datetime.now(timezone.utc)
    q = {"status": {"$in": ["paid", "fulfilled", "refunded"]}, "stripe_payment_intent": {"$ne": None},
         "paid_at": {"$lt": (now - timedelta(minutes=min_age_min)).isoformat()}}
    if period:
        start, end = statements.month_bounds(period)
        q["paid_at"] = {"$gte": start.isoformat(), "$lt": end.isoformat()}
    done = 0
    for o in await db.orders.find(q, {"_id": 0}).sort("paid_at", 1).to_list(limit):
        if not await db.wallet_entries.find_one({"source_type": "order", "source_id": o["order_id"]}, {"_id": 1}):
            await _credit_order(o["order_id"])
            done += 1
        refunded = max([int(r.get("amount_refunded_cents") or 0) for r in (o.get("refunds") or [])] or [0])
        if refunded:
            done += await wallet.reverse_order(db, o, kind="refund", refunded_cents=refunded, now=now) > 0
        if o.get("dispute_lost"):
            done += await wallet.reverse_order(db, o, kind="dispute", refunded_cents=0, now=now) > 0
    return done


def _wallet_test_mode() -> bool:
    return not payouts.stripe_livemode()


async def _close_month(period: str, admin: str) -> dict:
    return await statements.close_month(
        db, period, test_mode=_wallet_test_mode(), now=datetime.now(timezone.utc), admin=admin,
        put_object=_r2_put, send_email=send_email, site=sync_orders.site_url(),
        catch_up=lambda p: _wallet_catch_up(p, min_age_min=0, limit=100000))


async def _wallet_sweep(now: datetime) -> None:
    """Every reconcile tick: catch up missed credits. On the 1st from 06:00 UTC, prepare
    the month that just ended (Close month). It never pays: payouts wait for Tyler."""
    await _wallet_catch_up()
    if now.day == 1 and now.hour >= 6:
        period = statements.previous_period(now)
        if not await db.wallet_closes.find_one({"period": period, "test_mode": _wallet_test_mode()}, {"_id": 1}):
            summary = await _close_month(period, admin="sweeper")
            logger.info("wallet close period=%s summary=%s", period, summary)


async def _run_fulfilment_reconciler() -> None:
    logger.info("Fulfilment reconciler started instance=%s", INSTANCE_ID)
    while True:
        await asyncio.sleep(FULFIL_RECONCILE_INTERVAL)
        try:
            await _reconcile_fulfilment(datetime.now(timezone.utc))
        except Exception as exc:
            logger.error("fulfilment reconciler error: %s", exc)
        try:
            await _wallet_sweep(datetime.now(timezone.utc))
        except Exception as exc:
            logger.error("wallet sweep error: %s", exc)


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
                background.add_task(_credit_order, order_id)
    elif event.type == "checkout.session.expired":
        await sync_orders.apply_session_expired(db, obj, now=now)
    elif event.type == "charge.refunded":
        order_id = await sync_orders.apply_refund(db, obj, now=now)          # single-track first
        if order_id:
            try:   # Wallet reversal; Close month re-checks refunded orders if this fails.
                order = await db.orders.find_one({"order_id": order_id}, {"_id": 0})
                await wallet.reverse_order(db, order, kind="refund",
                                           refunded_cents=int(obj.get("amount_refunded") or 0), now=now)
            except Exception as exc:
                logger.error("wallet refund reversal deferred order=%s error=%s", order_id, type(exc).__name__)
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
        closed = event.type.endswith("closed")
        order = await sync_orders.apply_dispute(db, obj, closed=closed, now=now)   # single-track first
        if order:
            # License Terms A13. The subscription void path never runs on a single-track charge.
            logger.info("charge.dispute %s single-track order %s outcome=%s",
                        obj.get("id"), order.get("order_id"), order["dispute_outcome"])
            if order["dispute_outcome"] == "lost":
                try:
                    await wallet.reverse_order(db, order, kind="dispute", refunded_cents=0, now=now)
                except Exception as exc:
                    logger.error("wallet dispute reversal failed order=%s error=%s",
                                 order.get("order_id"), type(exc).__name__)
        elif client:
            sub_invoice = await subscriptions.on_dispute(db, client, obj, now, closed=closed)
            if not sub_invoice:
                logger.error("charge.dispute %s matched neither a single-track order nor an invoice",
                             obj.get("id"))
        else:
            logger.error("dispute event %s matched no single-track order and no Stripe API key is configured",
                         event.type)

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
            "ends_at": subscriptions.ending_date(sub),
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
    if not sub or subscriptions._state(sub, now) != "ending":
        raise HTTPException(status_code=409, detail="There is nothing to resume.")
    client = sync_orders.stripe_client()
    try:
        await subscriptions.resume_subscription(db, client, sub, now)
    except Exception as exc:
        logger.error("resume failed uid=%s error=%s", uid, exc)
        raise HTTPException(status_code=502, detail="Could not resume. Please try again.")
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
    if not track or not listed_for(track, "sync"):
        raise _not_found()
    if exclusive.is_exclusive(track):
        raise HTTPException(status_code=409, detail=exclusive.EXCLUSIVE_ONLY_DETAIL)
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
                               attachments=[(f"OVOXI-license-{lic['license_id']}.pdf", pdf)],
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
        if lic.get("status") in ("refunded", "void", "suspended"):
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


# ---------------------------------------------------------------------------
# Privacy choices (Brief 26). Signed out: one row per decision, keyed by the visitor id.
# Signed in: the row carries the account, and a copy goes to Clerk public_metadata.privacy.
# ---------------------------------------------------------------------------

@api_router.post("/privacy/choices")
@limiter.limit("30/minute")
async def post_privacy_choice(request: Request, payload: privacy.PrivacyChoiceIn,
                              viewer: Optional[dict] = Depends(optional_clerk)):
    user_id = viewer["sub"] if viewer else None
    if user_id and payload.source == "signup":
        # Decision 2: an account that already has choices keeps them; the visit's choice
        # is only the starting point for a new account.
        existing = await privacy.latest_choice(db, user_id)
        if existing:
            return {"saved": False, "choice": privacy.public_choice(existing)}
    row = privacy.choice_row(payload, user_id=user_id, ip=get_real_client_ip(request),
                             user_agent=request.headers.get("user-agent", ""))
    try:
        await privacy.record_choice(db, row)
    except Exception as exc:
        logger.error("Privacy choice write failed: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Could not save your choice. Please try again.")
    clerk_synced = None
    if user_id:
        # The database row is the record. The Clerk copy is a convenience, so a Clerk
        # failure is logged and reported, never a failed save.
        try:
            await set_clerk_public_metadata(user_id, {"privacy": privacy.clerk_privacy(row)})
            clerk_synced = True
        except HTTPException:
            clerk_synced = False
    return {"saved": True, "choice": privacy.public_choice(row), "clerk_synced": clerk_synced}


@api_router.get("/privacy/me")
@limiter.limit("30/minute")
async def get_my_privacy_choice(request: Request, clerk_payload: dict = Depends(verify_clerk_token)):
    return {"choice": privacy.public_choice(await privacy.latest_choice(db, clerk_payload["sub"]))}


# ---------------------------------------------------------------------------
# OVOXI Wallet: admin close, payouts and holds (Brief 27 Part C)
# ---------------------------------------------------------------------------

class PeriodIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    period: str = Field(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$")


class HoldIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    track_id: str = Field(..., min_length=1, max_length=64)
    reason: str = Field(..., min_length=3, max_length=300)


@api_router.get("/admin/wallet/overview")
@limiter.limit("30/minute")
async def admin_wallet_overview(request: Request, period: Optional[str] = None,
                                clerk_payload: dict = Depends(require_admin)):
    now = datetime.now(timezone.utc)
    period = period or statements.previous_period(now)
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", period):
        raise HTTPException(status_code=422, detail="Invalid period.")
    livemode = payouts.stripe_livemode()
    close = await db.wallet_closes.find_one({"period": period, "test_mode": not livemode}, {"_id": 0})
    plan = await payouts.preview(db, period, livemode=livemode)
    runs = await db.payouts.find({"period": period, "livemode": livemode}, {"_id": 0}).sort("created_at", -1).to_list(500)
    holds = await db.wallet_holds.find({"released_at": None}, {"_id": 0}).to_list(500)
    return {"period": period, "period_label": statements.period_label(period), "livemode": livemode,
            "payment_due": statements.payment_due(period), "december": payouts.is_december(period),
            "closed": close, "preview": plan, "payouts": runs, "holds": holds,
            "minimum_cents": payouts.PAYOUT_MIN_CENTS}


@api_router.post("/admin/wallet/close")
@limiter.limit("5/minute")
async def admin_wallet_close(request: Request, payload: PeriodIn, clerk_payload: dict = Depends(require_admin)):
    """Close month: subscription pool, balances made available, statements. Pays nothing."""
    try:
        summary = await _close_month(payload.period, admin=clerk_payload["sub"])
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    await db.admin_actions.insert_one({"action": "wallet_close", "admin": clerk_payload["sub"],
                                       "period": payload.period, "summary": summary,
                                       "at": datetime.now(timezone.utc).isoformat()})
    return summary


@api_router.post("/admin/wallet/payouts")
@limiter.limit("3/minute")
async def admin_wallet_pay(request: Request, payload: PeriodIn, clerk_payload: dict = Depends(require_admin)):
    """Approve and pay: one Stripe Transfer per eligible payee (8.1). Needs the month closed."""
    livemode = payouts.stripe_livemode()
    if not await db.wallet_closes.find_one({"period": payload.period, "test_mode": not livemode}, {"_id": 1}):
        raise HTTPException(status_code=409, detail="Close the month first.")
    try:
        client = sync_orders.stripe_client()
    except sync_orders.ConfigError:
        raise HTTPException(status_code=503, detail="Stripe is not configured.")
    now = datetime.now(timezone.utc)
    result = await payouts.run(db, client, payload.period, livemode=livemode, admin=clerk_payload["sub"], now=now)
    await db.admin_actions.insert_one({"action": "wallet_payout_run", "admin": clerk_payload["sub"],
                                       "period": payload.period, "livemode": livemode,
                                       "paid": len(result["paid"]), "failed": len(result["failed"]),
                                       "paid_total_cents": result["paid_total_cents"], "at": now.isoformat()})
    return result


@api_router.post("/admin/wallet/holds")
@limiter.limit("20/minute")
async def admin_wallet_hold(request: Request, payload: HoldIn, clerk_payload: dict = Depends(require_admin)):
    """8.5: hold a track's Revenue Share while a claim is open."""
    if not await db.track_submissions.find_one({"id": payload.track_id}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Track not found.")
    now = datetime.now(timezone.utc)
    await wallet.hold_track(db, payload.track_id, reason=payload.reason, admin=clerk_payload["sub"], now=now)
    await db.admin_actions.insert_one({"action": "wallet_hold", "admin": clerk_payload["sub"],
                                       "track_id": payload.track_id, "reason": payload.reason, "at": now.isoformat()})
    return {"held": True}


@api_router.delete("/admin/wallet/holds/{track_id}")
@limiter.limit("20/minute")
async def admin_wallet_release(request: Request, track_id: str, clerk_payload: dict = Depends(require_admin)):
    now = datetime.now(timezone.utc)
    await wallet.release_track(db, track_id, admin=clerk_payload["sub"], now=now)
    await db.admin_actions.insert_one({"action": "wallet_release", "admin": clerk_payload["sub"],
                                       "track_id": track_id, "at": now.isoformat()})
    return {"held": False}


# ---------------------------------------------------------------------------
# OVOXI Wallet: Stripe Connect Express onboarding (Brief 27 Part B)
# ---------------------------------------------------------------------------

class ConnectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    country: str = Field(..., min_length=2, max_length=2)


async def _suggested_country(uid: str) -> Optional[str]:
    agreement = await _current_agreement(uid)
    return payouts.guess_country(((agreement or {}).get("fields") or {}).get("country"))


def _connect_view(acct: Optional[dict]) -> dict:
    if not acct:
        return {"connected": False}
    if acct.get("unsupported_country"):
        return {"connected": False, "country": acct.get("country"), "unsupported": True,
                "message": payouts.UNSUPPORTED_MESSAGE}
    return {"connected": bool(acct.get("stripe_account_id")), "country": acct.get("country"),
            "details_submitted": bool(acct.get("details_submitted")),
            "payouts_enabled": payouts.payout_ready(acct),
            "currently_due": acct.get("currently_due") or [],
            "disabled_reason": acct.get("disabled_reason")}


@api_router.get("/wallet/me")
@limiter.limit("30/minute")
async def wallet_me(request: Request, clerk_payload: dict = Depends(verify_clerk_token)):
    """The signed-in payee's OVOXI Wallet: totals, lines, statements and payout setup."""
    uid = clerk_payload["sub"]
    try:
        user = await fetch_clerk_user(uid)
        if user.get("email_verified") and user.get("email"):
            moved = await wallet.claim_email_entries(db, user_id=uid, email=user["email"])
            if moved:
                logger.info("wallet claimed %s co-owner lines for user=%s", moved, uid)
    except HTTPException:
        pass   # Clerk unreachable: show what is already under the account
    test_mode = _wallet_test_mode()
    rows = await db.wallet_entries.find({"payee_key": uid, "test_mode": test_mode},
                                        {"_id": 0}).sort("created_at", -1).to_list(2000)
    titles = {t["id"]: t.get("track_name") or "" for t in await db.track_submissions.find(
        {"id": {"$in": list({r["track_id"] for r in rows})}}, {"_id": 0, "id": 1, "track_name": 1}).to_list(5000)}
    sts = await db.statements.find({"payee_key": uid, "test_mode": test_mode},
                                   {"_id": 0, "period": 1, "revenue_share_cents": 1, "payment_due": 1}).sort("period", -1).to_list(240)
    acct = await payouts.get_account(db, uid)
    now = datetime.now(timezone.utc)
    return {"summary": wallet.summarize(rows, this_period=now.strftime("%Y-%m")),
            "entries": [wallet.entry_view(r, titles) for r in rows[:500]],
            "statements": [{**s, "period_label": statements.period_label(s["period"])} for s in sts],
            "connect": _connect_view(acct), "test_mode": test_mode,
            "minimum_cents": payouts.PAYOUT_MIN_CENTS}


@api_router.get("/wallet/statements/{period}")
@limiter.limit("30/minute")
async def wallet_statement_pdf(request: Request, period: str, clerk_payload: dict = Depends(verify_clerk_token)):
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", period):
        raise HTTPException(status_code=404, detail="Statement not found.")
    st = await db.statements.find_one({"payee_key": clerk_payload["sub"], "period": period,
                                       "test_mode": _wallet_test_mode()}, {"_id": 0, "pdf_key": 1})
    if not st or not st.get("pdf_key"):
        raise HTTPException(status_code=404, detail="Statement not found.")
    url = r2_client.generate_presigned_url("get_object", Params={"Bucket": R2_BUCKET, "Key": st["pdf_key"]},
                                           ExpiresIn=300)
    return {"url": url}


@api_router.get("/wallet/connect/status")
@limiter.limit("30/minute")
async def wallet_connect_status(request: Request, clerk_payload: dict = Depends(verify_clerk_token)):
    uid = clerk_payload["sub"]
    acct = await payouts.get_account(db, uid)
    if acct and acct.get("stripe_account_id"):
        try:
            acct = await payouts.refresh_status(db, sync_orders.stripe_client(), acct, datetime.now(timezone.utc))
        except Exception as exc:   # show the last saved status
            logger.warning("connect status refresh failed user=%s error=%s", uid, type(exc).__name__)
    return {**_connect_view(acct), "suggested_country": await _suggested_country(uid),
            "countries": [{"code": c, "name": n} for c, n in sorted(payouts.CONNECT_COUNTRIES.items(), key=lambda x: x[1])]}


@api_router.post("/wallet/connect")
@limiter.limit("5/minute")
async def wallet_connect(request: Request, payload: ConnectRequest, clerk_payload: dict = Depends(verify_clerk_token)):
    """Start (or resume) Stripe Express onboarding. Returns the Stripe link to open."""
    uid = clerk_payload["sub"]
    country = payload.country.upper()
    now = datetime.now(timezone.utc)
    if country not in payouts.CONNECT_COUNTRIES:
        await db.wallet_accounts.update_one(
            {"user_id": uid, "livemode": payouts.stripe_livemode()},
            {"$set": {"country": country, "unsupported_country": True, "updated_at": now.isoformat()},
             "$setOnInsert": {"created_at": now.isoformat(), "stripe_account_id": None}}, upsert=True)
        return {"url": None, "unsupported": True, "message": payouts.UNSUPPORTED_MESSAGE}
    try:
        client = sync_orders.stripe_client()
    except sync_orders.ConfigError:
        raise HTTPException(status_code=503, detail="Payouts are not set up yet.")
    existing = await payouts.get_account(db, uid)
    if existing and existing.get("stripe_account_id") and existing.get("country") != country:
        raise HTTPException(status_code=409, detail="Your payout country is already set. Email tyler@ovoxi.net to change it.")
    user = await fetch_clerk_user(uid)
    try:
        acct = await payouts.create_or_get(db, client, user_id=uid, email=user.get("email"),
                                           country=country, now=now)
        url = await payouts.onboarding_link(client, acct["stripe_account_id"], site=sync_orders.site_url())
    except Exception as exc:
        logger.error("connect onboarding failed user=%s error=%s", uid, exc)
        raise HTTPException(status_code=502, detail="Could not reach our payment provider. Please try again.")
    await db.admin_actions.insert_one({"action": "wallet_connect_started", "user_id": uid,
                                       "stripe_account_id": acct["stripe_account_id"], "at": now.isoformat()})
    return {"url": url}


@api_router.post("/wallet/dashboard-link")
@limiter.limit("10/minute")
async def wallet_dashboard_link(request: Request, clerk_payload: dict = Depends(verify_clerk_token)):
    """A one-time link to the payee's Stripe Express dashboard (payouts and tax forms)."""
    acct = await payouts.get_account(db, clerk_payload["sub"])
    if not acct or not acct.get("stripe_account_id") or not acct.get("details_submitted"):
        raise HTTPException(status_code=409, detail="Connect your bank account first.")
    try:
        return {"url": await payouts.dashboard_link(sync_orders.stripe_client(), acct["stripe_account_id"])}
    except Exception as exc:
        logger.error("connect dashboard link failed error=%s", exc)
        raise HTTPException(status_code=502, detail="Could not reach our payment provider. Please try again.")


@api_router.post("/stripe/connect-webhook")
async def stripe_connect_webhook(request: Request):
    """Payee account updates, with their own signing secret. Accounts v2 sends thin event
    notifications (scope "Your account"): verify, then fetch the account and save its
    payout status. Any v2.core.account event is treated as "something changed"."""
    import stripe
    secret = os.environ.get("STRIPE_CONNECT_WEBHOOK_SECRET", "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="Not configured")
    try:
        client = sync_orders.stripe_client()
    except sync_orders.ConfigError:
        raise HTTPException(status_code=503, detail="Not configured")
    raw = await request.body()
    try:
        note = client.parse_event_notification(raw, request.headers.get("stripe-signature"), secret)
    except (ValueError, KeyError, stripe.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Invalid signature")
    etype = getattr(note, "type", "") or ""
    related = getattr(note, "related_object", None)
    account_id = getattr(related, "id", None)
    if etype.startswith("v2.core.account") and account_id and account_id.startswith("acct_"):
        if await db.wallet_accounts.find_one({"stripe_account_id": account_id}, {"_id": 1}):
            account = await payouts.fetch_account(client, account_id)   # errors: 500, Stripe retries
            await payouts.save_status(db, account_id, account, datetime.now(timezone.utc))
    return {"ok": True}


@api_router.post("/account/buyer-access")
@limiter.limit("5/minute")
async def account_buyer_access(request: Request, clerk_payload: dict = Depends(verify_clerk_token)):
    """Grant the signed-in user buyer access by setting public_metadata.buyer = true
    (decision 5). Merges, so an artist's role is preserved; safe to call more than once."""
    await set_clerk_public_metadata(clerk_payload["sub"], {"buyer": True})
    return {"buyer": True}


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
                "ResponseContentDisposition": f'attachment; filename="OVOXI-license-{license_id}.pdf"'},
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
    if lic.get("status") == "suspended":
        raise HTTPException(status_code=409, detail="Downloads are paused while a payment dispute is open.")
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
        await db.privacy_choices.create_index([("user_id", 1), ("created_at", -1)])
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
        await db.cosign_requests.create_index([("token_sha256", 1)], unique=True)
        await db.cosign_requests.create_index([("track_id", 1), ("email", 1)], unique=True)
        await sync_orders.ensure_indexes(db)
        await licenses.ensure_indexes(db)
        await subscriptions.ensure_indexes(db)
        await wallet.ensure_indexes(db)
        await payouts.ensure_indexes(db)
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
