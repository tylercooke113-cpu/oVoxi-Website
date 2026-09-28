"""
PRD-03 Phase 4b: public artist and track pages, the SYNC_PUBLIC_PAGES_ENABLED
gate, owner/admin visibility, listing rule, allowlists, waveform and preview.
"""
import copy
import json
from io import BytesIO
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import server
from sync_public import is_listed
from test_vault import FakeCollection, MATCH

OWNER, OTHER, ADMIN = "user_owner", "user_other", "user_admin"
TID = "track-live"
# "profiles/..." may appear, but only inside the signed photo link itself.
PRIVATE = ["owner@email.test", "Private Person", "00123456789", "BMI", "user_owner",
           "catalog/", "Famous Song", "acr123"]


def listed_track(**over):
    doc = {
        "id": TID, "clerk_user_id": OWNER, "artist_name": "Upload Name", "track_name": "Night Drive",
        "genre": "R&B", "upload_date": "2026-09-28T00:00:00+00:00", "status": "completed",
        "consent": {"ai_training": True, "sync": True},
        "metadata": {"moods": ["Chill"], "vocals": "vocal", "bpm": 90.0, "key": "C major",
                     "duration_s": 184.0, "bpm_detected": 90.0},
        "intake": {"content_id": "no", "ipi": "00123456789", "pro_name": "BMI"},
        "rights": {"writers": [{"legal_name": "Private Person", "share_bp": 10000}]},
        "sync_status": "cleared", "on_sync_profile": True,
        "preview_key": f"catalog/a/t/previews/{TID}.mp3",
        "waveform_key": f"catalog/a/t/previews/{TID}.waveform.json",
        "email": "owner@email.test",
        **MATCH,
    }
    doc.update(over)
    return doc


def profile(**over):
    p = {"user_id": OWNER, "slug": "tyler-example", "display_name": "Tyler Example",
         "bio": "Producer from NYC.", "location": "New York, NY",
         "spotify_url": "", "instagram_url": "", "photo_key": "profiles/tyler-example/photo/abc",
         "hidden_by_admin": False, "sales_count": 3}
    p.update(over)
    return p


class QueryCollection(FakeCollection):
    """Adds dotted paths and $ne to the fake matcher."""

    @staticmethod
    def _get(doc, path):
        cur = doc
        for part in path.split("."):
            if not isinstance(cur, dict):
                return None
            cur = cur.get(part)
        return cur

    @staticmethod
    def _project(doc, proj):
        """Exclusion and inclusion projections, like Mongo."""
        if proj and any(v == 1 for v in proj.values()):
            return {k: copy.deepcopy(doc[k]) for k, v in proj.items() if v == 1 and k in doc}
        return FakeCollection._project(doc, proj)

    def _match(self, doc, flt):
        for k, v in flt.items():
            actual = self._get(doc, k)
            if isinstance(v, dict) and "$ne" in v:
                if actual == v["$ne"]:
                    return False
            elif actual != v:
                return False
        return True


class FakeR2:
    def __init__(self, waveform=None):
        self.waveform = waveform if waveform is not None else json.dumps(
            {"version": 1, "points": 3, "peaks": [0.1, 0.5, 1.0]}).encode()

    def generate_presigned_url(self, op, Params, ExpiresIn):
        return f"https://r2.test/{Params['Key']}?ttl={ExpiresIn}"

    def get_object(self, Bucket, Key):
        return {"Body": BytesIO(self.waveform), "ContentLength": len(self.waveform)}


@pytest.fixture
def env(monkeypatch):
    db = MagicMock()
    db.track_submissions = QueryCollection([listed_track()])
    db.sync_profiles = QueryCollection([profile()])
    monkeypatch.setattr(server, "db", db)
    r2 = FakeR2()
    monkeypatch.setattr(server, "r2_client", r2)
    monkeypatch.setattr(server.limiter, "enabled", False)
    monkeypatch.setenv("SYNC_PUBLIC_PAGES_ENABLED", "false")
    state = {"viewer": None}
    server.app.dependency_overrides[server.optional_clerk] = lambda: state["viewer"]
    client = TestClient(server.app)

    def as_(who):
        state["viewer"] = None if who is None else {
            "sub": who, "metadata": {"role": "admin" if who == ADMIN else "artist"}}
    yield client, db, r2, as_, monkeypatch
    server.app.dependency_overrides.clear()


