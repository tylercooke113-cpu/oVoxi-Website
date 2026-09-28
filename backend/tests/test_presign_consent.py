"""
Phase 1 (PRD-03): upload consent, consent ledger, moods, vocals, sync intake.

No Mongo test fixture exists (conftest mocks motor), so presign_upload is
exercised through TestClient with a mocked db and R2 client, and auth
replaced via dependency_overrides.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

import server


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_db(monkeypatch):
    db = MagicMock()
    db.track_submissions.count_documents = AsyncMock(return_value=0)
    db.track_submissions.insert_one = AsyncMock()
    db.consent_events.insert_many = AsyncMock()
    monkeypatch.setattr(server, "db", db)
    return db


@pytest.fixture
def client(fake_db, monkeypatch):
    r2 = MagicMock()
    r2.generate_presigned_url.return_value = "https://r2.test/presigned"
    monkeypatch.setattr(server, "r2_client", r2)
    monkeypatch.setenv("UPLOADS_ENABLED", "true")
    monkeypatch.setattr(server.limiter, "enabled", False)
    server.app.dependency_overrides[server.require_artist] = lambda: {
        "sub": "user_test", "metadata": {"role": "artist"},
    }
    yield TestClient(server.app)
    server.app.dependency_overrides.clear()


def base(**overrides):
    body = {
        "artist_name": "Test Artist",
        "track_name": "Test Track",
        "genre": "R&B",
        "filename": "track.wav",
        "file_size": 1024,
        "consent_ai_training": True,
        "consent_sync": False,
        "moods": ["Chill", "Dreamy"],
        "vocals": "vocal",
        "rights": rights(),
    }
    body.update(overrides)
    return body


def rights(**overrides):
    body = {"owns_everything": True, "self_legal_name": "Test Person", "attested": True}
    body.update(overrides)
    return body


def intake(**overrides):
    body = {
        "samples": "original",
        "samples_attested": True,
        "distributor": "DistroKid",
        "content_id": "no",
        "pro_not_affiliated": False,
        "pro_name": "BMI",
        "ipi": "00123456789",
    }
    body.update(overrides)
    return body


def post(client, body):
    return client.post("/api/upload/presign", json=body)


def events(fake_db):
    if not fake_db.consent_events.insert_many.await_count:
        return []
    return fake_db.consent_events.insert_many.await_args.args[0]


def inserted_doc(fake_db):
    return fake_db.track_submissions.insert_one.await_args.args[0]


def assert_rejected(resp, fake_db, status=422):
    assert resp.status_code == status, resp.text
    fake_db.track_submissions.insert_one.assert_not_awaited()
    fake_db.consent_events.insert_many.assert_not_awaited()


# ---------------------------------------------------------------------------
# Consent combinations
# ---------------------------------------------------------------------------

def test_neither_consent_rejected(client, fake_db):
    assert_rejected(post(client, base(consent_ai_training=False)), fake_db)


def test_ai_only(client, fake_db):
    resp = post(client, base())
    assert resp.status_code == 200, resp.text
    ev = events(fake_db)
    assert [e["scope"] for e in ev] == ["ai_training"]
    assert all(e["source"] == "upload" and e["action"] == "grant" for e in ev)
    assert all(e["grant_version"] == "draft-0" for e in ev)
    doc = inserted_doc(fake_db)
    assert doc["consent"] == {"ai_training": True, "sync": False}
    assert doc["consent_grant_version"] == "draft-0"
    assert doc["metadata"] == {"moods": ["Chill", "Dreamy"], "vocals": "vocal"}
    assert "intake" not in doc


def test_sync_only(client, fake_db):
    resp = post(client, base(consent_ai_training=False, consent_sync=True, sync_intake=intake()))
    assert resp.status_code == 200, resp.text
    assert [e["scope"] for e in events(fake_db)] == ["sync"]
    doc = inserted_doc(fake_db)
    assert doc["consent"] == {"ai_training": False, "sync": True}
    assert doc["intake"]["samples_attested_at"]
    assert doc["intake"]["ipi"] == "00123456789"
    assert "samples_attested" not in doc["intake"]


def test_both(client, fake_db):
    resp = post(client, base(consent_sync=True, sync_intake=intake()))
    assert resp.status_code == 200, resp.text
    assert sorted(e["scope"] for e in events(fake_db)) == ["ai_training", "sync"]


def test_event_track_id_matches_submission(client, fake_db):
    resp = post(client, base())
    sid = resp.json()["submission_id"]
    assert events(fake_db)[0]["track_id"] == sid
    assert inserted_doc(fake_db)["id"] == sid
    assert events(fake_db)[0]["user_id"] == "user_test"


def test_sync_without_intake_rejected(client, fake_db):
    assert_rejected(post(client, base(consent_sync=True)), fake_db)


def test_intake_without_sync_rejected(client, fake_db):
    assert_rejected(post(client, base(sync_intake=intake())), fake_db)


# ---------------------------------------------------------------------------
# Moods and vocals
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("moods", [
    [],
    ["Chill", "Dreamy", "Sad", "Dark"],
    ["Chill", "Chill"],
    ["Chill", "Spooky"],
])
def test_bad_moods_rejected(client, fake_db, moods):
    assert_rejected(post(client, base(moods=moods)), fake_db)


def test_moods_missing_rejected(client, fake_db):
    body = base()
    del body["moods"]
    assert_rejected(post(client, body), fake_db)


def test_vocals_missing_rejected(client, fake_db):
    body = base()
    del body["vocals"]
    assert_rejected(post(client, body), fake_db)


def test_vocals_invalid_rejected(client, fake_db):
    assert_rejected(post(client, base(vocals="acapella")), fake_db)


# ---------------------------------------------------------------------------
# Sync intake
# ---------------------------------------------------------------------------

def sync_body(**intake_overrides):
    return base(consent_ai_training=False, consent_sync=True, sync_intake=intake(**intake_overrides))


def test_samples_not_attested_rejected(client, fake_db):
    assert_rejected(post(client, sync_body(samples_attested=False)), fake_db)


def test_unknown_distributor_rejected(client, fake_db):
    assert_rejected(post(client, sync_body(distributor="Spotify")), fake_db)


def test_not_affiliated_with_pro_name_rejected(client, fake_db):
    assert_rejected(post(client, sync_body(pro_not_affiliated=True, ipi=None)), fake_db)


def test_not_affiliated_clean_accepted(client, fake_db):
    resp = post(client, sync_body(pro_not_affiliated=True, pro_name=None, ipi=None))
    assert resp.status_code == 200, resp.text


@pytest.mark.parametrize("ipi", [None, "12345678", "1234567890", "12345abc901"])
def test_bad_ipi_rejected(client, fake_db, ipi):
    assert_rejected(post(client, sync_body(ipi=ipi)), fake_db)


def test_unknown_pro_rejected(client, fake_db):
    assert_rejected(post(client, sync_body(pro_name="Spotify")), fake_db)


@pytest.mark.parametrize("ipi", ["123456789", "12345678901"])
def test_valid_pro_and_9_or_11_digit_ipi_accepted(client, fake_db, ipi):
    resp = post(client, sync_body(pro_name="ASCAP", ipi=ipi))
    assert resp.status_code == 200, resp.text


def test_unknown_intake_field_rejected(client, fake_db):
    assert_rejected(post(client, sync_body(isrc="US1234567890")), fake_db)


# ---------------------------------------------------------------------------
# Ledger failure
# ---------------------------------------------------------------------------

def test_ledger_failure_returns_503_and_no_submission(client, fake_db):
    fake_db.consent_events.insert_many.side_effect = RuntimeError("mongo down")
    resp = post(client, base())
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Could not record consent. Please try again."
    fake_db.track_submissions.insert_one.assert_not_awaited()
    assert "presigned_url" not in resp.text
