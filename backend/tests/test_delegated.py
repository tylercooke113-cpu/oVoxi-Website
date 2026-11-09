"""Brief 28 C-2: delegated uploads, acting-for vault edits, not-intended, admin takedown.

Includes the required wiring test: for each of the 10 allowlisted routes, (a) an acting
caller with no authorization gets 403, and (b) an authorized uploader's request is scoped
to the ARTIST's track, never the caller's own.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError

import server


def run(coro):
    return asyncio.run(coro)


class FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, key, direction=-1):
        self._docs = sorted(self._docs, key=lambda d: d.get(key) or "", reverse=direction < 0)
        return self

    async def to_list(self, n=None):
        return [dict(d) for d in self._docs]


class FakeCollection:
    def __init__(self):
        self.docs = []

    @staticmethod
    def _match(d, flt):
        for k, v in flt.items():
            dv = d.get(k)
            if isinstance(v, dict):
                if "$ne" in v and dv == v["$ne"]:
                    return False
                if "$in" in v and dv not in v["$in"]:
                    return False
                if "$gte" in v and not (dv is not None and dv >= v["$gte"]):
                    return False
                if "$gt" in v and not (dv is not None and dv > v["$gt"]):
                    return False
                if "$lte" in v and not (dv is not None and dv <= v["$lte"]):
                    return False
            elif dv != v:
                return False
        return True

    async def insert_one(self, doc):
        self.docs.append(dict(doc))
        return SimpleNamespace(inserted_id="x")

    async def insert_many(self, docs):
        for d in docs:
            self.docs.append(dict(d))
        return SimpleNamespace(inserted_ids=["x"] * len(docs))

    async def find_one(self, flt, proj=None):
        for d in self.docs:
            if self._match(d, flt):
                return dict(d)
        return None

    def find(self, flt, proj=None):
        return FakeCursor([d for d in self.docs if self._match(d, flt)])

    async def update_one(self, flt, update):
        def _step(cur, p):
            return cur[int(p)] if isinstance(cur, list) else cur.setdefault(p, {})

        for d in self.docs:
            if self._match(d, flt):
                for k, val in update.get("$set", {}).items():
                    if "." in k:
                        parts = k.split(".")
                        cur = d
                        for p in parts[:-1]:
                            cur = _step(cur, p)
                        if isinstance(cur, list):
                            cur[int(parts[-1])] = val
                        else:
                            cur[parts[-1]] = val
                    else:
                        d[k] = val
                return SimpleNamespace(matched_count=1)
        return SimpleNamespace(matched_count=0)

    async def count_documents(self, flt):
        return sum(1 for d in self.docs if self._match(d, flt))

    async def distinct(self, field, flt=None):
        return list({d.get(field) for d in self.docs if self._match(d, flt or {})})

    async def create_index(self, *a, **k):
        return None


class FakeDB:
    def __init__(self):
        for name in ("upload_authorizations", "authorization_events", "track_submissions",
                     "artist_agreements", "cosign_requests", "consent_events", "upload_digests",
                     "admin_actions"):
            setattr(self, name, FakeCollection())


ARTIST, UPLOADER, ADMIN = "user_artist", "user_uploader", "user_admin"
AGREEMENT = {"id": "agr1", "user_id": ARTIST, "version": "v6", "signed_at": "2026-10-28T00:00:00+00:00",
             "licensor_party": "Jane Q Smith, of 1 Main St", "licensor_email": "jane@example.com",
             "fields": {"entity_type": "individual", "legal_name": "Jane Q Smith"}}


def active_person_auth():
    return {"id": "auth-p", "artist_user_id": ARTIST, "artist_name": "Jane", "kind": "person",
            "uploader_user_id": UPLOADER, "uploader_name": "Sam Engineer", "uploader_email": "sam@example.com",
            "uploader_role": "Engineer", "uses": ["sync", "ai_training"], "status": "active"}


def artist_track(tid="t-artist", owner=ARTIST):
    return {"id": tid, "clerk_user_id": owner, "artist_name": "Jane", "track_name": "Song",
            "genre": "R&B", "status": "completed", "consent": {"ai_training": False, "sync": False},
            "rights": {"owns_everything": True, "writers": []},
            "intake": {"samples": "original", "loops": [{"creator_email": "l@example.com",
                                                         "loop_name": "Loop", "license_key": None}]},
            "authorization_id": None}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("ARTIST_AGREEMENT_VERSION", "v6")
    monkeypatch.setenv("ARTIST_AGREEMENT_ENFORCED", "true")
    monkeypatch.setenv("ARTIST_APPROVAL_REQUIRED", "false")   # avoid Clerk role lookups
    import artist_agreement
    artist_agreement.load_template.cache_clear()


@pytest.fixture
def db(monkeypatch):
    fake = FakeDB()
    fake.artist_agreements.docs.append(dict(AGREEMENT))
    monkeypatch.setattr(server, "db", fake)
    return fake


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setattr(server, "send_email", AsyncMock(return_value={"status": "sent", "id": "e", "error": None}))
    monkeypatch.setattr(server, "r2_client", MagicMock())
    monkeypatch.setattr(server.limiter, "enabled", False)
    monkeypatch.setattr(server, "_run_clearance", AsyncMock())
    monkeypatch.setattr(server, "vault_track_view", lambda doc: {})
    monkeypatch.setattr(server, "is_legacy", lambda doc: False)
    yield TestClient(server.app)
    server.app.dependency_overrides.clear()


def caller(sub=UPLOADER, role="artist"):
    payload = {"sub": sub, "metadata": {"role": role} if role else {}}
    server.app.dependency_overrides[server.require_artist] = lambda: payload
    server.app.dependency_overrides[server.verify_clerk_token] = lambda: payload


HDR = {"X-Acting-For": ARTIST}
PRESIGN_BODY = {
    "artist_name": "Jane", "track_name": "New Song", "genre": "R&B",
    "filename": "t.wav", "file_size": 1024, "consent_ai_training": True, "consent_sync": False,
    "moods": ["Chill"], "vocals": "vocal", "bpm": 120.0, "key": "C major",
    "rights": {"owns_everything": True, "self_legal_name": "Jane Q Smith", "attested": True},
    "declarations": {"samples": "original", "samples_attested": True, "ai_tools": "none", "ai_tools_attested": True},
}
DECL_BODY = {"samples": "original", "samples_attested": True, "ai_tools": "none", "ai_tools_attested": True}

# (method, path, body) for the 10 allowlisted routes. {tid}/{rid} filled per test.
ROUTES = [
    ("POST", "/api/upload/presign", PRESIGN_BODY),
    ("GET", "/api/vault/tracks", None),
    ("PATCH", "/api/vault/tracks/{tid}/metadata", {"bpm": 120.0}),
    ("POST", "/api/vault/tracks/{tid}/declarations", DECL_BODY),
    ("POST", "/api/vault/tracks/{tid}/loops/0/license/presign",
     {"filename": "l.pdf", "content_type": "application/pdf", "file_size": 1000}),
    ("POST", "/api/vault/tracks/{tid}/loops/0/license/complete", None),
    ("POST", "/api/vault/tracks/{tid}/consent", {"scope": "ai_training", "action": "grant"}),
    ("POST", "/api/vault/tracks/{tid}/cosign/req1/resend", None),
    ("PATCH", "/api/vault/tracks/{tid}/cosign/req1", {"email": "new@example.com"}),
]


def _call(client, method, path, body):
    fn = getattr(client, method.lower())
    return fn(path, json=body, headers=HDR) if body is not None else fn(path, headers=HDR)


# ---------------------------------------------------------------------------
# Wiring (a): no authorization + X-Acting-For -> 403, on every allowlisted route
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("method,path,body", ROUTES)
def test_wiring_unauthorized_acting_403(client, db, method, path, body):
    caller()                       # no authorization seeded
    r = _call(client, method, path.format(tid="t-artist"), body)
    assert r.status_code == 403, f"{method} {path}: {r.status_code} {r.text}"


def test_wiring_complete_unauthorized_403_and_deletes(client, db):
    # complete re-checks the submission's authorization; a revoked/absent one deletes the file.
    db.track_submissions.docs.append({
        "id": "sub1", "clerk_user_id": ARTIST, "status": "pending", "original_r2_path": "k",
        "authorization_id": "auth-gone"})
    caller()
    r = client.post("/api/upload/complete", json={"submission_id": "sub1"}, headers=HDR)
    assert r.status_code == 403
    assert server.r2_client.delete_object.called
    assert db.track_submissions.docs[0]["status"] == "failed"


# ---------------------------------------------------------------------------
# Wiring (b): an authorized uploader acts on the ARTIST's track, not the caller's own
# ---------------------------------------------------------------------------

TRACK_ROUTES = [r for r in ROUTES if "{tid}" in r[1]]


@pytest.mark.parametrize("method,path,body", TRACK_ROUTES)
def test_wiring_authorized_reads_artist_track(client, db, method, path, body):
    db.upload_authorizations.docs.append(active_person_auth())
    db.track_submissions.docs.append(artist_track("t-artist", owner=ARTIST))
    db.cosign_requests.docs.append({"id": "req1", "track_id": "t-artist", "email": "dana@example.com",
                                    "status": "pending", "interests": [], "send_count": 1,
                                    "last_sent_at": None})
    caller()
    r = _call(client, method, path.format(tid="t-artist"), body)
    assert r.status_code not in (403, 404), f"{method} {path}: {r.status_code} {r.text}"


@pytest.mark.parametrize("method,path,body", TRACK_ROUTES)
def test_wiring_acting_cannot_touch_callers_own_track(client, db, method, path, body):
    # A track owned by the CALLER is invisible when acting for the artist: scoped to artist.
    db.upload_authorizations.docs.append(active_person_auth())
    db.track_submissions.docs.append(artist_track("t-caller", owner=UPLOADER))
    caller()
    r = _call(client, method, path.format(tid="t-caller"), body)
    assert r.status_code == 404, f"{method} {path}: {r.status_code} {r.text}"


# ---------------------------------------------------------------------------
# C3 delegated upload behavior
# ---------------------------------------------------------------------------

def test_delegated_presign_owned_by_artist(client, db, monkeypatch):
    monkeypatch.setattr(server, "build_rights", lambda *a, **k: {"owns_everything": True, "writers": []})
    db.upload_authorizations.docs.append(active_person_auth())
    caller()
    r = client.post("/api/upload/presign", json=PRESIGN_BODY, headers=HDR)   # ai_training only
    assert r.status_code == 200, r.text
    doc = db.track_submissions.docs[-1]
    assert doc["clerk_user_id"] == ARTIST          # owned by the artist, never the uploader
    assert doc["uploaded_by_user_id"] == UPLOADER
    assert doc["uploaded_by_name"] == "Sam Engineer"
    assert doc["authorization_id"] == "auth-p"
    assert doc["acting_admin_user_id"] is None
    assert any(e["event"] == "upload" for e in db.authorization_events.docs)


def test_delegated_presign_use_outside_authorization_403(client, db):
    auth = {**active_person_auth(), "uses": ["sync"]}     # sync only
    db.upload_authorizations.docs.append(auth)
    caller()
    r = client.post("/api/upload/presign",
                    json={**PRESIGN_BODY, "consent_ai_training": True, "consent_sync": False}, headers=HDR)
    assert r.status_code == 403 and "AI training" in r.json()["detail"]


def test_delegated_presign_exclusive_403(client, db):
    db.upload_authorizations.docs.append(active_person_auth())
    caller()
    r = client.post("/api/upload/presign",
                    json={**PRESIGN_BODY, "consent_exclusive": True}, headers=HDR)
    assert r.status_code == 403 and "exclusive" in r.json()["detail"].lower()


def test_own_upload_unaffected_without_header(client, db, monkeypatch):
    monkeypatch.setattr(server, "build_rights", lambda *a, **k: {"owns_everything": True, "writers": []})
    caller(sub=ARTIST)
    r = client.post("/api/upload/presign", json=PRESIGN_BODY)    # no header
    assert r.status_code == 200, r.text
    doc = db.track_submissions.docs[-1]
    assert doc["clerk_user_id"] == ARTIST
    assert doc.get("uploaded_by_user_id") is None and doc.get("authorization_id") is None


# ---------------------------------------------------------------------------
# C4 consent: acting may only add an authorized use
# ---------------------------------------------------------------------------

def test_acting_consent_grant_logs_use_added(client, db):
    db.upload_authorizations.docs.append(active_person_auth())
    db.track_submissions.docs.append(artist_track("t1"))
    caller()
    r = client.post("/api/vault/tracks/t1/consent",
                    json={"scope": "ai_training", "action": "grant"}, headers=HDR)
    assert r.status_code == 200, r.text
    assert any(e["event"] == "use_added" for e in db.authorization_events.docs)
    ev = db.consent_events.docs[-1]
    assert ev["user_id"] == ARTIST and ev["actor_user_id"] == UPLOADER and ev["authorization_id"] == "auth-p"


def test_acting_consent_withdraw_403(client, db):
    db.upload_authorizations.docs.append(active_person_auth())
    db.track_submissions.docs.append({**artist_track("t1"), "consent": {"ai_training": True, "sync": False}})
    caller()
    r = client.post("/api/vault/tracks/t1/consent",
                    json={"scope": "ai_training", "action": "withdraw"}, headers=HDR)
    assert r.status_code == 403 and r.json()["detail"] == "Only the artist can do this."


def test_acting_exclusive_403(client, db):
    db.upload_authorizations.docs.append(active_person_auth())
    db.track_submissions.docs.append(artist_track("t1"))
    caller()
    r = client.post("/api/vault/tracks/t1/consent",
                    json={"scope": "exclusive", "action": "grant"}, headers=HDR)
    assert r.status_code == 403 and r.json()["detail"] == "Only the artist can do this."


# ---------------------------------------------------------------------------
# C5 not-intended removal (artist only, delegated tracks, 30 days)
# ---------------------------------------------------------------------------

def test_not_intended_removes_and_delists(client, db):
    from datetime import datetime, timezone
    db.track_submissions.docs.append({
        **artist_track("t1"), "authorization_id": "auth-p",
        "consent": {"ai_training": True, "sync": True, "exclusive": False},
        "upload_date": datetime.now(timezone.utc).isoformat()})
    caller(sub=ARTIST)
    r = client.post("/api/vault/tracks/t1/not-intended")
    assert r.status_code == 200, r.text
    doc = db.track_submissions.docs[0]
    assert doc["consent"]["ai_training"] is False and doc["consent"]["sync"] is False
    assert doc.get("not_intended_at") and "sync_delisted_by_admin" not in doc   # own flag, not the hold
    wd = [e for e in db.consent_events.docs if e["action"] == "withdraw"]
    assert wd and all(e["reason"] == "not_intended" for e in wd)


def test_not_intended_rejects_non_delegated(client, db):
    db.track_submissions.docs.append({**artist_track("t1"), "authorization_id": None})
    caller(sub=ARTIST)
    r = client.post("/api/vault/tracks/t1/not-intended")
    assert r.status_code == 409


def test_not_intended_rejects_after_30_days(client, db):
    from datetime import datetime, timezone, timedelta
    db.track_submissions.docs.append({
        **artist_track("t1"), "authorization_id": "auth-p",
        "upload_date": (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()})
    caller(sub=ARTIST)
    assert client.post("/api/vault/tracks/t1/not-intended").status_code == 409


def test_vault_view_uploaded_by_and_not_intended_window():
    """D5: the Vault shows who uploaded a delegated song, and until when the artist can
    remove it as not intended. Own uploads and already-removed songs get neither."""
    from sync_vault import vault_track_view
    base = {**artist_track("t1"), "upload_date": "2026-10-29T10:00:00+00:00"}
    own = vault_track_view(base)
    assert own["uploaded_by"] is None and own["not_intended_until"] is None
    delegated = vault_track_view({**base, "authorization_id": "auth-p", "uploaded_by_name": "Sam Ortiz"})
    assert delegated["uploaded_by"] == {"name": "Sam Ortiz"}
    assert delegated["not_intended_until"] == "2026-11-28T10:00:00+00:00"
    removed = vault_track_view({**base, "authorization_id": "auth-p", "uploaded_by_name": "Sam Ortiz",
                                "not_intended_at": "2026-10-30T00:00:00+00:00"})
    assert removed["not_intended_until"] is None and removed["not_intended_at"] == "2026-10-30T00:00:00+00:00"


def test_vault_tracks_carries_uploaded_by(client, db, monkeypatch):
    from datetime import datetime, timezone
    import sync_vault
    monkeypatch.setattr(server, "vault_track_view", sync_vault.vault_track_view)   # the real view
    db.track_submissions.docs.append({
        **artist_track("t1"), "authorization_id": "auth-p", "uploaded_by_name": "Sam Ortiz",
        "upload_date": datetime.now(timezone.utc).isoformat()})
    caller(sub=ARTIST)
    r = client.get("/api/vault/tracks")
    assert r.status_code == 200, r.text
    row = r.json()[0]
    assert row["uploaded_by"] == {"name": "Sam Ortiz"} and row["not_intended_until"]


def test_acting_vault_tracks_real_view_has_no_sensitive_fields(client, db, monkeypatch):
    """Fix 5, against the REAL vault_track_view (the fixture stubs it out for other tests):
    acting /vault/tracks carries no earnings, wallet, payout, statement or price fields."""
    import sync_vault
    monkeypatch.setattr(server, "vault_track_view", sync_vault.vault_track_view)
    db.upload_authorizations.docs.append(active_person_auth())
    db.track_submissions.docs.append({**artist_track("t1"), "authorization_id": "auth-p",
                                      "uploaded_by_name": "Sam", "upload_date": "2026-10-29T10:00:00+00:00"})
    caller()
    r = client.get("/api/vault/tracks", headers=HDR)
    assert r.status_code == 200, r.text
    assert r.json() and "consent" in r.json()[0]          # proves the real view ran
    blob = str(r.json()).lower()
    for key in _FORBIDDEN_VAULT_KEYS:
        assert key not in blob, f"{key} leaked into the acting vault response"


# ---------------------------------------------------------------------------
# C6 admin takedown
# ---------------------------------------------------------------------------

def test_admin_takedown_ai_withdraws_and_logs(client, db):
    db.track_submissions.docs.append({**artist_track("t1"),
                                      "consent": {"ai_training": True, "sync": True}})
    caller(sub=ADMIN, role="admin")
    r = client.post("/api/admin/tracks/t1/takedown",
                    json={"uses": ["ai_training"], "reason": "rights_problem", "note": "dmca"})
    assert r.status_code == 200, r.text
    doc = db.track_submissions.docs[0]
    assert doc["consent"]["ai_training"] is False and doc["consent"]["sync"] is True  # sync untouched
    wd = [e for e in db.consent_events.docs if e["action"] == "withdraw"]
    assert wd and wd[-1]["reason"] == "admin_takedown_rights" and wd[-1]["acting_admin_user_id"] == ADMIN
    assert any(a["action"] == "takedown" for a in db.admin_actions.docs)


def test_admin_takedown_sync_clears_consent(client, db):
    db.track_submissions.docs.append({**artist_track("t1"),
                                      "consent": {"ai_training": False, "sync": True}})
    caller(sub=ADMIN, role="admin")
    r = client.post("/api/admin/tracks/t1/takedown",
                    json={"uses": ["sync"], "reason": "artist_request"})
    assert r.status_code == 200, r.text
    doc = db.track_submissions.docs[0]
    assert doc["consent"]["sync"] is False          # a real Removal, not the delist hold
    assert "sync_delisted_by_admin" not in doc
    wd = [e for e in db.consent_events.docs if e["action"] == "withdraw"]
    assert wd and wd[-1]["reason"] == "admin_takedown_artist_request"


def test_admin_takedown_requires_admin(client, db):
    db.track_submissions.docs.append(artist_track("t1"))
    caller(sub=UPLOADER, role="artist")
    r = client.post("/api/admin/tracks/t1/takedown",
                    json={"uses": ["sync"], "reason": "artist_request"})
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Acting /vault/tracks exposes no earnings/wallet/payout/statement/price fields
# ---------------------------------------------------------------------------

_FORBIDDEN_VAULT_KEYS = ("earnings", "wallet", "payout", "statement", "price", "amount_cents",
                         "revenue", "net_cents", "exclusive_price")


def test_acting_vault_tracks_has_no_sensitive_fields(client, db):
    db.upload_authorizations.docs.append(active_person_auth())
    db.track_submissions.docs.append(artist_track("t1"))
    caller()
    r = client.get("/api/vault/tracks", headers=HDR)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert rows, "expected the artist's catalog"
    blob = str(rows).lower()
    for key in _FORBIDDEN_VAULT_KEYS:
        assert key not in blob, f"{key} leaked into the acting vault response"


# ---------------------------------------------------------------------------
# C7 digest: per-artist cutoff, idempotent per ET day, rolls forward
# ---------------------------------------------------------------------------

def test_digest_covers_since_last_cutoff(client, db, monkeypatch):
    sends = []
    monkeypatch.setattr(server, "fetch_clerk_user",
                        AsyncMock(return_value={"email": "jane@example.com"}))
    monkeypatch.setattr(server, "send_email",
                        AsyncMock(side_effect=lambda **k: sends.append(k) or {"status": "sent"}))
    db.track_submissions.docs.append({
        "id": "d1", "clerk_user_id": ARTIST, "authorization_id": "auth-p",
        "track_name": "One", "uploaded_by_name": "Sam", "consent": {"sync": True},
        "upload_date": "2026-10-28T10:00:00+00:00"})

    # First digest: no prior cutoff -> covers d1, stamps a cutoff.
    run(server._maybe_send_digest(ARTIST, "2026-10-28", "2026-10-28T23:05:00+00:00"))
    assert len(sends) == 1 and len(db.upload_digests.docs) == 1
    assert db.upload_digests.docs[0]["cutoff_at"] == "2026-10-28T23:05:00+00:00"

    # Same ET day again -> idempotent, no second send.
    run(server._maybe_send_digest(ARTIST, "2026-10-28", "2026-10-28T23:20:00+00:00"))
    assert len(sends) == 1

    # A later upload rolls into the NEXT day's digest (since the stored cutoff).
    db.track_submissions.docs.append({
        "id": "d2", "clerk_user_id": ARTIST, "authorization_id": "auth-p",
        "track_name": "Two", "uploaded_by_name": "Sam", "consent": {"sync": True},
        "upload_date": "2026-10-29T09:00:00+00:00"})
    run(server._maybe_send_digest(ARTIST, "2026-10-29", "2026-10-29T23:05:00+00:00"))
    assert len(sends) == 2
    # Only the new song is in the second digest.
    assert "Two" in sends[1]["text"] and "One" not in sends[1]["text"]


# ---------------------------------------------------------------------------
# /vault/tracks projection must carry every field vault_track_view reads
# ---------------------------------------------------------------------------

def test_vault_tracks_projection_feeds_the_real_view(client, db, monkeypatch):
    """MongoDB returns only the projected fields. The fake DB ignores projections, so this
    test applies it, then checks /vault/tracks equals vault_track_view on the FULL document.
    A field the view reads but the query does not fetch shows up here as a mismatch."""
    import sync_vault
    monkeypatch.setattr(server, "vault_track_view", sync_vault.vault_track_view)
    full = {
        **artist_track("t1"), "upload_date": "2026-10-29T10:00:00+00:00",
        "consent": {"ai_training": True, "sync": True, "exclusive": True},
        "metadata": {"bpm": 120, "key": "C major", "moods": ["Chill"]},
        "sync_status": "cleared", "ai_status": "cleared", "on_sync_profile": True,
        "checks": {"loops": {"result": "fail", "reason": "loop_license_missing"}},
        "intake": {"samples": "royalty_free_loop", "ai_tools": "none",
                   "loops": [{"creator_name": "J", "loop_name": "Keys", "source": "Splice", "license_key": "k"}]},
        "loop_licenses_reviewed": {"result": "approved"},
        "sync_delisted_by_admin": True, "exclusive_sold": {"sync": True},
        "cosign_required": True, "cosign_status": "pending",
        "authorization_id": "auth-p", "uploaded_by_name": "Sam", "not_intended_at": None,
    }
    db.track_submissions.docs.append(full)
    real_find = db.track_submissions.find

    def projected_find(flt, proj=None):
        cur = real_find(flt, proj)
        if proj and any(v for v in proj.values()):
            keep = {k for k, v in proj.items() if v}
            cur._docs = [{k: v for k, v in d.items() if k in keep} for d in cur._docs]
        return cur
    monkeypatch.setattr(db.track_submissions, "find", projected_find)

    caller(sub=ARTIST)
    r = client.get("/api/vault/tracks")
    assert r.status_code == 200, r.text
    row = r.json()[0]
    expected = sync_vault.vault_track_view(full)
    got = {k: row.get(k) for k in expected}
    assert got == expected