def gate(mp, on):
    mp.setenv("SYNC_PUBLIC_PAGES_ENABLED", "true" if on else "false")


def assert_nothing_private(payload):
    text = json.dumps(payload)
    for s in PRIVATE:
        assert s not in text, s
    for f in MATCH:
        assert f'"{f}"' not in text, f
    for f in ('"intake"', '"rights"', '"clerk_user_id"', '"user_id"', '"sales_count"',
              '"preview_key"', '"waveform_key"', '"photo_key"', '"checks"'):
        assert f not in text, f


# ---------------------------------------------------------------------------
# Visibility matrix
# ---------------------------------------------------------------------------

PAGE = "/api/sync/artists/tyler-example"
TRACK = f"/api/sync/tracks/{TID}"


@pytest.mark.parametrize("who, gate_on, listed, expect", [
    (None,  False, True,  404), (None,  True, True,  200), (None,  True, False, 404),
    (OTHER, False, True,  404), (OTHER, True, True,  200), (OTHER, True, False, 404),
    (OWNER, False, True,  200), (OWNER, False, False, 200),
    (ADMIN, False, True,  200), (ADMIN, False, False, 200),
])
def test_artist_page_visibility(env, who, gate_on, listed, expect):
    client, db, r2, as_, mp = env
    gate(mp, gate_on)
    as_(who)
    if not listed:
        db.track_submissions.docs[0]["sync_status"] = "needs_docs"
    resp = client.get(PAGE)
    assert resp.status_code == expect, resp.text
    if expect == 200:
        assert_nothing_private(resp.json())
        assert len(resp.json()["tracks"]) == (1 if listed else 0)


@pytest.mark.parametrize("who, gate_on, listed, expect", [
    (None,  False, True,  404), (None,  True, True,  200), (None,  True, False, 404),
    (OTHER, True, False, 404),
    (OWNER, False, False, 200), (ADMIN, False, False, 200),
])
def test_track_page_visibility(env, who, gate_on, listed, expect):
    client, db, r2, as_, mp = env
    gate(mp, gate_on)
    as_(who)
    if not listed:
        db.track_submissions.docs[0]["sync_status"] = "needs_docs"
    for path, method in ((TRACK, "get"), (TRACK + "/waveform", "get"), (TRACK + "/preview", "post")):
        resp = getattr(client, method)(path)
        assert resp.status_code == expect, (path, resp.text)


def test_unknown_slug_and_track_are_404(env):
    client, db, r2, as_, mp = env
    gate(mp, True)
    as_(ADMIN)
    assert client.get("/api/sync/artists/nobody").status_code == 404
    assert client.get("/api/sync/tracks/nope").status_code == 404


def test_track_without_sync_consent_hidden_even_from_owner(env):
    client, db, r2, as_, mp = env
    db.track_submissions.docs[0]["consent"]["sync"] = False
    as_(OWNER)
    assert client.get(TRACK).status_code == 404


def test_bad_token_is_treated_as_public(monkeypatch):
    async def reject(authorization):
        raise HTTPException(status_code=401, detail="Not authenticated")
    monkeypatch.setattr(server, "verify_clerk_token", reject)
    import asyncio
    assert asyncio.run(server.optional_clerk("Bearer expired")) is None
    assert asyncio.run(server.optional_clerk(None)) is None


# ---------------------------------------------------------------------------
# Listing rule (PRD-03 3.2)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("field, value", [
    ("sync_status", "needs_docs"), ("sync_status", "conflict"),
    ("consent", {"ai_training": True, "sync": False}),
    ("intake", {"content_id": "yes"}), ("intake", {"content_id": "not_sure"}),
    ("on_sync_profile", False), ("sync_delisted_by_admin", True),
])
def test_each_listing_condition_removes_track(env, field, value):
    client, db, r2, as_, mp = env
    assert is_listed(listed_track())
    assert not is_listed(listed_track(**{field: value}))
    db.track_submissions.docs[0][field] = value
    gate(mp, True)
    as_(None)
    assert client.get(PAGE).status_code == 404     # no listed tracks left
    assert client.get(TRACK).status_code == 404


