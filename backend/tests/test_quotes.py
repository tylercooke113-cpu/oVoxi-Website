"""Brief 18: POST /api/sync/quotes (quote requests)."""
import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

mongomock = pytest.importorskip("mongomock")

import server  # noqa: E402

LISTED = {"id": "t1", "track_name": "Golden Hour", "artist_name": "J Riv", "clerk_user_id": "u",
          "sync_status": "cleared", "on_sync_profile": True, "intake": {"content_id": "no"},
          "consent": {"sync": True, "exclusive_buyout": True}}
NO_BUYOUT = {**LISTED, "id": "t2", "consent": {"sync": True, "exclusive_buyout": False}}


class AsyncCollection:
    def __init__(self, c):
        self._c = c

    async def find_one(self, *a, **k):
        return self._c.find_one(*a, **k)

    async def insert_one(self, *a, **k):
        return self._c.insert_one(*a, **k)


class AsyncDB:
    def __init__(self):
        self._db = mongomock.MongoClient().db

    def __getattr__(self, name):
        return AsyncCollection(self._db[name])


@pytest.fixture
def env(monkeypatch):
    db = AsyncDB()
    db._db.track_submissions.insert_one(dict(LISTED))
    db._db.track_submissions.insert_one(dict(NO_BUYOUT))
    monkeypatch.setattr(server, "db", db)
    monkeypatch.setattr(server.limiter, "enabled", False)
    sender = AsyncMock(return_value={"status": "sent", "id": "e1", "error": None})
    monkeypatch.setattr(server, "send_email", sender)
    return SimpleEnv(TestClient(server.app), db, sender)


class SimpleEnv:
    def __init__(self, client, db, sender):
        self.client, self.db, self.sender = client, db, sender

    def quotes(self):
        return list(self.db._db.quote_requests.find({}, {"_id": 0}))


def body(**over):
    b = {"kind": "enterprise", "name": "Dana", "company": "Studio", "email": "dana@example.com",
         "use": "National TV campaign", "territory": "Worldwide", "term": "2 years",
         "budget": "$5,000 to $25,000", "details": "line one\nline two", "website": ""}
    b.update(over)
    return b


def test_enterprise_happy_path_stores_and_emails(env):
    r = env.client.post("/api/sync/quotes", json=body())
    assert r.status_code == 200 and r.json() == {"ok": True}
    [q] = env.quotes()
    assert q["kind"] == "enterprise" and q["email"] == "dana@example.com"
    assert q["details"] == "line one\nline two"          # newline preserved
    assert env.sender.await_count == 1
    assert env.sender.await_args.kwargs["reply_to"] == "dana@example.com"


def test_honeypot_discards_silently(env):
    r = env.client.post("/api/sync/quotes", json=body(website="http://spam"))
    assert r.status_code == 200 and env.quotes() == [] and env.sender.await_count == 0


def test_buyout_on_allowed_track(env):
    r = env.client.post("/api/sync/quotes", json=body(kind="buyout", track_id="t1", use="Exclusive buyout"))
    assert r.status_code == 200
    [q] = env.quotes()
    assert q["kind"] == "buyout" and q["track_title"] == "Golden Hour" and q["artist_display_name"] == "J Riv"


def test_buyout_on_not_allowed_track_409(env):
    r = env.client.post("/api/sync/quotes", json=body(kind="buyout", track_id="t2", use="Exclusive buyout"))
    assert r.status_code == 409 and env.quotes() == [] and env.sender.await_count == 0


def test_buyout_without_track_409(env):
    assert env.client.post("/api/sync/quotes", json=body(kind="buyout", use="Exclusive buyout")).status_code == 409


def test_email_failure_still_200_and_stored(env, monkeypatch):
    monkeypatch.setattr(server, "send_email",
                        AsyncMock(return_value={"status": "failed", "id": None, "error": "boom"}))
    r = env.client.post("/api/sync/quotes", json=body())
    assert r.status_code == 200 and len(env.quotes()) == 1


def test_bad_use_or_budget_422(env):
    assert env.client.post("/api/sync/quotes", json=body(use="Whatever")).status_code == 422
    assert env.client.post("/api/sync/quotes", json=body(budget="free")).status_code == 422


def test_rate_limit_enforced(env, monkeypatch):
    monkeypatch.setattr(server.limiter, "enabled", True)
    codes = [env.client.post("/api/sync/quotes", json=body()).status_code for _ in range(6)]
    assert codes[:5] == [200] * 5 and codes[5] == 429
