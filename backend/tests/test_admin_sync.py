"""
PRD-03 Phase 4b: admin delist / relist, hide / unhide, audit log, and that an
admin delist survives clearance and artist consent changes.
"""
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import server
from test_public_pages import QueryCollection, listed_track, profile, TID, OWNER

ADMIN = {"sub": "user_admin", "metadata": {"role": "admin"}}


@pytest.fixture
def env(monkeypatch):
    db = MagicMock()
    db.track_submissions = QueryCollection([listed_track(fingerprint_result="CLEARED",
        rights={"attested_at": "t", "writers": [{"share_bp": 10000}], "publishers": [{"share_bp": 10000}],
                "master_owners": [{"share_bp": 10000}]},
        intake={"samples": "original", "samples_attested_at": "t", "content_id": "no",
                "pro_not_affiliated": True},
        stem_paths={n: "x" for n in ("vocals", "instrumental", "drums", "bass", "other")})])
    db.sync_profiles = QueryCollection([profile()])
    db.admin_actions = QueryCollection()
    db.consent_events = QueryCollection()
    monkeypatch.setattr(server, "db", db)
    monkeypatch.setattr(server.limiter, "enabled", False)
    server.app.dependency_overrides[server.require_admin] = lambda: ADMIN
    server.app.dependency_overrides[server.require_artist] = lambda: {"sub": OWNER, "metadata": {"role": "artist"}}
    yield TestClient(server.app), db
    server.app.dependency_overrides.clear()


def test_delist_removes_and_logs(env):
    client, db = env
    resp = client.post(f"/api/admin/sync/tracks/{TID}/delist", json={"delisted": True, "reason": "complaint"})
    assert resp.status_code == 200, resp.text
    d = db.track_submissions.docs[0]
    assert d["sync_delisted_by_admin"] is True and d["on_sync_profile"] is False and d["sync_delisted_at"]
    log = db.admin_actions.inserted[0]
    assert log["action"] == "delist" and log["target"] == TID and log["admin_id"] == "user_admin"
    assert log["reason"] == "complaint"


def test_delist_survives_clearance_and_artist_consent_changes(env):
    client, db = env
    client.post(f"/api/admin/sync/tracks/{TID}/delist", json={"delisted": True})
    import asyncio
    asyncio.run(server._run_clearance(TID))
    assert db.track_submissions.docs[0]["on_sync_profile"] is False
    intake = {"samples": "original", "samples_attested": True, "distributor": "DistroKid",
              "content_id": "no", "pro_not_affiliated": True}
    client.post(f"/api/vault/tracks/{TID}/consent", json={"scope": "sync", "action": "withdraw"})
    client.post(f"/api/vault/tracks/{TID}/consent", json={"scope": "sync", "action": "grant", "sync_intake": intake})
    d = db.track_submissions.docs[0]
    assert d["consent"]["sync"] is True and d["on_sync_profile"] is False
    assert d["sync_delisted_by_admin"] is True


def test_relist_runs_clearance_and_relists(env):
    client, db = env
    client.post(f"/api/admin/sync/tracks/{TID}/delist", json={"delisted": True})
    resp = client.post(f"/api/admin/sync/tracks/{TID}/delist", json={"delisted": False})
    assert resp.status_code == 200, resp.text
    d = db.track_submissions.docs[0]
    assert d["sync_delisted_by_admin"] is False and d["on_sync_profile"] is True
    assert [a["action"] for a in db.admin_actions.inserted] == ["delist", "relist"]


def test_vault_shows_delisted_by_admin(env):
    from sync_vault import vault_track_view
    client, db = env
    client.post(f"/api/admin/sync/tracks/{TID}/delist", json={"delisted": True})
    assert vault_track_view(db.track_submissions.docs[0])["delisted_by_admin"] is True


def test_hide_and_unhide_profile(env):
    client, db = env
    assert client.post("/api/admin/sync/profiles/tyler-example/hide", json={"hidden": True}).status_code == 200
    assert db.sync_profiles.docs[0]["hidden_by_admin"] is True
    client.post("/api/admin/sync/profiles/tyler-example/hide", json={"hidden": False})
    assert db.sync_profiles.docs[0]["hidden_by_admin"] is False
    assert [a["action"] for a in db.admin_actions.inserted] == ["hide_profile", "unhide_profile"]


def test_admin_profile_list_is_minimal(env):
    client, db = env
    rows = client.get("/api/admin/sync/profiles").json()
    assert rows[0]["slug"] == "tyler-example"
    assert "user_id" not in rows[0] and "bio" not in rows[0]


def test_unknown_targets_404(env):
    client, db = env
    assert client.post("/api/admin/sync/tracks/nope/delist", json={"delisted": True}).status_code == 404
    assert client.post("/api/admin/sync/profiles/nobody/hide", json={"hidden": True}).status_code == 404
    assert db.admin_actions.inserted == []


@pytest.mark.parametrize("path, body", [
    (f"/api/admin/sync/tracks/{TID}/delist", {"delisted": "yes"}),
    (f"/api/admin/sync/tracks/{TID}/delist", {"delisted": True, "extra": 1}),
    ("/api/admin/sync/profiles/tyler-example/hide", {}),
])
def test_bad_bodies_rejected(env, path, body):
    client, db = env
    assert client.post(path, json=body).status_code == 422


def test_non_admin_is_refused():
    server.app.dependency_overrides.clear()
    client = TestClient(server.app)
    assert client.post(f"/api/admin/sync/tracks/{TID}/delist", json={"delisted": True}).status_code == 401
    assert client.get("/api/admin/sync/profiles").status_code == 401