# ---------------------------------------------------------------------------
# What the pages contain
# ---------------------------------------------------------------------------

def test_public_page_content(env):
    client, db, r2, as_, mp = env
    gate(mp, True)
    as_(None)
    body = client.get(PAGE).json()
    assert body["profile"]["display_name"] == "Tyler Example" and body["profile"]["bio"]
    assert body["profile"]["photo_url"].startswith("https://r2.test/")
    t = body["tracks"][0]
    assert t == {"id": TID, "track_name": "Night Drive", "artist_display_name": "Tyler Example",
                 "artist_slug": "tyler-example", "genre": "R&B", "moods": ["Chill"], "vocals": "vocal",
                 "bpm": 90.0, "key": "C major", "duration_s": 184.0,
                 "has_preview": True, "has_waveform": True}
    assert body["viewer"] == {"is_owner": False, "is_admin": False, "public": True}
    assert_nothing_private(client.get(TRACK).json())


def test_owner_preview_flags(env):
    client, db, r2, as_, mp = env
    as_(OWNER)
    v = client.get(PAGE).json()["viewer"]
    assert v == {"is_owner": True, "is_admin": False, "public": False}


@pytest.mark.parametrize("who, sees", [(None, False), (OWNER, False), (ADMIN, True)])
def test_hidden_photo_and_bio(env, who, sees):
    client, db, r2, as_, mp = env
    db.sync_profiles.docs[0]["hidden_by_admin"] = True
    gate(mp, True)
    as_(who)
    p = client.get(PAGE).json()["profile"]
    assert (p["bio"] == "Producer from NYC.") is sees
    assert (p["photo_url"] is not None) is sees
    assert p["display_name"] == "Tyler Example"          # name always stays
    assert p["hidden_by_admin"] is sees


def test_artist_name_falls_back_without_profile(env):
    client, db, r2, as_, mp = env
    db.sync_profiles.docs.clear()
    gate(mp, True)
    as_(None)
    body = client.get(TRACK).json()
    assert body["track"]["artist_display_name"] == "Upload Name" and body["artist"] is None


# ---------------------------------------------------------------------------
# Waveform and preview
# ---------------------------------------------------------------------------

def test_waveform_served_and_clamped(env):
    client, db, r2, as_, mp = env
    r2.waveform = json.dumps({"peaks": [-1, 0.5, 7]}).encode()
    gate(mp, True)
    resp = client.get(TRACK + "/waveform")
    assert resp.status_code == 200
    assert resp.json() == {"version": 1, "points": 3, "peaks": [0.0, 0.5, 1.0]}
    assert "private" in resp.headers["cache-control"]


@pytest.mark.parametrize("blob", [b"not json", json.dumps({"peaks": "x"}).encode(),
                                  json.dumps({"peaks": [0.1] * 6000}).encode(),
                                  b"{" + b" " * (201 * 1024) + b"}"])
def test_bad_or_oversized_waveform_is_404(env, blob):
    client, db, r2, as_, mp = env
    r2.waveform = blob
    gate(mp, True)
    assert client.get(TRACK + "/waveform").status_code == 404


def test_preview_is_short_lived_signed_link(env):
    client, db, r2, as_, mp = env
    gate(mp, True)
    body = client.post(TRACK + "/preview").json()
    assert body["expires_in"] == 300 and "ttl=300" in body["url"]
    assert body["url"].endswith("?ttl=300") and ".mp3" in body["url"]


def test_missing_preview_is_404(env):
    client, db, r2, as_, mp = env
    db.track_submissions.docs[0]["preview_key"] = None
    gate(mp, True)
    assert client.post(TRACK + "/preview").status_code == 404


def test_gate_requires_exact_true(env):
    client, db, r2, as_, mp = env
    for value in ("True", "1", "yes", ""):
        mp.setenv("SYNC_PUBLIC_PAGES_ENABLED", value)
        assert client.get(PAGE).status_code == 404
