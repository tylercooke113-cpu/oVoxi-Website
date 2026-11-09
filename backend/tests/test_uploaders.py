"""Brief 28 Part C1/C2: authorization lifecycle and resolve_actor.

Mocks motor with a small in-memory fake (same approach as test_cosign). send_email, the R2
client and the Clerk verified-email lookup are mocked. ARTIST_AGREEMENT_VERSION is set to v6
so supports_authorized_uploaders is true for the signed agreement.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError

import server


def run(coro):
    return asyncio.run(coro)


class FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    async def to_list(self, n=None):
        return [dict(d) for d in self._docs]


class FakeCollection:
    def __init__(self, unique=()):
        self.docs = []
        self._unique = unique

    @staticmethod
    def _match(d, flt):
        for k, v in flt.items():
            dv = d.get(k)
            if isinstance(v, dict):
                if "$in" in v and dv not in v["$in"]:
                    return False
                if "$ne" in v and dv == v["$ne"]:
                    return False
            elif dv != v:
                return False
        return True

    async def insert_one(self, doc):
        for keys in self._unique:
            if all(doc.get(k) is not None for k in keys):
                for e in self.docs:
                    if all(e.get(k) == doc.get(k) for k in keys):
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
                return SimpleNamespace(matched_count=1)
        return SimpleNamespace(matched_count=0)

    async def create_index(self, *a, **k):
        return None


class FakeDB:
    def __init__(self):
        self.upload_authorizations = FakeCollection()
        self.authorization_events = FakeCollection()
        self.artist_agreements = FakeCollection()
        self.track_submissions = FakeCollection()


ARTIST = "user_artist"
UPLOADER = "user_uploader"
ADMIN = "user_admin"
AGREEMENT = {
    "id": "agr1", "user_id": ARTIST, "version": "v6", "signed_at": "2026-10-28T00:00:00+00:00",
    "licensor_party": "Jane Q Smith, of 1 Main St, Austin, TX 78701, USA",
    "licensor_email": "jane@example.com",
    "fields": {"entity_type": "individual", "legal_name": "Jane Q Smith"},
}


@pytest.fixture(autouse=True)
def _v6(monkeypatch):
    monkeypatch.setenv("ARTIST_AGREEMENT_VERSION", "v6")
    monkeypatch.setenv("UPLOAD_AUTH_VERSION", "upload_auth_v1")
    import artist_agreement
    artist_agreement.load_template.cache_clear()


@pytest.fixture
def db(monkeypatch):
    fake = FakeDB()
    fake.artist_agreements.docs.append(dict(AGREEMENT))
    monkeypatch.setattr(server, "db", fake)
    return fake


@pytest.fixture
def sent(monkeypatch):
    m = AsyncMock(return_value={"status": "sent", "id": "e1", "error": None})
    monkeypatch.setattr(server, "send_email", m)
    return m


@pytest.fixture
def client(db, sent, monkeypatch):
    monkeypatch.setattr(server, "r2_client", MagicMock())
    monkeypatch.setattr(server.limiter, "enabled", False)
    yield TestClient(server.app)
    server.app.dependency_overrides.clear()


def as_artist(payload=None):
    server.app.dependency_overrides[server.require_artist] = lambda: payload or {
        "sub": ARTIST, "metadata": {"role": "artist"}}


def as_signed_in(sub, role=None):
    server.app.dependency_overrides[server.verify_clerk_token] = lambda: {
        "sub": sub, "metadata": {"role": role} if role else {}}


def events(db, kind=None):
    return [e for e in db.authorization_events.docs if kind is None or e["event"] == kind]


# ---------------------------------------------------------------------------
# Create (artist signs)
# ---------------------------------------------------------------------------

def _preview(client, kind="person", **over):
    body = {"kind": kind, "uses": ["sync"]}
    if kind == "person":
        body.update({"uploader_name": "Sam Engineer", "uploader_email": "SAM@Example.com",
                     "uploader_role": "Engineer"})
    body.update(over)
    return client.post("/api/vault/uploaders/preview", json=body)


def _create(client, kind="person", **over):
    as_artist()
    pv = _preview(client, kind=kind, **over).json()
    body = {"kind": kind, "uses": ["sync"], "typed_signature": "Jane Q Smith",
            "text_sha256": pv["text_sha256"]}
    if kind == "person":
        body.update({"uploader_name": "Sam Engineer", "uploader_email": "SAM@Example.com",
                     "uploader_role": "Engineer"})
    body.update(over)
    return client.post("/api/vault/uploaders", json=body)


def test_create_person_awaiting_and_invited(client, db, sent):
    r = _create(client)
    assert r.status_code == 201, r.text
    auth = db.upload_authorizations.docs[0]
    assert auth["status"] == "awaiting_uploader"
    assert auth["uploader_email"] == "sam@example.com"            # lowercased
    assert auth["uploader_user_id"] is None
    assert auth["token_sha256"] and auth["token_expires_at"]
    assert {e["event"] for e in events(db)} == {"created", "artist_signed"}
    # Invitation email went to the uploader.
    assert any(c.kwargs["to"] == "sam@example.com" for c in sent.await_args_list)


def test_create_ovoxi_active_with_pdf(client, db, sent):
    r = _create(client, kind="ovoxi", uses=["ai_training", "sync"])
    assert r.status_code == 201, r.text
    auth = db.upload_authorizations.docs[0]
    assert auth["status"] == "active" and auth["kind"] == "ovoxi"
    assert auth["uploader_email"] is None and auth["uploader_role"] == "OVOXI"
    assert auth["pdf_key"] and auth["token_sha256"] is None
    # Signed copy to artist and tyler@ovoxi.net.
    tos = {c.kwargs["to"] for c in sent.await_args_list}
    assert "jane@example.com" in tos and server.SIGNED_COPY_TO in tos


def test_create_requires_v6_agreement(client, db, monkeypatch):
    monkeypatch.setenv("ARTIST_AGREEMENT_VERSION", "v5")
    import artist_agreement
    artist_agreement.load_template.cache_clear()
    as_artist()
    # Preview itself is gated.
    r = client.post("/api/vault/uploaders/preview", json={"kind": "ovoxi", "uses": ["sync"]})
    assert r.status_code == 403


def test_create_artist_name_must_match(client, db):
    as_artist()
    pv = _preview(client).json()
    r = client.post("/api/vault/uploaders", json={
        "kind": "person", "uses": ["sync"], "uploader_name": "Sam Engineer",
        "uploader_email": "sam@example.com", "uploader_role": "Engineer",
        "typed_signature": "Not The Artist", "text_sha256": pv["text_sha256"]})
    assert r.status_code == 422


def test_create_duplicate_ovoxi_409(client, db):
    assert _create(client, kind="ovoxi").status_code == 201
    assert _create(client, kind="ovoxi").status_code == 409


def test_create_duplicate_person_email_409(client, db):
    assert _create(client).status_code == 201
    assert _create(client).status_code == 409


def test_stale_hash_409(client, db):
    as_artist()
    r = client.post("/api/vault/uploaders", json={
        "kind": "person", "uses": ["sync"], "uploader_name": "Sam Engineer",
        "uploader_email": "sam@example.com", "uploader_role": "Engineer",
        "typed_signature": "Jane Q Smith", "text_sha256": "a" * 64})
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# Revoke
# ---------------------------------------------------------------------------

def test_revoke_person(client, db, sent):
    _create(client)
    aid = db.upload_authorizations.docs[0]["id"]
    as_artist()
    r = client.delete(f"/api/vault/uploaders/{aid}")
    assert r.status_code == 200, r.text
    assert db.upload_authorizations.docs[0]["status"] == "revoked"
    assert events(db, "revoked")
    assert any(c.kwargs["to"] == "sam@example.com" for c in sent.await_args_list)


def test_revoke_other_artist_404(client, db):
    _create(client)
    aid = db.upload_authorizations.docs[0]["id"]
    as_artist({"sub": "someone_else", "metadata": {"role": "artist"}})
    assert client.delete(f"/api/vault/uploaders/{aid}").status_code == 404


# ---------------------------------------------------------------------------
# Authorize: get / sign / decline with the verified-email gate
# ---------------------------------------------------------------------------

@pytest.fixture
def verified(monkeypatch):
    m = AsyncMock(return_value={"sam@example.com"})
    monkeypatch.setattr(server, "fetch_clerk_verified_emails", m)
    return m


def _token_for(db):
    # Reproduce the raw token is impossible (only the hash is stored), so seed a known token.
    import secrets
    tok = secrets.token_urlsafe(16)
    db.upload_authorizations.docs[0]["token_sha256"] = server._hash_token(tok)
    return tok


def test_authorize_sign_happy(client, db, sent, verified):
    _create(client)
    tok = _token_for(db)
    as_signed_in(UPLOADER)
    g = client.get(f"/api/authorize/{tok}")
    assert g.status_code == 200, g.text
    sign = client.post(f"/api/authorize/{tok}/sign", json={
        "typed_signature": "Sam Engineer", "adult_confirmed": True,
        "text_sha256": g.json()["text_sha256"]})
    assert sign.status_code == 200, sign.text
    auth = db.upload_authorizations.docs[0]
    assert auth["status"] == "active" and auth["uploader_user_id"] == UPLOADER
    assert auth["pdf_key"] and auth["uploader_signature"]["email"] == "sam@example.com"
    assert events(db, "uploader_signed")
    tos = {c.kwargs["to"] for c in sent.await_args_list}
    assert {"jane@example.com", "sam@example.com", server.SIGNED_COPY_TO} <= tos


def test_authorize_wrong_email_403(client, db, monkeypatch):
    _create(client)
    tok = _token_for(db)
    monkeypatch.setattr(server, "fetch_clerk_verified_emails",
                        AsyncMock(return_value={"other@example.com"}))
    as_signed_in(UPLOADER)
    r = client.get(f"/api/authorize/{tok}")
    assert r.status_code == 403
    assert "sam@example.com" in r.json()["detail"]


def test_authorize_expired_marks_expired(client, db, verified):
    _create(client)
    tok = _token_for(db)
    db.upload_authorizations.docs[0]["token_expires_at"] = "2000-01-01T00:00:00+00:00"
    as_signed_in(UPLOADER)
    r = client.get(f"/api/authorize/{tok}")
    assert r.status_code == 404
    assert db.upload_authorizations.docs[0]["status"] == "expired"
    assert events(db, "expired")


def test_authorize_decline(client, db, sent, verified):
    _create(client)
    tok = _token_for(db)
    as_signed_in(UPLOADER)
    r = client.post(f"/api/authorize/{tok}/decline", json={"reason": "not me"})
    assert r.status_code == 200, r.text
    assert db.upload_authorizations.docs[0]["status"] == "declined"
    assert events(db, "declined")


# ---------------------------------------------------------------------------
# uploader/artists and end
# ---------------------------------------------------------------------------

def test_uploader_artists_person_and_ovoxi(client, db):
    # One active person auth for UPLOADER, one active OVOXI auth.
    db.upload_authorizations.docs.append({
        "id": "a-person", "artist_user_id": ARTIST, "artist_name": "Jane", "kind": "person",
        "uploader_user_id": UPLOADER, "uses": ["sync"], "status": "active"})
    db.upload_authorizations.docs.append({
        "id": "a-ovoxi", "artist_user_id": "artist2", "artist_name": "Max", "kind": "ovoxi",
        "uploader_user_id": None, "uses": ["ai_training"], "status": "active"})
    as_signed_in(UPLOADER)
    r = client.get("/api/uploader/artists")
    assert {a["artist_user_id"] for a in r.json()["artists"]} == {ARTIST}   # non-admin: person only
    as_signed_in(ADMIN, role="admin")
    r = client.get("/api/uploader/artists")
    ids = {a["artist_user_id"] for a in r.json()["artists"]}
    assert ids == {"artist2"}            # admin sees every active OVOXI (plus its own person auths, none here)


def test_uploader_artists_returns_current_licensor_name(client, db):
    """D3: the upload form locks rights.self_legal_name to this, so it must be the licensor on
    the artist's CURRENT agreement (what upload/presign checks), falling back to the stored name."""
    db.upload_authorizations.docs.append({
        "id": "a-person", "artist_user_id": ARTIST, "artist_name": "Old Name", "kind": "person",
        "uploader_user_id": UPLOADER, "uses": ["sync"], "status": "active"})
    db.upload_authorizations.docs.append({
        "id": "a-person2", "artist_user_id": "artist_no_v6", "artist_name": "Max Stored", "kind": "person",
        "uploader_user_id": UPLOADER, "uses": ["ai_training"], "status": "active"})
    as_signed_in(UPLOADER)
    r = client.get("/api/uploader/artists")
    assert r.status_code == 200, r.text
    by_id = {a["artist_user_id"]: a for a in r.json()["artists"]}
    assert by_id[ARTIST]["licensor_name"] == "Jane Q Smith"          # from the current agreement
    assert by_id["artist_no_v6"]["licensor_name"] == "Max Stored"   # no current agreement: stored name
    # Nothing sensitive rides along.
    for a in by_id.values():
        assert set(a) == {"artist_user_id", "artist_name", "authorization_id", "uses", "is_ovoxi", "licensor_name"}


