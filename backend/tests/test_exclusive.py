"""Brief 25b Part B: exclusive songs. Pure rules, the sale record and takedown,
and the refusals on every standard sale path."""
import asyncio
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import exclusive as ex
import server
from sync_public import LISTING_FILTER, is_listed, public_track_view
from test_sync_orders import AsyncDB  # noqa: E402

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)

LISTED = {
    "id": "t1", "clerk_user_id": "user_artist", "track_name": "Night Drive", "artist_name": "Upload Name",
    "sync_status": "cleared", "consent": {"sync": True, "ai_training": True, "exclusive": True},
    "intake": {"content_id": "no"}, "on_sync_profile": True,
    "mastered_r2_key": "catalog/a/b/mastered/t1.wav",
}


def run(coro):
    return asyncio.run(coro)


def lic(track=None, **over):
    kw = dict(track=track or LISTED, uses=["sync"], buyer_name="Dana", buyer_company="Acme",
              buyer_email="Dana@Example.com", price_cents_sync=500000, price_cents_ai=None,
              granted_by="user_admin", now=NOW)
    kw.update(over)
    return ex.build_exclusive_license(**kw)


# --------------------------------------------------------------------------- pure rules

def test_helpers():
    t = {**LISTED, "exclusive_sold": {"sync": "L1", "ai": None}}
    assert ex.is_exclusive(t) and not ex.is_exclusive({"consent": {"exclusive": False}})
    assert ex.opted_uses(t) == ["sync", "ai"] and ex.sold_uses(t) == ["sync"]
    assert not ex.use_available(t, "sync") and ex.use_available(t, "ai")
    assert not ex.fully_sold(t)
    assert ex.fully_sold({**t, "exclusive_sold": {"sync": "L1", "ai": "L2"}})
    assert ex.uses_label(["ai", "sync"]) == "sync and AI training"


def test_build_license_both_uses_total_is_sum_and_rate_40pct():
    r = lic(uses=["ai", "sync"], price_cents_sync=500000, price_cents_ai=300000)
    assert r["uses"] == ["sync", "ai"]
    assert r["total_cents"] == 800000 and r["rate_bp"] == 4000
    assert r["term"] == "Perpetual" and r["territory"] == "Worldwide"
    assert r["buyer_email"] == "dana@example.com" and r["quote_id"] is None


@pytest.mark.parametrize("over,msg", [
    ({"uses": []}, "Choose sync, AI training or both."),
    ({"track": {**LISTED, "consent": {"sync": True, "exclusive": False}}}, "not offered as exclusive"),
    ({"track": {**LISTED, "consent": {"sync": True, "exclusive": True}}, "uses": ["ai"],
      "price_cents_ai": 100}, "not opted into AI training"),
    ({"track": {**LISTED, "exclusive_sold": {"sync": "L1"}}}, "already licensed exclusively for sync"),
    ({"price_cents_sync": 0}, "Enter a price for sync."),
    ({"buyer_email": ""}, "buyer's name and email"),
])
def test_build_license_refusals(over, msg):
    with pytest.raises(ex.ExclusiveError, match=msg):
        lic(**over)


# --------------------------------------------------------------------------- record + takedown

def test_record_sets_sold_stores_license_and_takes_down_sync():
    db = AsyncDB()
    db._db.track_submissions.insert_one(dict(LISTED))
    r = lic()
    run(ex.record_exclusive_license(db, r))
    t = db._db.track_submissions.find_one({"id": "t1"}, {"_id": 0})
    assert t["exclusive_sold"] == {"sync": r["id"]}
    assert db._db.exclusive_licenses.find_one({"id": r["id"]}, {"_id": 0})["rate_bp"] == 4000
    assert is_listed(t) is False                                   # sync down at once
    assert ex.use_available(t, "ai") is True                       # AI stays offered
    assert db._db.track_submissions.count_documents(LISTING_FILTER) == 0


