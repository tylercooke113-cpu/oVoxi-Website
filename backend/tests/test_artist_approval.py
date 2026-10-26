import asyncio

import pytest
from fastapi import HTTPException

import server


def _call(payload):
    return asyncio.run(server.require_artist(payload))


def test_default_lets_pending_accounts_in_but_not_approved(monkeypatch):
    # Oct 26: accounts awaiting approval may upload (held); approval gates processing.
    monkeypatch.delenv("ARTIST_APPROVAL_REQUIRED", raising=False)
    assert _call({"sub": "u1", "metadata": {}})["sub"] == "u1"
    assert server.is_approved({"sub": "u1", "metadata": {}}) is False
    assert server.is_approved({"sub": "u1", "metadata": {"role": "artist"}}) is True
    assert server.is_approved({"sub": "u1", "metadata": {"role": "admin"}}) is True


def test_approval_off_treats_everyone_as_approved(monkeypatch):
    monkeypatch.setenv("ARTIST_APPROVAL_REQUIRED", "false")
    assert _call({"sub": "u2"})["sub"] == "u2"
    assert server.is_approved({"sub": "u2", "metadata": {}}) is True


def test_approval_off_still_refuses_other_roles(monkeypatch):
    monkeypatch.setenv("ARTIST_APPROVAL_REQUIRED", "false")
    with pytest.raises(HTTPException):
        _call({"sub": "u3", "metadata": {"role": "suspended"}})


def test_admin_routes_unaffected(monkeypatch):
    monkeypatch.setenv("ARTIST_APPROVAL_REQUIRED", "false")
    with pytest.raises(HTTPException):
        asyncio.run(server.require_admin({"sub": "u4", "metadata": {}}))


# ---------------------------------------------------------------------------
# Held uploads: worker skips them; approval releases them (Oct 26)
# ---------------------------------------------------------------------------
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from test_subscriptions import AsyncDB


def test_worker_never_claims_held_uploads(monkeypatch):
    import mongomock
    seen = {}

    class Col:
        async def find_one_and_update(self, flt, *a, **k):
            seen.update(flt)
            return None

    monkeypatch.setattr(server, "db", SimpleNamespace(track_submissions=Col()))
    asyncio.run(server._claim_next())
    assert seen == {"status": "uploaded", "awaiting_approval": {"$ne": True}}


@pytest.fixture
def approve_env(monkeypatch):
    db = AsyncDB()
    db._db.track_submissions.insert_many([
        {"id": "h1", "clerk_user_id": "user_abc", "status": "uploaded", "awaiting_approval": True,
         "cosign_required": True},
        {"id": "h2", "clerk_user_id": "user_abc", "status": "pending", "awaiting_approval": True},
        {"id": "x1", "clerk_user_id": "user_other", "status": "uploaded", "awaiting_approval": True},
    ])
    clerk = AsyncMock()
    dispatch = AsyncMock()
    sender = AsyncMock(return_value={"status": "sent"})
    monkeypatch.setattr(server, "db", db)
    monkeypatch.setattr(server, "set_clerk_public_metadata", clerk)
    monkeypatch.setattr(server, "_dispatch_cosign_requests", dispatch)
    monkeypatch.setattr(server, "fetch_clerk_user", AsyncMock(return_value={"email": "artist@example.com"}))
    monkeypatch.setattr(server, "send_email", sender)
    monkeypatch.setattr(server.limiter, "enabled", False)
    server.app.dependency_overrides[server.require_admin] = lambda: {"sub": "admin", "metadata": {"role": "admin"}}
    yield SimpleNamespace(client=TestClient(server.app), db=db, clerk=clerk, dispatch=dispatch, sender=sender)
    server.app.dependency_overrides.clear()


def test_admin_approve_sets_role_releases_and_emails(approve_env):
    r = approve_env.client.post("/api/admin/artists/user_abc/approve")
    assert r.status_code == 200, r.text
    assert r.json()["released"] == 2
    approve_env.clerk.assert_awaited_once_with("user_abc", {"role": "artist"})
    docs = {d["id"]: d for d in approve_env.db._db.track_submissions.find({}, {"_id": 0})}
    assert docs["h1"]["awaiting_approval"] is False and docs["h2"]["awaiting_approval"] is False
    assert docs["x1"]["awaiting_approval"] is True                    # other artists untouched
    assert approve_env.dispatch.await_count == 1                      # co-owner emails only for h1
    assert approve_env.sender.await_args.kwargs["to"] == "artist@example.com"
    assert approve_env.db._db.admin_actions.find_one({}, {"_id": 0})["action"] == "approve_artist"


def test_admin_approve_bad_id_422(approve_env):
    assert approve_env.client.post("/api/admin/artists/not-a-user/approve").status_code == 422
