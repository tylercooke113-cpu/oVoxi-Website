"""
PRD-03 Phase 4a: Vault fields, artist edits, consent changes, sync profile,
and ACRCloud match detail never leaving the database (decision 13).
Mocked db (conftest mocks motor); a tiny projection-aware fake stands in for
Mongo where the projection itself is what is being tested.
"""
import copy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError

import server
from metadata_reconcile import reconcile
from sync_vault import slugify_profile, vault_track_view

UID = "user_artist"
TID = "track-1"
MATCH = {"matched_title": "Famous Song", "matched_artist": "Famous Artist", "matched_label": "Big Label",
         "matched_isrc": "USABC1234567", "confidence": 97, "acrid": "acr123", "raw_code": 0}


def track(**overrides):
    doc = {
        "id": TID, "clerk_user_id": UID, "artist_name": "Test", "track_name": "Night Drive",
        "genre": "R&B", "upload_date": "2026-09-28T00:00:00+00:00", "status": "completed",
        "consent": {"ai_training": True, "sync": False},
        "metadata": {"moods": ["Chill"], "vocals": "vocal", "duration_s": 180.0,
                     "bpm": None, "bpm_source": "detected", "bpm_detected": 129.0, "bpm_unsure": True,
                     "bpm_needs_confirmation": True,
                     "key": "A minor", "key_source": "detected", "key_detected": "A minor",
                     "key_unsure": True, "key_needs_confirmation": True},
        "intake": {"samples": "original", "ipi": "00123456789", "pro_name": "BMI"},
        "rights": {"writers": [{"legal_name": "Private Person", "share_bp": 10000}]},
        "fingerprint_result": "CLEARED",
        **MATCH,
    }
    doc.update(overrides)
    return doc


class FakeCollection:
    """Just enough of a Mongo collection: filter by equality, exclusion
    projections, $set with dotted paths."""

    def __init__(self, docs=None):
        self.docs = [copy.deepcopy(d) for d in (docs or [])]
        self.updates = []
        self.inserted = []
        self.insert_one = AsyncMock(side_effect=self._insert_one)
        self.insert_many = AsyncMock(side_effect=self._insert_many)

    def _match(self, doc, flt):
        return all(doc.get(k) == v for k, v in flt.items())

    @staticmethod
    def _project(doc, proj):
        out = copy.deepcopy(doc)
        if proj:
            for k, v in proj.items():
                if v == 0:
                    out.pop(k, None)
        return out

    async def find_one(self, flt, proj=None):
        for d in self.docs:
            if self._match(d, flt):
                return self._project(d, proj)
        return None

    async def update_one(self, flt, update):
        self.updates.append(update)
        for d in self.docs:
            if self._match(d, flt):
                for path, value in update.get("$set", {}).items():
                    cur = d
                    parts = path.split(".")
                    for p in parts[:-1]:
                        cur = cur.setdefault(p, {})
                    cur[parts[-1]] = value
                return SimpleNamespace(matched_count=1)
        return SimpleNamespace(matched_count=0)

    async def _insert_one(self, doc):
        self.inserted.append(doc)
        self.docs.append(copy.deepcopy(doc))

    async def _insert_many(self, docs):
        self.inserted.extend(docs)

    def find(self, flt=None, proj=None):
        rows = [self._project(d, proj) for d in self.docs if self._match(d, flt or {})]
        cursor = MagicMock()
        cursor.sort.return_value.to_list = AsyncMock(return_value=rows)
        return cursor


@pytest.fixture
def db(monkeypatch):
    fake = MagicMock()
    fake.track_submissions = FakeCollection([track()])
    fake.consent_events = FakeCollection()
    fake.sync_profiles = FakeCollection()
    # vault consent grant now reads the artist agreement (Stage A gate); unsigned by default.
    fake.artist_agreements.find_one = AsyncMock(return_value=None)
    monkeypatch.setattr(server, "db", fake)
    return fake


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setattr(server.limiter, "enabled", False)
    r2 = MagicMock()
    r2.generate_presigned_url.return_value = "https://r2.test/signed"
    monkeypatch.setattr(server, "r2_client", r2)
    artist = {"sub": UID, "metadata": {"role": "artist"}}
    server.app.dependency_overrides[server.require_artist] = lambda: artist
    server.app.dependency_overrides[server.verify_clerk_token] = lambda: artist
    server.app.dependency_overrides[server.require_admin] = lambda: {"sub": "admin", "metadata": {"role": "admin"}}
    yield TestClient(server.app)
    server.app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Match detail is database-only (decision 13)
