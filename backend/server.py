import asyncio
import json
import os
import logging
import re
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import List, Optional

import boto3
import httpx
from botocore.config import Config
from dotenv import load_dotenv
from jose import jwt, JWTError
from fastapi import BackgroundTasks, Depends, FastAPI, APIRouter, UploadFile, File, Form, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, ConfigDict, EmailStr, field_validator
from starlette.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware


def get_real_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

UPLOADS_DIR = ROOT_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

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

# Lalal.ai
LALAL_API_KEY = os.environ.get("LALAL_API_KEY", "")
LALAL_BASE = "https://www.lalal.ai/api"

AUDIO_CONTENT_TYPES = {".mp3": "audio/mpeg", ".wav": "audio/wav"}

app = FastAPI()
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

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

CLERK_JWKS_URL = os.environ.get('CLERK_JWKS_URL', '')
CLERK_SECRET_KEY = os.environ.get('CLERK_SECRET_KEY', '')


async def verify_clerk_token(authorization: str = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=401, detail='Missing or invalid Authorization header')
    token = authorization.split(' ', 1)[1]
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                CLERK_JWKS_URL,
                headers={'Authorization': f'Bearer {CLERK_SECRET_KEY}'}
            )
            jwks = resp.json()
        payload = jwt.decode(token, jwks, algorithms=['RS256'])
        return payload
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=f'Invalid token: {exc}')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(text: str) -> str:
    text = re.sub(r'[^\w\s-]', '', text.lower().strip())
    return re.sub(r'[\s_-]+', '_', text)[:80].strip('_')


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


async def _master_track(submission_id: str, r2_key: str) -> str:
    """
    Downloads raw track from R2, masters it with Matchering,
    uploads mastered WAV to R2, returns the mastered R2 key.
    """
    import tempfile, os
    import matchering as mg

    mastered_r2_key = r2_key.replace("/original/", "/mastered/")

    # Reference track bundled in the repo
    reference_path = os.path.join(os.path.dirname(__file__), "reference", "default.wav")

    with tempfile.TemporaryDirectory() as tmpdir:
        raw_path = os.path.join(tmpdir, "input.wav")
        mastered_path = os.path.join(tmpdir, "mastered.wav")

        # 1. Download raw file from R2
        audio_data = await _r2_get(r2_key)
        with open(raw_path, "wb") as f:
            f.write(audio_data)

        # 2. Run Matchering in a thread (CPU-bound)
        def _run_matchering():
            mg.process(
                target=raw_path,
                reference=reference_path,
                results=[mg.pcm24(mastered_path)],
            )

        await asyncio.to_thread(_run_matchering)

        # 3. Read mastered file and upload to R2
        with open(mastered_path, "rb") as f:
            mastered_data = f.read()

        await _r2_put(mastered_r2_key, mastered_data, "audio/wav")

    return mastered_r2_key


async def _process_stems(submission_id: str, r2_key: str, artist_name: str, track_name: str) -> None:
    try:
        await db.track_submissions.update_one(
            {"id": submission_id},
            {"$set": {"status": "processing"}},
        )

        # Master the track first
        await db.track_submissions.update_one(
            {"id": submission_id},
            {"$set": {"status": "mastering"}},
        )
        mastered_r2_key = await _master_track(submission_id, r2_key)
        await db.track_submissions.update_one(
            {"id": submission_id},
            {"$set": {"status": "processing", "mastered_r2_key": mastered_r2_key}},
        )

        audio_data = await _r2_get(mastered_r2_key)
        filename = Path(r2_key).name
        lalal_file_id = await _lalal_upload(audio_data, filename)
        logger.info("Lalal.ai upload complete, file_id=%s submission=%s", lalal_file_id, submission_id)

        safe_artist = _slugify(artist_name)
        safe_track = _slugify(track_name)
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

        await db.track_submissions.update_one(
            {"id": submission_id},
            {"$set": {"status": "completed", "stem_paths": stem_paths}},
        )
        logger.info("Stem processing completed for submission=%s", submission_id)

    except Exception as exc:
        logger.error("Stem processing failed for submission=%s: %s", submission_id, exc)
        await db.track_submissions.update_one(
            {"id": submission_id},
            {"$set": {"status": "failed", "error": str(exc)}},
        )


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StatusCheckCreate(BaseModel):
    client_name: str


class LeadCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr
    company: Optional[str] = Field(default=None, max_length=160)
    interest: str = Field(..., max_length=60)
    message: str = Field(..., min_length=1, max_length=4000)


class Lead(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    email: str
    company: Optional[str] = None
    interest: str
    message: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ContactSubmissionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr
    company: Optional[str] = Field(default=None, max_length=160)
    interest: Optional[str] = Field(default=None, max_length=60)
    message: str = Field(..., min_length=1, max_length=4000)


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
    pro_registered: bool = False
    pro_org: str = ''
    pro_register_us: bool = False


class CompleteUploadRequest(BaseModel):
    submission_id: str


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


# ---------------------------------------------------------------------------
# Existing routes
# ---------------------------------------------------------------------------

@api_router.get("/")
async def root():
    return {"message": "Hello World"}


@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    doc = status_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    await db.status_checks.insert_one(doc)
    return status_obj


@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    for check in status_checks:
        if isinstance(check['timestamp'], str):
            check['timestamp'] = datetime.fromisoformat(check['timestamp'])
    return status_checks


@api_router.post("/leads", response_model=Lead, status_code=201)
async def create_lead(payload: LeadCreate):
    lead = Lead(**payload.model_dump())
    doc = lead.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.leads.insert_one(doc)
    logger.info("New lead captured: %s (%s)", lead.email, lead.interest)
    return lead


@api_router.get("/leads", response_model=List[Lead])
async def get_leads():
    leads = await db.leads.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    for lead in leads:
        if isinstance(lead.get('created_at'), str):
            lead['created_at'] = datetime.fromisoformat(lead['created_at'])
    return leads


# ---------------------------------------------------------------------------
# Contact / partnership form routes
# ---------------------------------------------------------------------------

@api_router.post("/contact", response_model=ContactSubmission, status_code=201)
async def create_contact_submission(payload: ContactSubmissionCreate):
    submission = ContactSubmission(**payload.model_dump())
    doc = submission.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.contact_submissions.insert_one(doc)
    logger.info("New contact submission: %s (%s)", submission.email, submission.name)
    return submission


@api_router.get("/contact", response_model=List[ContactSubmission])
async def get_contact_submissions(x_admin_password: Optional[str] = Header(default=None)):
    admin_password = os.environ.get('ADMIN_PASSWORD', '')
    if not admin_password or x_admin_password != admin_password:
        raise HTTPException(status_code=401, detail="Unauthorized")
    submissions = await db.contact_submissions.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    for s in submissions:
        if isinstance(s.get('created_at'), str):
            s['created_at'] = datetime.fromisoformat(s['created_at'])
    return submissions


# ---------------------------------------------------------------------------
# Artist application routes
# ---------------------------------------------------------------------------

@api_router.post("/artists", response_model=Artist, status_code=201)
async def create_artist(payload: ArtistCreate):
    existing = await db.artists.find_one({"email": payload.email}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=409, detail="An application with this email already exists")
    artist = Artist(**payload.model_dump())
    doc = artist.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.artists.insert_one(doc)
    logger.info("New artist application: %s (%s)", artist.email, artist.genre)
    return artist


@api_router.post("/artists/{email}/tracks", status_code=201)
async def upload_artist_tracks(
    email: str,
    titles: List[str] = Form(...),
    files: List[UploadFile] = File(...),
    pro_registered: bool = Form(False),
    pro_org: str = Form(''),
    pro_register_us: bool = Form(False),
):
    artist = await db.artists.find_one({"email": email}, {"_id": 0})
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    if isinstance(titles, str):
        titles = [titles]
    if not isinstance(files, list):
        files = [files]

    if len(titles) != len(files):
        raise HTTPException(status_code=400, detail="Number of titles must match number of files")

    allowed_ext = {'.mp3', '.wav'}
    max_size = 20 * 1024 * 1024

    saved_tracks = []
    for title, upload in zip(titles, files):
        ext = Path(upload.filename or '').suffix.lower()
        if ext not in allowed_ext:
            raise HTTPException(status_code=400, detail=f"'{upload.filename}' must be an MP3 or WAV file")
        content = await upload.read()
        if len(content) > max_size:
            raise HTTPException(status_code=400, detail=f"'{upload.filename}' exceeds the 20 MB limit")
        safe_email = email.replace('@', '_').replace('.', '_')
        safe_filename = f"{safe_email}_{uuid.uuid4().hex}{ext}"
        with open(UPLOADS_DIR / safe_filename, 'wb') as f:
            f.write(content)
        saved_tracks.append({
            "id": str(uuid.uuid4()),
            "title": title,
            "filename": safe_filename,
            "pro_registered": pro_registered,
            "pro_org": pro_org,
            "pro_register_us": pro_register_us,
        })

    await db.artists.update_one(
        {"email": email},
        {"$push": {"tracks": {"$each": saved_tracks}}},
    )
    logger.info("Uploaded %d track(s) for %s", len(saved_tracks), email)
    return {"uploaded": len(saved_tracks)}


@api_router.get("/artists")
async def get_artists(
    request: Request,
    x_admin_password: Optional[str] = Header(default=None),
):
    admin_password = os.environ.get('ADMIN_PASSWORD', '')
    if not admin_password or x_admin_password != admin_password:
        raise HTTPException(status_code=401, detail="Unauthorized")
    artists = await db.artists.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    base_url = str(request.base_url).rstrip('/')
    for artist in artists:
        if isinstance(artist.get('created_at'), str):
            artist['created_at'] = datetime.fromisoformat(artist['created_at'])
        for track in artist.get('tracks', []):
            track['url'] = f"{base_url}/uploads/{track['filename']}"
    return artists


# ---------------------------------------------------------------------------
# Upload pipeline routes
# ---------------------------------------------------------------------------

@api_router.post("/upload/presign")
@limiter.limit("5/minute")
async def presign_upload(request: Request, payload: PresignRequest, clerk_payload: dict = Depends(verify_clerk_token)):
    if payload.genre not in VALID_GENRES:
        raise HTTPException(status_code=400, detail=f"Invalid genre")

    ext = Path(payload.filename).suffix.lower()
    if ext not in AUDIO_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Only MP3 or WAV files are accepted")

    submission_id = str(uuid.uuid4())
    safe_artist = _slugify(payload.artist_name)
    safe_track = _slugify(payload.track_name)
    content_type = AUDIO_CONTENT_TYPES[ext]
    r2_key = f"catalog/{safe_artist}/{safe_track}/original/{submission_id}{ext}"

    def _presign():
        return r2_client.generate_presigned_url(
            "put_object",
            Params={"Bucket": R2_BUCKET, "Key": r2_key, "ContentType": content_type},
            ExpiresIn=3600,
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
    await db.track_submissions.insert_one(doc)

    return {
        "presigned_url": presigned_url,
        "submission_id": submission_id,
        "r2_key": r2_key,
        "content_type": content_type,
    }


@api_router.post("/upload/complete")
@limiter.limit("5/minute")
async def complete_upload(request: Request, payload: CompleteUploadRequest, background_tasks: BackgroundTasks):
    sub = await db.track_submissions.find_one({"id": payload.submission_id}, {"_id": 0})
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if sub["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Submission status is already '{sub['status']}'")

    await db.track_submissions.update_one(
        {"id": payload.submission_id},
        {"$set": {"status": "uploaded"}},
    )

    background_tasks.add_task(
        _process_stems,
        payload.submission_id,
        sub["original_r2_path"],
        sub["artist_name"],
        sub["track_name"],
    )
    logger.info("Queued stem processing for submission=%s", payload.submission_id)
    return {"status": "processing", "submission_id": payload.submission_id}


@api_router.get('/vault/tracks')
async def get_vault_tracks(clerk_payload: dict = Depends(verify_clerk_token)):
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
async def get_submissions(x_admin_password: Optional[str] = Header(default=None)):
    admin_password = os.environ.get('ADMIN_PASSWORD', '')
    if not admin_password or x_admin_password != admin_password:
        raise HTTPException(status_code=401, detail="Unauthorized")
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


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
