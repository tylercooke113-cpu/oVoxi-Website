"""
Brief 22 Part C: co-owner sign-off.

The suite mocks motor (see conftest), so there is no Mongo. These tests drive the
cosign routes through TestClient against a small in-memory fake that supports the
handful of query operators the routes use, plus direct calls to the dispatch helper.
send_email and the R2 client are mocked; fetch_clerk_user is left to raise (no
CLERK_SECRET_KEY in tests), so uploader-notification emails are simply skipped.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError

import cosign
import server


# ---------------------------------------------------------------------------
# A tiny async fake for the two collections cosign touches
# ---------------------------------------------------------------------------

class FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    async def to_list(self, n=None):
        return [dict(d) for d in self._docs]


class FakeCollection:
    def __init__(self, unique=()):
        self.docs = []
        self._unique = unique  # tuples of key names forming a unique index

    @staticmethod
    def _match(d, flt):
        for k, v in flt.items():
            dv = d.get(k)
            if isinstance(v, dict):
                if "$ne" in v and dv == v["$ne"]:
                    return False
                if "$in" in v and dv not in v["$in"]:
                    return False
            elif dv != v:
                return False
        return True

    async def insert_one(self, doc):
        for keys in self._unique:
            if any(doc.get(k) is not None for k in keys):
                for existing in self.docs:
                    if all(existing.get(k) == doc.get(k) for k in keys):
                        raise DuplicateKeyError(f"dup {keys}")
        self.docs.append(dict(doc))
        return SimpleNamespace(inserted_id="x")

    async def find_one(self, flt, proj=None):
        for d in self.docs:
            if self._match(d, flt):
                return dict(d)
        return None

    def find(self, flt, proj=None):
        return FakeCursor([d for d in self.docs if self._match(d, flt)])

    async def update_one(self, flt, update):
        for d in self.docs:
            if self._match(d, flt):
                d.update(update.get("$set", {}))
                for k, n in update.get("$inc", {}).items():
                    d[k] = d.get(k, 0) + n
                return SimpleNamespace(matched_count=1)
        return SimpleNamespace(matched_count=0)

    async def create_index(self, *a, **k):
        return None


class FakeDB:
    def __init__(self):
        self.track_submissions = FakeCollection()
        self.cosign_requests = FakeCollection(
            unique=(("token_sha256",), ("track_id", "email")))
        self.artist_agreements = FakeCollection()


TRACK_ID = "track-1"
UID = "user_uploader"


def make_track(**overrides):
    doc = {
        "id": TRACK_ID,
        "artist_name": "Alex Artist",
        "track_name": "Night Drive",
        "clerk_user_id": UID,
        "agreement_id": None,
        "consent": {"ai_training": True, "sync": False},
        "cosign_required": True,
        "cosign_status": "pending",
        "rights": {
            "owns_everything": False,
            "self_legal_name": "Alex Uploader",
            "writers": [
                {"legal_name": "Alex Uploader", "share_bp": 5000, "role": "CA",
                 "is_self": True, "email": None},
                {"legal_name": "Dana Cowriter", "share_bp": 5000, "role": "C",
                 "is_self": False, "email": "dana@example.com"},
            ],
            "publishers": [
                {"legal_name": "Dana Cowriter", "share_bp": 10000, "role": "E",
                 "is_self": False, "email": "dana@example.com"},
            ],
            "master_owners": [
                {"legal_name": "Alex Uploader", "share_bp": 10000, "role": None,
                 "is_self": True, "email": None},
            ],
        },
    }
    doc.update(overrides)
    return doc


@pytest.fixture
def db(monkeypatch):
    fake = FakeDB()
    monkeypatch.setattr(server, "db", fake)
    return fake


@pytest.fixture
def sent(monkeypatch):
    mock = AsyncMock(return_value={"status": "sent", "id": "e1", "error": None})
    monkeypatch.setattr(server, "send_email", mock)
    return mock


@pytest.fixture
def client(db, sent, monkeypatch):
    r2 = MagicMock()
    monkeypatch.setattr(server, "r2_client", r2)
    monkeypatch.setattr(server.limiter, "enabled", False)
    yield TestClient(server.app)
    server.app.dependency_overrides.clear()


def run(coro):
    return asyncio.run(coro)


def seed_request(db, token, *, status="pending", email="dana@example.com",
                 interests=None, **overrides):
    req = {
        "id": overrides.get("id", "req-1"), "track_id": TRACK_ID,
        "uploader_clerk_user_id": UID, "email": email,
        "interests": interests or [
            {"side": "writers", "legal_name": "Dana Cowriter", "role": "C", "share_bp": 5000},
            {"side": "publishers", "legal_name": "Dana Cowriter", "role": "E", "share_bp": 10000},
        ],
        "token_sha256": server._hash_token(token),
        "token_expires_at": "2099-01-01T00:00:00+00:00",
        "status": status, "created_at": "2026-10-20T00:00:00+00:00",
        "sent_at": None, "send_count": 1, "last_sent_at": None,
        "signed_at": None, "typed_signature": None, "entity_type": None,
        "signer_name": None, "signer_title": None, "legal_name": None,
        "ip": None, "consent_version": "cosign_v1", "text_sha256": None, "pdf_key": None,
        "declined_at": None, "decline_reason": None,
    }
    req.update(overrides)
    db.cosign_requests.docs.append(req)
    return req


# ---------------------------------------------------------------------------
# C3: dispatch
# ---------------------------------------------------------------------------

def test_dispatch_creates_one_request_per_unique_email(db, sent):
    run(server._dispatch_cosign_requests(make_track()))
    # Dana is both a writer and a publisher but one email: one request, two interests.
    assert len(db.cosign_requests.docs) == 1
    req = db.cosign_requests.docs[0]
    assert req["email"] == "dana@example.com"
    assert {i["side"] for i in req["interests"]} == {"writers", "publishers"}
    assert sent.await_count == 1
    assert req["sent_at"] is not None and req["send_count"] == 1


def test_dispatch_is_idempotent(db, sent):
    run(server._dispatch_cosign_requests(make_track()))
    run(server._dispatch_cosign_requests(make_track()))
    assert len(db.cosign_requests.docs) == 1
    assert sent.await_count == 1  # second run sends nothing


def test_dispatch_email_failure_still_creates_request(db, sent):
    sent.return_value = {"status": "failed", "id": None, "error": "boom"}
    run(server._dispatch_cosign_requests(make_track()))
    req = db.cosign_requests.docs[0]
    assert req["sent_at"] is None  # Vault will show "Not sent"
    assert req["send_count"] == 0


# ---------------------------------------------------------------------------
# C4: GET / sign / decline
# ---------------------------------------------------------------------------

def test_get_returns_consent_and_agreement(client, db):
    db.track_submissions.docs.append(make_track())
    seed_request(db, "tok-good")
    r = client.get("/api/cosign/tok-good")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["track_title"] == "Night Drive"
    assert body["uploader_name"] == "Alex Uploader"
    assert len(body["text_sha256"]) == 64
    assert body["consent_blocks"] and body["agreement_blocks"]
    assert body["uses"] == ["AI training"]


def test_get_unknown_token_404(client, db):
    assert client.get("/api/cosign/nope").status_code == 404


def test_get_expired_token_404(client, db):
    db.track_submissions.docs.append(make_track())
    seed_request(db, "tok-old", token_expires_at="2000-01-01T00:00:00+00:00")
    assert client.get("/api/cosign/tok-old").status_code == 404


def test_get_used_token_409(client, db):
    db.track_submissions.docs.append(make_track())
    seed_request(db, "tok-used", status="signed", signed_at="2026-10-20T00:00:00+00:00")
    r = client.get("/api/cosign/tok-used")
    assert r.status_code == 409
    assert r.json()["detail"]["status"] == "signed"


def _hash_for(client, token):
    return client.get(f"/api/cosign/{token}").json()["text_sha256"]


def test_sign_with_matching_name(client, db):
    db.track_submissions.docs.append(make_track())
    seed_request(db, "tok-sign")
    text_hash = _hash_for(client, "tok-sign")
    r = client.post("/api/cosign/tok-sign/sign", json={
        "entity_type": "individual", "legal_name": "Dana Cowriter",
        "typed_signature": "Dana Cowriter", "adult_confirmed": True, "text_sha256": text_hash})
    assert r.status_code == 200, r.text
    req = db.cosign_requests.docs[0]
    assert req["status"] == "signed" and req["pdf_key"].endswith("/req-1.pdf")
    # Track rolled up to complete (Dana is the only co-owner).
    assert db.track_submissions.docs[0]["cosign_status"] == "complete"


def test_sign_name_mismatch_422(client, db):
    db.track_submissions.docs.append(make_track())
    seed_request(db, "tok-mm")
    text_hash = _hash_for(client, "tok-mm")
    r = client.post("/api/cosign/tok-mm/sign", json={
        "entity_type": "individual", "legal_name": "Dana Cowriter",
        "typed_signature": "Someone Else", "adult_confirmed": True, "text_sha256": text_hash})
    assert r.status_code == 422


def test_sign_stale_hash_409(client, db):
    db.track_submissions.docs.append(make_track())
    seed_request(db, "tok-stale")
    r = client.post("/api/cosign/tok-stale/sign", json={
        "entity_type": "individual", "legal_name": "Dana Cowriter",
        "typed_signature": "Dana Cowriter", "adult_confirmed": True, "text_sha256": "a" * 64})
    assert r.status_code == 409
    assert "changed" in r.json()["detail"].lower()


def test_decline_rolls_up(client, db):
    db.track_submissions.docs.append(make_track())
    seed_request(db, "tok-dec")
    r = client.post("/api/cosign/tok-dec/decline", json={"reason": "not mine"})
    assert r.status_code == 200, r.text
    assert db.cosign_requests.docs[0]["status"] == "declined"
    assert db.track_submissions.docs[0]["cosign_status"] == "declined"


def test_status_rolls_up_only_when_all_signed(client, db):
    db.track_submissions.docs.append(make_track())
    seed_request(db, "tok-a", email="a@example.com", id="req-a",
                 interests=[{"side": "writers", "legal_name": "A", "role": "C", "share_bp": 5000}])
    seed_request(db, "tok-b", email="b@example.com", id="req-b",
                 interests=[{"side": "writers", "legal_name": "B", "role": "C", "share_bp": 5000}])
    # Sign the first; one still pending -> track stays pending.
    h = _hash_for(client, "tok-a")
    client.post("/api/cosign/tok-a/sign", json={
        "entity_type": "individual", "legal_name": "A", "typed_signature": "A",
        "adult_confirmed": True, "text_sha256": h})
    assert db.track_submissions.docs[0]["cosign_status"] == "pending"
    # Sign the second -> complete.
    h2 = _hash_for(client, "tok-b")
    client.post("/api/cosign/tok-b/sign", json={
        "entity_type": "individual", "legal_name": "B", "typed_signature": "B",
        "adult_confirmed": True, "text_sha256": h2})
    assert db.track_submissions.docs[0]["cosign_status"] == "complete"


# ---------------------------------------------------------------------------
# C5: uploader endpoints (resend, edit email)
# ---------------------------------------------------------------------------

@pytest.fixture
def as_artist():
    server.app.dependency_overrides[server.require_artist] = lambda: {
        "sub": UID, "metadata": {"role": "artist"}}
    yield
    server.app.dependency_overrides.pop(server.require_artist, None)


def test_resend_rotates_token_old_link_dies(client, db, as_artist):
    db.track_submissions.docs.append(make_track())
    seed_request(db, "tok-r", send_count=1, last_sent_at=None)
    r = client.post(f"/api/vault/tracks/{TRACK_ID}/cosign/req-1/resend")
    assert r.status_code == 200, r.text
    # New hash stored; the old raw token no longer resolves.
    assert db.cosign_requests.docs[0]["token_sha256"] != server._hash_token("tok-r")
    assert client.get("/api/cosign/tok-r").status_code == 404


def test_resend_cooldown_429(client, db, as_artist):
    from datetime import datetime, timezone
    db.track_submissions.docs.append(make_track())
    seed_request(db, "tok-cd", last_sent_at=datetime.now(timezone.utc).isoformat())
    r = client.post(f"/api/vault/tracks/{TRACK_ID}/cosign/req-1/resend")
    assert r.status_code == 429


def test_resend_max_total_429(client, db, as_artist):
    db.track_submissions.docs.append(make_track())
    seed_request(db, "tok-max", send_count=server.COSIGN_MAX_RESENDS + 1, last_sent_at=None)
    r = client.post(f"/api/vault/tracks/{TRACK_ID}/cosign/req-1/resend")
    assert r.status_code == 429


def test_edit_email_updates_request_and_rights(client, db, as_artist):
    db.track_submissions.docs.append(make_track())
    seed_request(db, "tok-e")
    r = client.patch(f"/api/vault/tracks/{TRACK_ID}/cosign/req-1",
                     json={"email": "dana.new@example.com"})
    assert r.status_code == 200, r.text
    assert db.cosign_requests.docs[0]["email"] == "dana.new@example.com"
    rights = db.track_submissions.docs[0]["rights"]
    assert rights["writers"][1]["email"] == "dana.new@example.com"
    assert rights["publishers"][0]["email"] == "dana.new@example.com"


def test_edit_email_duplicate_409(client, db, as_artist):
    db.track_submissions.docs.append(make_track())
    seed_request(db, "tok-1", email="dana@example.com", id="req-1")
    seed_request(db, "tok-2", email="other@example.com", id="req-2")
    r = client.patch(f"/api/vault/tracks/{TRACK_ID}/cosign/req-2",
                     json={"email": "dana@example.com"})
    assert r.status_code == 409


def test_resend_other_artists_track_404(client, db):
    server.app.dependency_overrides[server.require_artist] = lambda: {
        "sub": "someone_else", "metadata": {"role": "artist"}}
    db.track_submissions.docs.append(make_track())
    seed_request(db, "tok-x")
    r = client.post(f"/api/vault/tracks/{TRACK_ID}/cosign/req-1/resend")
    assert r.status_code == 404
    server.app.dependency_overrides.pop(server.require_artist, None)


def test_cosign_v2_renders_without_version_or_placeholders():
    from datetime import datetime, timezone
    import artist_agreement as aa
    values = cosign.build_values(
        now=datetime(2026, 10, 23, tzinfo=timezone.utc),
        entity_type="individual", legal_name="Jane Co", coowner_email="jane@example.com",
        uploader_name="Upload Artist",                      # no artist_agreement_version
        work_title="Night Drive", work_artist="Artist", work_id="w1",
        interests=[{"side": "writers", "legal_name": "Jane Co", "role": "C", "share_bp": 10000}],
    )
    text = cosign.render_text(values, "cosign_v2")
    # SIGNATURE_BLOCK is deliberately left literal for the PDF; no other placeholder remains.
    assert "{{" not in text.replace(aa.SIGNATURE_MARKER, "")
    assert "version" not in text.lower()


def test_cosign_v1_still_renders_agreement_version():
    from datetime import datetime, timezone
    import artist_agreement as aa
    values = cosign.build_values(
        now=datetime(2026, 10, 23, tzinfo=timezone.utc),
        entity_type="individual", legal_name="Jane Co", coowner_email="jane@example.com",
        uploader_name="Upload Artist", artist_agreement_version="v4",
        work_title="Night Drive", work_artist="Artist", work_id="w1",
        interests=[{"side": "writers", "legal_name": "Jane Co", "role": "C", "share_bp": 10000}],
    )
    text = cosign.render_text(values, "cosign_v1")
    assert "{{" not in text.replace(aa.SIGNATURE_MARKER, "")
    assert "version v4" in text                              # "...Agreement, version v4..."


def test_cosign_pdf_has_fingerprint_not_version():
    pypdf = pytest.importorskip("pypdf")
    from io import BytesIO
    from datetime import datetime, timezone
    values = cosign.build_values(
        now=datetime(2026, 10, 23, tzinfo=timezone.utc),
        entity_type="individual", legal_name="Jane Co", coowner_email="jane@example.com",
        uploader_name="Upload Artist",
        work_title="Night Drive", work_artist="Artist", work_id="w1",
        interests=[{"side": "writers", "legal_name": "Jane Co", "role": "C", "share_bp": 10000}],
    )
    text = cosign.render_text(values, "cosign_v2")
    sig = {"request_id": "req-1", "version": "cosign_v2", "work_id": "w1",
           "text_sha256": "b" * 64, "signed_at": "2026-10-23T00:00:00+00:00",
           "typed_signature": "Jane Co", "entity_type": "individual", "legal_name": "Jane Co",
           "signer_name": "", "signer_title": "", "coowner_email": "jane@example.com",
           "ip": "203.0.113.9"}
    body = "\n".join(p.extract_text() for p in pypdf.PdfReader(BytesIO(cosign.render_pdf(text, sig))).pages)
    assert "Document fingerprint" in body
    assert "bbbbbbbbbbbbbbbb" in body
    assert "Version" not in body


def test_cosign_v3_renders_without_version_or_placeholders():
    from datetime import datetime, timezone
    import artist_agreement as aa
    values = cosign.build_values(
        now=datetime(2026, 10, 23, tzinfo=timezone.utc),
        entity_type="individual", legal_name="Jane Co", coowner_email="jane@example.com",
        uploader_name="Upload Artist",
        work_title="Night Drive", work_artist="Artist", work_id="w1",
        interests=[{"side": "writers", "legal_name": "Jane Co", "role": "C", "share_bp": 10000}],
    )
    text = cosign.render_text(values, "cosign_v3")
    assert "{{" not in text.replace(aa.SIGNATURE_MARKER, "")
    assert "version" not in text.lower()