# ---------------------------------------------------------------------------

def assert_no_match_detail(payload):
    text = json.dumps(payload, default=str)
    for field, value in MATCH.items():
        assert f'"{field}"' not in text, field
        if isinstance(value, str):
            assert value not in text, value


def test_admin_submissions_never_return_match_detail(client, db):
    db.track_submissions.docs[0].update(status="CONFLICT", fingerprint_result="CONFLICT")
    resp = client.get("/api/submissions")
    assert resp.status_code == 200, resp.text
    assert resp.json()[0]["status"] == "CONFLICT"
    assert_no_match_detail(resp.json())


def test_vault_never_returns_match_detail_intake_or_splits(client):
    resp = client.get("/api/vault/tracks")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert_no_match_detail(body)
    text = json.dumps(body)
    assert "Private Person" not in text and "00123456789" not in text
    assert '"intake"' not in text and '"rights"' not in text and '"fingerprint_result"' not in text


def test_vault_edit_responses_never_return_match_detail(client):
    resp = client.patch(f"/api/vault/tracks/{TID}/metadata", json={"key": "A minor"})
    assert resp.status_code == 200, resp.text
    assert_no_match_detail(resp.json())


# ---------------------------------------------------------------------------
# Vault view
# ---------------------------------------------------------------------------

def test_vault_view_fields(client):
    t = client.get("/api/vault/tracks").json()[0]
    assert t["legacy"] is False
    assert t["consent"] == {"ai_training": True, "sync": False}
    assert t["metadata"]["key"] == "A minor" and t["metadata"]["key_needs_confirmation"] is True
    assert t["sync_status"] is None and t["sync_reasons"] == [] and t["on_sync_profile"] is False


def test_vault_view_legacy():
    assert vault_track_view({"id": "x", "status": "completed"}) == {"legacy": True}


def test_vault_view_sync_reasons():
    doc = track(consent={"ai_training": False, "sync": True}, sync_status="needs_docs",
                checks={"content_id": {"result": "fail", "reason": "content_id"},
                        "pro": {"result": "pass", "reason": None},
                        "metadata": {"result": "fail", "reason": "confirm: key"}})
    v = vault_track_view(doc)
    assert v["sync_status"] == "needs_docs"
    assert sorted(v["sync_reasons"]) == ["confirm: key", "content_id"]


# ---------------------------------------------------------------------------
# PATCH metadata
# ---------------------------------------------------------------------------

def test_confirm_key_sets_artist_confirmed(client, db):
    resp = client.patch(f"/api/vault/tracks/{TID}/metadata", json={"key": "A minor"})
    assert resp.status_code == 200, resp.text
    m = db.track_submissions.docs[0]["metadata"]
    assert m["key"] == "A minor" and m["key_source"] == "artist"
    assert m["key_needs_confirmation"] is False and m["key_confirmed"] is True and m["key_unsure"] is False
    assert resp.json()["metadata"]["key_needs_confirmation"] is False


def test_edit_bpm_moods_genre(client, db):
    resp = client.patch(f"/api/vault/tracks/{TID}/metadata",
                        json={"bpm": 130, "moods": ["Energetic", "Gritty"], "genre": "Hip-Hop"})
    assert resp.status_code == 200, resp.text
    d = db.track_submissions.docs[0]
    assert d["metadata"]["bpm"] == 130.0 and d["metadata"]["bpm_confirmed"] is True
    assert d["metadata"]["moods"] == ["Energetic", "Gritty"] and d["genre"] == "Hip-Hop"


@pytest.mark.parametrize("body", [
    {}, {"bpm": 500}, {"key": "H major"}, {"moods": []}, {"moods": ["A", "B", "C", "D"]},
    {"moods": ["Chill", "Chill"]}, {"genre": "Polka"}, {"bpm_source": "artist"},
])
def test_bad_metadata_patch_rejected(client, db, body):
    resp = client.patch(f"/api/vault/tracks/{TID}/metadata", json=body)
    assert resp.status_code == 422, resp.text
    assert db.track_submissions.updates == []


