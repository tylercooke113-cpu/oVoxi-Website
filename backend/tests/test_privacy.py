"""Brief 26: privacy choices are appended, GPC forces advertising off, signed-in
choices are copied to Clerk without touching role or buyer."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import privacy
import server

USER = {"sub": "user_1", "metadata": {"role": "artist"}}


@pytest.fixture
def fake_db(monkeypatch):
    db = MagicMock()
    db.privacy_choices.insert_one = AsyncMock()
    db.privacy_choices.find_one = AsyncMock(return_value=None)
    monkeypatch.setattr(server, "db", db)
    return db


@pytest.fixture
def clerk(monkeypatch):
    m = AsyncMock()
    monkeypatch.setattr(server, "set_clerk_public_metadata", m)
    return m


def make_client(monkeypatch, viewer=None):
    monkeypatch.setattr(server.limiter, "enabled", False)
    server.app.dependency_overrides[server.optional_clerk] = lambda: viewer
    server.app.dependency_overrides[server.verify_clerk_token] = lambda: USER
    return TestClient(server.app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    server.app.dependency_overrides.clear()


def body(**over):
    b = {"analytics": True, "advertising": True, "gpc": False, "source": "prompt",
         "policy_date": "2026-10-27", "visitor_id": "3f2a9c1e-5b7d-4e8a-9c21-7d4e5f6a8b90"}
    b.update(over)
    return b


def inserted(fake_db):
    return fake_db.privacy_choices.insert_one.await_args.args[0]


def test_signed_out_choice_is_appended(monkeypatch, fake_db, clerk):
    r = make_client(monkeypatch).post("/api/privacy/choices", json=body(),
                                      headers={"User-Agent": "TestBrowser/1.0"})
    assert r.status_code == 200, r.text
    row = inserted(fake_db)
    assert row["user_id"] is None and row["visitor_id"].startswith("3f2a")
    assert row["analytics"] is True and row["advertising"] is True
    assert row["user_agent"] == "TestBrowser/1.0" and row["ip"]
    assert r.json()["clerk_synced"] is None
    clerk.assert_not_awaited()
    assert "ip" not in r.json()["choice"]


def test_gpc_forces_advertising_off(monkeypatch, fake_db, clerk):
    r = make_client(monkeypatch).post("/api/privacy/choices", json=body(gpc=True, advertising=True))
    assert r.status_code == 200
    assert inserted(fake_db)["advertising"] is False
    assert r.json()["choice"]["advertising"] is False


def test_signed_in_choice_goes_to_clerk_privacy_key_only(monkeypatch, fake_db, clerk):
    r = make_client(monkeypatch, viewer=USER).post(
        "/api/privacy/choices", json=body(source="account", advertising=False))
    assert r.status_code == 200 and r.json()["clerk_synced"] is True
    assert inserted(fake_db)["user_id"] == "user_1"
    uid, patch = clerk.await_args.args
    assert uid == "user_1" and set(patch) == {"privacy"}   # never role or buyer
    assert patch["privacy"]["analytics"] is True and patch["privacy"]["advertising"] is False
    assert patch["privacy"]["policy_date"] == "2026-10-27"


def test_clerk_failure_still_saves(monkeypatch, fake_db, clerk):
    clerk.side_effect = server.HTTPException(status_code=503, detail="x")
    r = make_client(monkeypatch, viewer=USER).post("/api/privacy/choices", json=body(source="account"))
    assert r.status_code == 200 and r.json()["clerk_synced"] is False
    fake_db.privacy_choices.insert_one.assert_awaited_once()


def test_signup_keeps_an_existing_account_choice(monkeypatch, fake_db, clerk):
    fake_db.privacy_choices.find_one.return_value = {
        "user_id": "user_1", "analytics": False, "advertising": False, "gpc": False,
        "source": "account", "policy_date": "2026-10-27", "created_at": "2026-10-27T00:00:00+00:00"}
    r = make_client(monkeypatch, viewer=USER).post("/api/privacy/choices", json=body(source="signup"))
    assert r.status_code == 200 and r.json()["saved"] is False
    assert r.json()["choice"]["analytics"] is False
    fake_db.privacy_choices.insert_one.assert_not_awaited()
    clerk.assert_not_awaited()


def test_signup_saves_when_the_account_has_none(monkeypatch, fake_db, clerk):
    r = make_client(monkeypatch, viewer=USER).post("/api/privacy/choices", json=body(source="signup"))
    assert r.status_code == 200 and r.json()["saved"] is True
    assert inserted(fake_db)["source"] == "signup"


@pytest.mark.parametrize("over", [
    {"source": "ads"}, {"policy_date": "Oct 27"}, {"visitor_id": "x y"},
    {"analytics": "maybe"}, {"role": "admin"},
])
def test_bad_payloads_refused(monkeypatch, fake_db, clerk, over):
    r = make_client(monkeypatch).post("/api/privacy/choices", json=body(**over))
    assert r.status_code == 422
    fake_db.privacy_choices.insert_one.assert_not_awaited()


def test_me_returns_latest_without_ip(monkeypatch, fake_db, clerk):
    fake_db.privacy_choices.find_one.return_value = privacy.choice_row(
        privacy.PrivacyChoiceIn(**body()), user_id="user_1", ip="1.2.3.4", user_agent="UA",
        now=datetime(2026, 10, 27, tzinfo=timezone.utc))
    r = make_client(monkeypatch).get("/api/privacy/me")
    assert r.status_code == 200
    choice = r.json()["choice"]
    assert choice["analytics"] is True and "ip" not in choice and "user_agent" not in choice
    assert fake_db.privacy_choices.find_one.await_args.args[0] == {"user_id": "user_1"}


def test_me_with_no_choice(monkeypatch, fake_db, clerk):
    assert make_client(monkeypatch).get("/api/privacy/me").json() == {"choice": None}


def test_user_agent_is_capped():
    row = privacy.choice_row(privacy.PrivacyChoiceIn(**body()), user_id=None, ip="1",
                             user_agent="A" * 1000)
    assert len(row["user_agent"]) == privacy.USER_AGENT_MAX


def test_choices_endpoint_is_rate_limited():
    route = next(r for r in server.app.routes if getattr(r, "path", "") == "/api/privacy/choices")
    limits = server.limiter._route_limits[f"{route.endpoint.__module__}.{route.endpoint.__name__}"]
    assert [str(lim.limit) for lim in limits] == ["30 per 1 minute"]


def test_model_has_no_extra_fields():
    with pytest.raises(ValidationError):
        privacy.PrivacyChoiceIn(**body(user_id="someone_else"))