def test_record_twice_for_same_use_refused():
    db = AsyncDB()
    db._db.track_submissions.insert_one(dict(LISTED))
    run(ex.record_exclusive_license(db, lic()))
    with pytest.raises(ex.ExclusiveError, match="just licensed exclusively"):
        run(ex.record_exclusive_license(db, lic()))                # built before the first landed
    assert db._db.exclusive_licenses.count_documents({}) == 1


def test_listing_filter_matches_unsold_track():
    db = AsyncDB()
    db._db.track_submissions.insert_one(dict(LISTED))
    assert db._db.track_submissions.count_documents(LISTING_FILTER) == 1
    assert is_listed(LISTED) is True


def test_public_view_exposes_exclusive_flag():
    assert public_track_view(LISTED, None)["exclusive"] is True
    assert "buyout_allowed" not in public_track_view(LISTED, None)


# --------------------------------------------------------------------------- standard sale paths refuse

@pytest.fixture
def checkout_env(monkeypatch):
    for name in ("SYNC_DELIVER_STEMS", "SYNC_TERMS_VERSION", "SYNC_SITE_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_abc")
    monkeypatch.setenv("SYNC_TOKEN_SECRET", "s" * 64)
    monkeypatch.setenv("SYNC_CHECKOUT_ENABLED", "true")
    db = AsyncDB()
    db._db.track_submissions.insert_one(dict(LISTED))
    db._db.sync_profiles.insert_one({"user_id": "user_artist", "display_name": "Kay", "slug": "kay"})
    monkeypatch.setattr(server, "db", db)
    monkeypatch.setattr(server.limiter, "enabled", False)
    server.app.dependency_overrides[server.optional_clerk] = lambda: {"sub": "user_admin", "metadata": {"role": "admin"}}
    yield SimpleNamespace(client=TestClient(server.app), db=db)
    server.app.dependency_overrides.clear()


from types import SimpleNamespace  # noqa: E402


def test_checkout_refuses_exclusive_song_409(checkout_env):
    import sync_orders as so
    r = checkout_env.client.post("/api/sync/checkout", json={
        "track_id": "t1", "tier": "digital", "include_stems": False, "buyer_name": "Dana",
        "buyer_company": "", "buyer_email": "dana@example.com", "project_name": "Teaser",
        "accept_terms": True, "terms_version": so.terms_version()})
    assert r.status_code == 409 and r.json()["detail"] == ex.EXCLUSIVE_ONLY_DETAIL
    assert checkout_env.db._db.orders.count_documents({}) == 0


def test_subscription_register_refuses_exclusive_song_409(monkeypatch):
    import subscriptions
    import sync_orders as so
    from test_subscriptions import AsyncDB as SubsDB
    db = SubsDB()
    db._db.track_submissions.insert_one(dict(LISTED))

    async def _ready():
        return True

    async def _access(*a, **k):
        return {"can_register": True, "plan": "pro", "reason": None}

    monkeypatch.setattr(server, "db", db)
    monkeypatch.setattr(server, "_subscriptions_ready", _ready)
    monkeypatch.setattr(subscriptions, "plan_access", _access)
    monkeypatch.setattr(server.limiter, "enabled", False)
    monkeypatch.setenv("SYNC_CHECKOUT_ENABLED", "true")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("SYNC_TOKEN_SECRET", "s" * 64)
    server.app.dependency_overrides[server.verify_clerk_token] = lambda: {"sub": "u", "metadata": {"role": "artist"}}
    try:
        r = TestClient(server.app).post("/api/subscriptions/register", json={
            "track_id": "t1", "project_name": "My project", "project_client": "",
            "include_stems": False, "accept_terms": True, "terms_version": so.terms_version()})
        assert r.status_code == 409 and r.json()["detail"] == ex.EXCLUSIVE_ONLY_DETAIL
        assert db._db.sub_usage.count_documents({}) == 0           # no download slot used
        assert db._db.licenses.count_documents({}) == 0
    finally:
        server.app.dependency_overrides.clear()
