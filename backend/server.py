from fastapi import FastAPI, APIRouter, UploadFile, File, Form, HTTPException, Header, Request
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr, field_validator
from typing import List, Optional
import uuid
from datetime import datetime, timezone


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

UPLOADS_DIR = ROOT_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Serve uploaded audio files statically
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


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
    interest: str = Field(..., max_length=60)  # ai_company | enterprise | artist | investor | other
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

    _ = await db.status_checks.insert_one(doc)
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
):
    artist = await db.artists.find_one({"email": email}, {"_id": 0})
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    # Normalize single-value submissions
    if isinstance(titles, str):
        titles = [titles]
    if not isinstance(files, list):
        files = [files]

    if len(titles) != len(files):
        raise HTTPException(status_code=400, detail="Number of titles must match number of files")

    allowed_ext = {'.mp3', '.wav'}
    max_size = 20 * 1024 * 1024  # 20 MB

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
# App wiring
# ---------------------------------------------------------------------------

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