def test_uploader_end_by_uploader(client, db):
    db.upload_authorizations.docs.append({
        "id": "a1", "artist_user_id": ARTIST, "artist_name": "Jane", "artist_email": "jane@example.com",
        "kind": "person", "uploader_user_id": UPLOADER, "uploader_name": "Sam", "uses": ["sync"],
        "status": "active"})
    as_signed_in("someone_else")
    assert client.post("/api/uploader/authorizations/a1/end").status_code == 403
    as_signed_in(UPLOADER)
    r = client.post("/api/uploader/authorizations/a1/end")
    assert r.status_code == 200, r.text
    assert db.upload_authorizations.docs[0]["status"] == "ended_by_uploader"
    assert events(db, "ended")


def test_ovoxi_end_requires_admin(client, db):
    db.upload_authorizations.docs.append({
        "id": "a2", "artist_user_id": ARTIST, "artist_name": "Jane", "artist_email": "jane@example.com",
        "kind": "ovoxi", "uploader_user_id": None, "uploader_name": None, "uses": ["sync"],
        "status": "active"})
    as_signed_in(UPLOADER)                        # non-admin cannot end an OVOXI authorization
    assert client.post("/api/uploader/authorizations/a2/end").status_code == 403
    as_signed_in(ADMIN, role="admin")
    assert client.post("/api/uploader/authorizations/a2/end").status_code == 200