def test_other_artists_track_is_404(client, db):
    db.track_submissions.docs[0]["clerk_user_id"] = "someone_else"
    assert client.patch(f"/api/vault/tracks/{TID}/metadata", json={"bpm": 90}).status_code == 404
    assert client.post(f"/api/vault/tracks/{TID}/consent",
                       json={"scope": "ai_training", "action": "withdraw"}).status_code == 404


def test_legacy_track_is_409(client, db):
    del db.track_submissions.docs[0]["consent"]
    resp = client.patch(f"/api/vault/tracks/{TID}/metadata", json={"bpm": 90})
    assert resp.status_code == 409
    assert "before usage options" in resp.json()["detail"]


def test_patch_runs_clearance(client, monkeypatch):
    spy = AsyncMock()
    monkeypatch.setattr(server, "_run_clearance", spy)
    client.patch(f"/api/vault/tracks/{TID}/metadata", json={"bpm": 90})
    spy.assert_awaited_once_with(TID)


def test_confirmed_value_never_held_by_later_detection():
    meta = {"bpm": 103.0, "bpm_source": "artist", "bpm_unsure": False, "bpm_confirmed": True,
            "key": "C major", "key_source": "artist", "key_unsure": False, "key_confirmed": True}
    out = reconcile(meta, 130.0, "F# minor")
    assert out["metadata.bpm"] == 103.0 and out["metadata.bpm_needs_confirmation"] is False
    assert out["metadata.key"] == "C major" and out["metadata.key_needs_confirmation"] is False
    assert out["metadata.bpm_detected"] == 130.0


# ---------------------------------------------------------------------------
# Consent changes
# ---------------------------------------------------------------------------

INTAKE = {"samples": "original", "samples_attested": True, "distributor": "DistroKid",
          "content_id": "no", "pro_not_affiliated": True}


def consent(client, **body):
    return client.post(f"/api/vault/tracks/{TID}/consent", json=body)


def test_add_sync_writes_event_intake_and_runs_clearance(client, db, monkeypatch):
    spy = AsyncMock()
    monkeypatch.setattr(server, "_run_clearance", spy)
    resp = consent(client, scope="sync", action="grant", sync_intake=INTAKE)
    assert resp.status_code == 200, resp.text
    ev = db.consent_events.inserted
    assert len(ev) == 1 and ev[0]["scope"] == "sync" and ev[0]["action"] == "grant" and ev[0]["source"] == "vault"
    d = db.track_submissions.docs[0]
    assert d["consent"]["sync"] is True and d["intake"]["samples_attested_at"]
    spy.assert_awaited_once_with(TID)


def test_add_sync_requires_intake(client, db):
    assert consent(client, scope="sync", action="grant").status_code == 422
    assert db.consent_events.inserted == []


def test_intake_only_when_adding_sync(client, db):
    assert consent(client, scope="ai_training", action="withdraw", sync_intake=INTAKE).status_code == 422


def test_remove_sync_delists(client, db):
    db.track_submissions.docs[0].update(consent={"ai_training": True, "sync": True},
                                        on_sync_profile=True, sync_status="cleared",
                                        sync_listed_at="t", checks={"splits": {}})
    resp = consent(client, scope="sync", action="withdraw")
    assert resp.status_code == 200, resp.text
    d = db.track_submissions.docs[0]
    assert d["consent"]["sync"] is False and d["on_sync_profile"] is False
    assert d["sync_delisted_at"] and d["sync_status"] is None and d["checks"] is None
    assert d["sync_listed_at"] == "t"   # history kept
    ev = db.consent_events.inserted[0]
    assert ev["action"] == "withdraw" and ev["scope"] == "sync"


def test_remove_ai_training(client, db):
    resp = consent(client, scope="ai_training", action="withdraw")
    assert resp.status_code == 200
    assert db.track_submissions.docs[0]["consent"] == {"ai_training": False, "sync": False}
    assert db.consent_events.inserted[0]["action"] == "withdraw"


