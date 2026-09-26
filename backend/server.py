import asyncio
import hashlib
import hmac
import json
import os
import logging
import re
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone, timedelta
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import List, Optional

import boto3
import httpx
import modal
from botocore.config import Config
from botocore.exceptions import ClientError
from dotenv import load_dotenv
import jwt
from jwt import PyJWKClient
from fastapi import Depends, FastAPI, APIRouter, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument
from pydantic import BaseModel, Field, ConfigDict, EmailStr, field_validator
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

PROOF_CONTENT_TYPES = {
    ".pdf":  "application/pdf",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
    ".doc":  "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

app = FastAPI()

limiter = Limiter(key_func=get_real_client_ip)
app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    lambda request, exc: JSONResponse(
        status_code=429,
        content={"error": "Too many requests. Please try again in a minute."},
    ),
)
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


async def _set_status(submission_id: str, status: str, extra: Optional[dict] = None) -> None:
    fields: dict = {"status": status, "status_updated_at": datetime.now(timezone.utc).isoformat()}
    if extra:
        fields.update(extra)
    await db.track_submissions.update_one(
        {"id": submission_id},
        {"$set": fields},
    )


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

            def _ffprobe():
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

            await asyncio.to_thread(_ffprobe)
            acr_result = await asyncio.to_thread(acrcloud_check.scan_file, scan_path)

        acr_status = acr_result["status"]
        logger.info("ACRCloud result submission=%s status=%s", submission_id, acr_status)

        if acr_status != "CLEARED":
            extra = {f: acr_result[f] for f in ("matched_title", "matched_artist",
                     "matched_label", "matched_isrc", "confidence", "acrid", "raw_code")
                     if acr_result.get(f) is not None}
            await _set_status(submission_id, acr_status, extra)
            return

        await _set_status(submission_id, "mastering")
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


class PresignRequest(BaseModel):
    artist_name: str = Field(..., min_length=1, max_length=120)
    track_name: str = Field(..., min_length=1, max_length=120)
    genre: str
    filename: str = Field(..., min_length=1, max_length=200)
    file_size: int = Field(..., gt=0)
    pro_registered: bool = False
    pro_org: str = ''
    pro_register_us: bool = False


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
# Upload pipeline routes
# ---------------------------------------------------------------------------

@api_router.post("/upload/presign")
@limiter.limit("5/minute")
async def presign_upload(request: Request, payload: PresignRequest, clerk_payload: dict = Depends(require_artist)):
    if os.environ.get("UPLOADS_ENABLED", "true") != "true":
        raise HTTPException(status_code=503, detail="Uploads are temporarily paused")
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
        {'_id': 0}
    ).sort('upload_date', -1).to_list(1000)

    def _presign_get(key: str) -> str:
        return r2_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': R2_BUCKET, 'Key': key},
            ExpiresIn=3600,
        )

    for s in subs:
        if isinstance(s.get('upload_date'), str):
            s['upload_date'] = datetime.fromisoformat(s['upload_date'])
        if s.get('stem_paths'):
            try:
                s['stem_urls'] = {
                    stem: await asyncio.to_thread(_presign_get, key)
                    for stem, key in s['stem_paths'].items()
                }
            except Exception:
                s['stem_urls'] = {}
        if s.get('mastered_r2_key'):
            try:
                s['mastered_url'] = await asyncio.to_thread(_presign_get, s['mastered_r2_key'])
            except Exception:
                s['mastered_url'] = None
    return subs


@api_router.get("/submissions")
@limiter.limit("30/minute")
async def get_submissions(request: Request, admin: dict = Depends(require_admin)):
    logger.info("admin_access user=%s path=%s", admin.get("sub"), request.url.path)
    subs = await db.track_submissions.find({}, {"_id": 0}).sort("upload_date", -1).to_list(1000)

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
    if not sid:
        raise HTTPException(status_code=400, detail="Missing submission_id")

    if status == "completed":
        update = {
            "status":              "completed",
            "stem_paths":          payload["stem_paths"],
            "stem_schema_version": payload.get("stem_schema_version", 2),
        }
        if "source_sample_rate" in payload:
            update["source_sample_rate"] = payload["source_sample_rate"]
        # Stem storage format, recorded explicitly so the catalog is
        # self-describing for licensees. "wav24" from schema v3 onward;
        # absent on v1 (LALAL pcm_s24le) and v2 (MP3 320) documents.
        if "stem_format" in payload:
            update["stem_format"] = payload["stem_format"]
        result = await db.track_submissions.update_one(
            {"id": sid, "status": {"$nin": ["failed", "completed"]}},
            {"$set": update},
        )
        if result.matched_count == 0:
            logger.warning(
                "Stem callback completed for %s but document already in terminal state — ignored",
                sid,
            )
        else:
            logger.info("Stem callback completed submission=%s", sid)
    elif status == "failed":
        await db.track_submissions.update_one(
            {"id": sid},
            {"$set": {
                "status": "failed",
                "error":  payload.get("error", "Unknown failure"),
            }},
        )
        logger.error("Stem callback failed submission=%s error=%s",
                     sid, payload.get("error"))
    else:
        raise HTTPException(status_code=400,
                            detail=f"Unknown status: {status!r}")
    return {"ok": True}


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
    except Exception as exc:
        logger.warning("Index creation failed (non-fatal): %s", exc)
    if RUN_WORKER:
        for _ in range(WORKER_CONCURRENCY):
            asyncio.ensure_future(_worker_loop())
        asyncio.ensure_future(_run_sweeper())
        logger.info("Started %d worker(s) and sweeper instance=%s", WORKER_CONCURRENCY, INSTANCE_ID)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