# ---------------------------------------------------------------------------
# resolve_actor
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Guard wired end-to-end (through the included router)
# ---------------------------------------------------------------------------

def test_guard_blocks_header_on_non_allowlisted_route(client, db):
    # wallet/me is not in the allowlist: the header is refused before the route runs.
    server.app.dependency_overrides[server.verify_clerk_token] = lambda: {
        "sub": ARTIST, "metadata": {"role": "artist"}}
    r = client.get("/api/wallet/me", headers={"X-Acting-For": ARTIST})
    assert r.status_code == 403
    assert "on behalf of an artist" in r.json()["detail"]


def _req(acting_for=None):
    return SimpleNamespace(headers={"x-acting-for": acting_for} if acting_for else {})


def test_resolve_actor_no_header(db):
    ctx = run(server.resolve_actor(_req(), {"sub": UPLOADER, "metadata": {}}))
    assert ctx["acting"] is False and ctx["principal_id"] == UPLOADER


def test_resolve_actor_person(db):
    db.upload_authorizations.docs.append({
        "id": "a1", "artist_user_id": ARTIST, "uploader_user_id": UPLOADER, "kind": "person",
        "status": "active", "uses": ["sync"]})
    ctx = run(server.resolve_actor(_req(ARTIST), {"sub": UPLOADER, "metadata": {}}))
    assert ctx["acting"] and ctx["principal_id"] == ARTIST and ctx["is_ovoxi"] is False
    assert ctx["uses"] == ["sync"] and ctx["acting_admin_user_id"] is None


def test_resolve_actor_unauthorized_403(db):
    with pytest.raises(HTTPException) as e:
        run(server.resolve_actor(_req(ARTIST), {"sub": UPLOADER, "metadata": {}}))
    assert e.value.status_code == 403


def test_resolve_actor_ovoxi_admin_only(db):
    db.upload_authorizations.docs.append({
        "id": "a2", "artist_user_id": ARTIST, "uploader_user_id": None, "kind": "ovoxi",
        "status": "active", "uses": ["sync"]})
    # Non-admin cannot use the OVOXI authorization.
    with pytest.raises(HTTPException) as e:
        run(server.resolve_actor(_req(ARTIST), {"sub": UPLOADER, "metadata": {}}))
    assert e.value.status_code == 403
    # Admin can, and it records the acting admin.
    ctx = run(server.resolve_actor(_req(ARTIST), {"sub": ADMIN, "metadata": {"role": "admin"}}))
    assert ctx["acting"] and ctx["is_ovoxi"] and ctx["acting_admin_user_id"] == ADMIN