def test_no_op_change_is_409_without_event(client, db):
    resp = consent(client, scope="ai_training", action="grant")
    assert resp.status_code == 409 and "already on" in resp.json()["detail"]
    assert db.consent_events.inserted == []


def test_ledger_failure_changes_nothing(client, db):
    db.consent_events.insert_many.side_effect = RuntimeError("mongo down")
    resp = consent(client, scope="ai_training", action="withdraw")
    assert resp.status_code == 503
    assert db.track_submissions.docs[0]["consent"]["ai_training"] is True
    assert db.track_submissions.updates == []


@pytest.mark.parametrize("body", [
    {"scope": "stems", "action": "grant"}, {"scope": "sync", "action": "delete"},
    {"scope": "sync", "action": "withdraw", "extra": 1},
])
def test_bad_consent_body_rejected(client, db, body):
    assert client.post(f"/api/vault/tracks/{TID}/consent", json=body).status_code == 422


# ---------------------------------------------------------------------------
# Sync profile
# ---------------------------------------------------------------------------

PROFILE = {"display_name": "Tyler Example", "bio": "Producer from NYC.", "location": "New York, NY",
           "spotify_url": "https://open.spotify.com/artist/4Z8W4fKeB5YxbusRsdQVPb",
           "instagram_url": "https://instagram.com/tyler.example"}


def test_profile_empty_then_created_with_slug(client, db):
    assert client.get("/api/sync/profile").json() == {}
    resp = client.put("/api/sync/profile", json=PROFILE)
    assert resp.status_code == 200, resp.text
    p = resp.json()
    assert p["slug"] == "tyler-example" and p["display_name"] == "Tyler Example"
    assert "user_id" not in p and "hidden_by_admin" not in p and "sales_count" not in p


def test_slug_never_changes_on_later_saves(client, db):
    client.put("/api/sync/profile", json=PROFILE)
    resp = client.put("/api/sync/profile", json={**PROFILE, "display_name": "New Name"})
    assert resp.json()["slug"] == "tyler-example" and resp.json()["display_name"] == "New Name"


def test_slug_taken_gets_suffix(client, db):
    calls = {"n": 0}
    original = db.sync_profiles._insert_one

    async def insert(doc):
        calls["n"] += 1
        if doc["slug"] == "tyler-example":
            raise DuplicateKeyError("E11000 duplicate key error index: slug_1")
        return await original(doc)
    db.sync_profiles.insert_one.side_effect = insert
    resp = client.put("/api/sync/profile", json=PROFILE)
    assert resp.status_code == 200, resp.text
    assert resp.json()["slug"] == "tyler-example-2"


@pytest.mark.parametrize("field, value", [
    ("display_name", "   "), ("display_name", "x" * 81), ("bio", "x" * 501), ("location", "x" * 81),
    ("spotify_url", "https://open.spotify.com/track/4Z8W4fKeB5YxbusRsdQVPb"),
    ("spotify_url", "http://open.spotify.com/artist/4Z8W4fKeB5YxbusRsdQVPb"),
    ("spotify_url", "https://evil.com/?u=open.spotify.com/artist/x"),
    ("instagram_url", "https://instagram.com/"), ("instagram_url", "https://evil.com/instagram.com/x"),
])
def test_bad_profile_rejected(client, db, field, value):
    resp = client.put("/api/sync/profile", json={**PROFILE, field: value})
    assert resp.status_code == 422, resp.text
    assert db.sync_profiles.inserted == []


def test_profile_links_optional(client):
    resp = client.put("/api/sync/profile", json={"display_name": "Solo"})
    assert resp.status_code == 200 and resp.json()["spotify_url"] == ""


@pytest.mark.parametrize("name, slug", [
    ("Tyler Example", "tyler-example"), ("  Beyoncé & Co.  ", "beyonce-co"),
    ("MIKE!!melodiaa", "mike-melodiaa"), ("日本", ""),
])
def test_slugify(name, slug):
    assert slugify_profile(name) == slug


def test_all_symbol_name_falls_back(client):
    assert client.put("/api/sync/profile", json={"display_name": "日本"}).json()["slug"] == "artist"
