"""Artist Agreement Stage A: template rendering, hashing, PDF, signing, the gate.

Same approach as test_presign_consent.py: conftest mocks motor, so the routes
run through TestClient with a mocked db and r2_client, auth via
dependency_overrides, limiter disabled, and fetch_clerk_user / send_email
monkeypatched. A temporary agreements dir holds a small template; one test
renders the real agreements/v1.txt.
"""
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError

import artist_agreement
import server

TEST_TEMPLATE = """# Test Agreement

Dated {{agreement_date}} between {{licensor_party}} and oVoxi, reachable at
{{licensor_email}} for account {{platform_account_id}}.

## Section One

The licensor agrees to the following.

- A single sub item.

{{SIGNATURE_BLOCK}}
"""

REAL_AGREEMENTS_DIR = Path(server.__file__).parent / "agreements"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_template_cache():
    artist_agreement.load_template.cache_clear()
    yield
    artist_agreement.load_template.cache_clear()


@pytest.fixture
def agreements_dir(tmp_path, monkeypatch):
    (tmp_path / "v1.txt").write_text(TEST_TEMPLATE, encoding="utf-8")
    monkeypatch.setattr(artist_agreement, "AGREEMENTS_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def fake_db(monkeypatch):
    db = MagicMock()
    db.artist_agreements.find_one = AsyncMock(return_value=None)
    db.artist_agreements.insert_one = AsyncMock()
    db.artist_legal_profiles.find_one = AsyncMock(return_value=None)
    db.artist_legal_profiles.update_one = AsyncMock()
    db.sync_profiles.find_one = AsyncMock(return_value=None)
    db.consent_events.insert_many = AsyncMock()
    db.track_submissions.count_documents = AsyncMock(return_value=0)
    db.track_submissions.insert_one = AsyncMock()
    db.track_submissions.update_one = AsyncMock()
    monkeypatch.setattr(server, "db", db)
    return db


@pytest.fixture
def clerk(monkeypatch):
    m = AsyncMock(return_value={"email": "jane@example.com",
                               "first_name": "Jane", "last_name": "Smith"})
    monkeypatch.setattr(server, "fetch_clerk_user", m)
    return m


@pytest.fixture
def mailer(monkeypatch):
    m = AsyncMock(return_value={"status": "sent", "id": "e1", "error": None})
    monkeypatch.setattr(server, "send_email", m)
    return m


def _r2(monkeypatch):
    r2 = MagicMock()
    r2.put_object.return_value = {}
    r2.generate_presigned_url.return_value = "https://r2.test/presigned"
    monkeypatch.setattr(server, "r2_client", r2)
    return r2


def _artist_client(monkeypatch, role="artist"):
    monkeypatch.setattr(server.limiter, "enabled", False)
    server.app.dependency_overrides[server.require_artist] = lambda: {
        "sub": "user_test", "metadata": {"role": role},
    }
    return TestClient(server.app)


@pytest.fixture
def client(fake_db, clerk, mailer, monkeypatch):
    _r2(monkeypatch)
    c = _artist_client(monkeypatch)
    yield c
    server.app.dependency_overrides.clear()


@pytest.fixture
def r2(client):
    return server.r2_client


# ---------------------------------------------------------------------------
# Pure helpers (no HTTP)
# ---------------------------------------------------------------------------

IND = {"entity_type": "individual", "legal_name": "Jane Q Smith", "artist_name": "",
       "company_name": "", "signer_title": "",
       "address_line1": "1 Main St", "address_line2": "", "city": "Austin",
       "region": "TX", "postal_code": "78701", "country": "USA", "adult_confirmed": True}

ADDR = "1 Main St, Austin, TX 78701, USA"


def _values(**over):
    v = {"agreement_date": "1st day of October, 2026",
         "licensor_party": "Jane Q Smith, of " + ADDR,
         "licensor_email": "jane@example.com", "platform_account_id": "user_test"}
    v.update(over)
    return v


def test_render_text_fills_all_but_signature(agreements_dir):
    text = artist_agreement.render_text("v1", _values())
    assert "{{SIGNATURE_BLOCK}}" in text
    assert "{{" not in text.replace("{{SIGNATURE_BLOCK}}", "")
    assert "jane@example.com" in text and "user_test" in text


def test_render_text_missing_value_raises(agreements_dir):
    vals = _values()
    del vals["platform_account_id"]
    with pytest.raises(KeyError):
        artist_agreement.render_text("v1", vals)


def test_load_template_bad_version(agreements_dir):
    with pytest.raises(ValueError):
        artist_agreement.load_template("../secrets")


def test_licensor_party_individual():
    assert artist_agreement.licensor_party(IND) == "Jane Q Smith, of " + ADDR


def test_licensor_party_individual_with_artist_name():
    f = {**IND, "artist_name": "DJ Jane"}
    assert artist_agreement.licensor_party(f) == 'Jane Q Smith p/k/a "DJ Jane", of ' + ADDR


def test_licensor_party_artist_name_equal_to_legal_name_not_doubled():
    f = {**IND, "artist_name": "jane q smith"}
    assert artist_agreement.licensor_party(f) == "Jane Q Smith, of " + ADDR


def test_licensor_party_company():
    f = {**IND, "entity_type": "company", "company_name": "Acme LLC", "signer_title": "Owner"}
    assert artist_agreement.licensor_party(f) == "Acme LLC, of " + ADDR


def test_blocks_types(agreements_dir):
    text = artist_agreement.render_text("v1", _values())
    types = [b["type"] for b in artist_agreement.blocks(text)]
    assert types == ["title", "para", "heading", "para", "item", "signature"]


def test_agreement_date_ordinals():
    from datetime import datetime, timezone
    d = lambda day: artist_agreement.agreement_date(datetime(2026, 10, day, tzinfo=timezone.utc))
    assert d(1).startswith("1st day of October")
    assert d(2).startswith("2nd day")
    assert d(11).startswith("11th day")
    assert d(23).startswith("23rd day")


def test_render_pdf_real_v1_multipage(monkeypatch):
    monkeypatch.setattr(artist_agreement, "AGREEMENTS_DIR", REAL_AGREEMENTS_DIR)
    artist_agreement.load_template.cache_clear()
    text = artist_agreement.render_text("v1", _values())
    sig = {"agreement_id": "a-1", "version": "v1", "text_sha256": "0" * 64,
           "signed_at": "2026-10-01T00:00:00+00:00", "typed_signature": "Jane Q Smith",
           "licensor_email": "jane@example.com", "platform_account_id": "user_test",
           "ip": "203.0.113.9", "fields": IND}
    pdf = artist_agreement.render_pdf(text, sig)
    assert pdf[:4] == b"%PDF"
    pages = len(re.findall(rb"/Type\s*/Page(?![s])", pdf))
    assert pages > 1


# ---------------------------------------------------------------------------
# Field validation (through /agreement/preview -> 422 before the body runs)
# ---------------------------------------------------------------------------

def _preview(client, **over):
    body = {k: v for k, v in IND.items()}
    body.update(over)
    return client.post("/api/agreement/preview", json=body)


@pytest.mark.parametrize("over", [
    {"adult_confirmed": False},
    {"city": ""},
    {"entity_type": "company", "company_name": "Acme LLC", "signer_title": ""},
    {"entity_type": "individual", "company_name": "Acme LLC"},
    {"legal_name": "Jane {{x}} Smith"},
    {"legal_name": "Jane\nSmith"},
])
def test_bad_fields_rejected(client, agreements_dir, over):
    resp = _preview(client, **over)
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def test_status_unsigned(client, fake_db, clerk):
    resp = client.get("/api/agreement/status")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["signed"] is False and body["current_version"] == "v1"
    assert body["enforced"] is False and body["required"] is True
    assert body["prefill"] is not None


def test_status_signed_does_not_call_clerk(client, fake_db, clerk):
    fake_db.artist_agreements.find_one = AsyncMock(
        return_value={"id": "a1", "version": "v1", "signed_at": "2026-10-01T00:00:00+00:00"})
    resp = client.get("/api/agreement/status")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["signed"] is True and body["prefill"] is None
    assert clerk.await_count == 0


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

def test_preview_returns_blocks_and_hash(client, agreements_dir, clerk):
    resp = _preview(client)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["version"] == "v1" and body["email"] == "jane@example.com"
    assert any(b["type"] == "signature" for b in body["blocks"])
    assert re.fullmatch(r"[0-9a-f]{64}", body["text_sha256"])


# ---------------------------------------------------------------------------
# Sign
# ---------------------------------------------------------------------------

def _sign_body(client, **over):
    """Preview to get the live hash, then build a matching sign body."""
    pv = _preview(client).json()
    body = {"fields": IND, "text_sha256": pv["text_sha256"],
            "typed_signature": "Jane Q Smith", "consent_electronic": True, "agreed": True}
    body.update(over)
    return body


def test_sign_happy_path(client, fake_db, r2, mailer, agreements_dir):
    resp = client.post("/api/agreement/sign", json=_sign_body(client))
    assert resp.status_code == 200, resp.text
    agr = resp.json()["agreement"]
    assert agr["version"] == "v1" and agr["id"]
    assert r2.put_object.call_count == 1
    key = r2.put_object.call_args.kwargs["Key"]
    assert key == f"agreements/user_test/{agr['id']}.pdf"
    doc = fake_db.artist_agreements.insert_one.await_args.args[0]
    assert re.fullmatch(r"[0-9a-f]{64}", doc["text_sha256"])
    assert re.fullmatch(r"[0-9a-f]{64}", doc["pdf_sha256"])
    assert doc["ip"] and "user_agent" in doc
    assert mailer.await_count == 1
    assert mailer.await_args.kwargs["attachments"][0][0] == "oVoxi-Artist-Agreement.pdf"


def test_sign_hash_mismatch(client, fake_db, r2, agreements_dir):
    body = _sign_body(client, text_sha256="f" * 64)
    resp = client.post("/api/agreement/sign", json=body)
    assert resp.status_code == 409, resp.text
    r2.put_object.assert_not_called()
    fake_db.artist_agreements.insert_one.assert_not_awaited()


def test_sign_typed_name_differs(client, r2, agreements_dir):
    body = _sign_body(client, typed_signature="Someone Else")
    resp = client.post("/api/agreement/sign", json=body)
    assert resp.status_code == 422, resp.text
    r2.put_object.assert_not_called()


def test_sign_already_signed(client, fake_db, r2, agreements_dir):
    body = _sign_body(client)
    fake_db.artist_agreements.find_one = AsyncMock(
        return_value={"id": "a1", "version": "v1", "signed_at": "x"})
    resp = client.post("/api/agreement/sign", json=body)
    assert resp.status_code == 409, resp.text
    r2.put_object.assert_not_called()


def test_sign_r2_failure(client, fake_db, r2, agreements_dir):
    body = _sign_body(client)
    r2.put_object.side_effect = RuntimeError("r2 down")
    resp = client.post("/api/agreement/sign", json=body)
    assert resp.status_code == 503, resp.text
    fake_db.artist_agreements.insert_one.assert_not_awaited()


def test_sign_duplicate_key(client, fake_db, r2, agreements_dir):
    body = _sign_body(client)
    fake_db.artist_agreements.insert_one.side_effect = DuplicateKeyError("dup")
    resp = client.post("/api/agreement/sign", json=body)
    assert resp.status_code == 409, resp.text


def test_sign_email_failure_still_200(client, fake_db, r2, mailer, agreements_dir):
    body = _sign_body(client)
    mailer.return_value = {"status": "failed", "id": None, "error": "boom"}
    resp = client.post("/api/agreement/sign", json=body)
    assert resp.status_code == 200, resp.text


def test_sign_clerk_unavailable(client, fake_db, r2, clerk, agreements_dir):
    body = _sign_body(client)  # preview succeeds first
    clerk.side_effect = HTTPException(status_code=503, detail="Could not load your account.")
    resp = client.post("/api/agreement/sign", json=body)
    assert resp.status_code == 503, resp.text
    r2.put_object.assert_not_called()


# ---------------------------------------------------------------------------
# PDF endpoint
# ---------------------------------------------------------------------------

def test_pdf_none(client, fake_db):
    resp = client.get("/api/agreement/pdf")
    assert resp.status_code == 404, resp.text


def test_pdf_signed(client, fake_db, r2):
    fake_db.artist_agreements.find_one = AsyncMock(
        return_value={"pdf_key": "agreements/user_test/a1.pdf"})
    resp = client.get("/api/agreement/pdf")
    assert resp.status_code == 200, resp.text
    assert resp.json()["url"] == "https://r2.test/presigned"


# ---------------------------------------------------------------------------
# The upload gate (presign)
# ---------------------------------------------------------------------------

PRESIGN_BODY = {
    "artist_name": "Test Artist", "track_name": "Test Track", "genre": "R&B",
    "filename": "track.wav", "file_size": 1024,
    "consent_ai_training": True, "consent_sync": False,
    "moods": ["Chill", "Dreamy"], "vocals": "vocal", "bpm": 120.0, "key": "C major",
    "rights": {"owns_everything": True, "self_legal_name": "Test Person", "attested": True},
}


def _presign(client):
    return client.post("/api/upload/presign", json=PRESIGN_BODY)


def _events(fake_db):
    return fake_db.consent_events.insert_many.await_args.args[0]


def test_presign_enforced_unsigned_artist_403(client, fake_db, monkeypatch):
    monkeypatch.setenv("ARTIST_AGREEMENT_ENFORCED", "true")
    resp = _presign(client)
    assert resp.status_code == 403, resp.text
    fake_db.track_submissions.insert_one.assert_not_awaited()
    fake_db.consent_events.insert_many.assert_not_awaited()


def test_presign_enforced_unsigned_admin_passes(fake_db, clerk, mailer, monkeypatch):
    monkeypatch.setenv("ARTIST_AGREEMENT_ENFORCED", "true")
    _r2(monkeypatch)
    c = _artist_client(monkeypatch, role="admin")
    try:
        resp = c.post("/api/upload/presign", json=PRESIGN_BODY)
        assert resp.status_code == 200, resp.text
        assert fake_db.track_submissions.insert_one.await_args.args[0]["agreement_id"] is None
    finally:
        server.app.dependency_overrides.clear()


def test_presign_enforced_signed_events_carry_agreement(client, fake_db, monkeypatch):
    monkeypatch.setenv("ARTIST_AGREEMENT_ENFORCED", "true")
    fake_db.artist_agreements.find_one = AsyncMock(
        return_value={"id": "agr1", "version": "v1", "signed_at": "x"})
    resp = _presign(client)
    assert resp.status_code == 200, resp.text
    ev = _events(fake_db)
    assert all(e["agreement_id"] == "agr1" for e in ev)
    assert all(e["grant_version"] == "v1" for e in ev)
    assert fake_db.track_submissions.insert_one.await_args.args[0]["agreement_id"] == "agr1"


def test_presign_not_enforced_unsigned_ok(client, fake_db, monkeypatch):
    monkeypatch.delenv("ARTIST_AGREEMENT_ENFORCED", raising=False)
    resp = _presign(client)
    assert resp.status_code == 200, resp.text
    ev = _events(fake_db)
    assert all("agreement_id" not in e for e in ev)
    assert all(e["grant_version"] == "draft-0" for e in ev)
    assert fake_db.track_submissions.insert_one.await_args.args[0]["agreement_id"] is None


# ---------------------------------------------------------------------------
# The vault-consent gate
# ---------------------------------------------------------------------------

def test_vault_grant_enforced_unsigned_403(client, fake_db, monkeypatch):
    monkeypatch.setenv("ARTIST_AGREEMENT_ENFORCED", "true")
    monkeypatch.setattr(server, "_owned_track",
                        AsyncMock(return_value={"consent": {"ai_training": False, "sync": False}}))
    resp = client.post("/api/vault/tracks/t1/consent",
                       json={"scope": "ai_training", "action": "grant"})
    assert resp.status_code == 403, resp.text
    fake_db.consent_events.insert_many.assert_not_awaited()


def test_vault_withdraw_enforced_unsigned_passes(client, fake_db, monkeypatch):
    monkeypatch.setenv("ARTIST_AGREEMENT_ENFORCED", "true")
    monkeypatch.setattr(server, "_owned_track",
                        AsyncMock(return_value={"consent": {"ai_training": True, "sync": False}}))
    monkeypatch.setattr(server, "vault_track_view", lambda doc: {})
    resp = client.post("/api/vault/tracks/t1/consent",
                       json={"scope": "ai_training", "action": "withdraw"})
    assert resp.status_code == 200, resp.text
    assert fake_db.consent_events.insert_many.await_count == 1


# ---------------------------------------------------------------------------
# v2 buyouts (Brief 16)
# ---------------------------------------------------------------------------

def test_supports_buyouts_v1_v2(monkeypatch):
    monkeypatch.setattr(artist_agreement, "AGREEMENTS_DIR", REAL_AGREEMENTS_DIR)
    artist_agreement.load_template.cache_clear()
    assert artist_agreement.supports_buyouts("v1") is False
    assert artist_agreement.supports_buyouts("v2") is True


def test_status_previous_signed(client, fake_db, clerk, monkeypatch):
    monkeypatch.setenv("ARTIST_AGREEMENT_VERSION", "v2")
    monkeypatch.setattr(artist_agreement, "AGREEMENTS_DIR", REAL_AGREEMENTS_DIR)
    artist_agreement.load_template.cache_clear()

    def find_one(q, *a, **k):
        ver = q.get("version")
        return {"_id": "x"} if isinstance(ver, dict) and "$ne" in ver else None
    fake_db.artist_agreements.find_one = AsyncMock(side_effect=find_one)

    body = client.get("/api/agreement/status").json()
    assert body["signed"] is False and body["previous_signed"] is True
    assert body["buyouts_supported"] is True and body["current_version"] == "v2"
