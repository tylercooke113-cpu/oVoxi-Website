"""PRD-03 Phase 6a: POST /api/sync/checkout and the Stripe session parameters.

Stripe is replaced by a fake client; MongoDB by mongomock through the async
adapter in test_sync_orders.
"""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("mongomock")

import server  # noqa: E402
import sync_orders as so  # noqa: E402
from test_sync_orders import AsyncDB  # noqa: E402

ADMIN = {"sub": "user_admin", "metadata": {"role": "admin"}}
BUYER = None  # anonymous guest
NOW = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)

LISTED = {
    "id": "t1", "clerk_user_id": "user_artist", "track_name": "Night Drive", "artist_name": "Upload Name",
    "sync_status": "cleared", "consent": {"sync": True, "ai_training": False}, "intake": {"content_id": "no"},
    "on_sync_profile": True, "mastered_r2_key": "catalog/a/b/mastered/t1.wav", "matched_title": "SECRET",
}


class FakeSessions:
    def __init__(self, fail=False):
        self.calls, self.fail = [], fail

    def create(self, params, options=None):
        if self.fail:
            raise RuntimeError("stripe down")
        self.calls.append((params, options))
        return SimpleNamespace(id="cs_test_123", url="https://checkout.stripe.com/c/pay/cs_test_123")


def body(**over):
    b = {"track_id": "t1", "tier": "digital", "include_stems": True, "buyer_name": "  Dana   Buyer ",
         "buyer_company": "", "buyer_email": "dana@example.com", "project_name": "Summer campaign teaser",
         "accept_terms": True, "terms_version": "v1"}
    b.update(over)
    return b


@pytest.fixture
def env(monkeypatch):
    for name in ("SYNC_CHECKOUT_ENABLED", "SYNC_DELIVER_STEMS", "SYNC_TERMS_VERSION", "SYNC_SITE_URL",
                 "SYNC_STRIPE_TAX_CODE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_abc")
    monkeypatch.setenv("SYNC_TOKEN_SECRET", "s" * 64)
    db = AsyncDB()
    db._db.track_submissions.insert_one(dict(LISTED))
    db._db.sync_profiles.insert_one({"user_id": "user_artist", "display_name": "Kay Lune", "slug": "kay-lune"})
    monkeypatch.setattr(server, "db", db)
    monkeypatch.setattr(server.limiter, "enabled", False)
    sessions = FakeSessions()
    monkeypatch.setattr(so, "stripe_client", lambda: SimpleNamespace(
        v1=SimpleNamespace(checkout=SimpleNamespace(sessions=sessions))))
    state = {"viewer": ADMIN}
    server.app.dependency_overrides[server.optional_clerk] = lambda: state["viewer"]
    yield SimpleNamespace(client=TestClient(server.app), db=db, sessions=sessions, state=state)
    server.app.dependency_overrides.clear()


def orders(env):
    return list(env.db._db.orders.find({}, {"_id": 0}))


def test_admin_test_purchase_creates_order_and_session(env):
    r = env.client.post("/api/sync/checkout", json=body())
    assert r.status_code == 200, r.text
    assert r.json()["checkout_url"].startswith("https://checkout.stripe.com/")
    [o] = orders(env)
    assert o["status"] == "pending" and o["price_cents"] == 29900 and o["test_mode"] is True
    assert o["stripe_session_id"] == "cs_test_123" and o["buyer_name"] == "Dana Buyer"
    assert o["track_title"] == "Night Drive" and o["artist_display_name"] == "Kay Lune"
    params, options = env.sessions.calls[0]
    assert options == {"idempotency_key": f"checkout-{o['order_id']}"}
    assert params["line_items"][0]["price_data"]["unit_amount"] == 29900
    assert params["metadata"]["order_id"] == o["order_id"]


def test_public_blocked_while_disabled(env):
    env.state["viewer"] = BUYER
    r = env.client.post("/api/sync/checkout", json=body())
    assert r.status_code == 403 and orders(env) == []


def test_admin_blocked_with_live_key_while_disabled(env, monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_abc")
    assert env.client.post("/api/sync/checkout", json=body()).status_code == 403


def test_public_allowed_when_enabled(env, monkeypatch):
    monkeypatch.setenv("SYNC_CHECKOUT_ENABLED", "true")
    env.state["viewer"] = BUYER
    assert env.client.post("/api/sync/checkout", json=body()).status_code == 200


def test_client_price_rejected(env):
    r = env.client.post("/api/sync/checkout", json=body(price_cents=1))
    assert r.status_code == 422 and orders(env) == []


@pytest.mark.parametrize("over,code", [
    ({"accept_terms": False}, 422), ({"terms_version": "old"}, 409), ({"tier": "enterprise"}, 422),
    ({"buyer_email": "not-an-email"}, 422), ({"buyer_name": ""}, 422), ({"track_id": "missing"}, 404),
])
def test_bad_requests(env, over, code):
    assert env.client.post("/api/sync/checkout", json=body(**over)).status_code == code
    assert orders(env) == []


@pytest.mark.parametrize("change", [
    {"sync_status": "needs_docs"}, {"consent": {"sync": False}}, {"intake": {"content_id": "yes"}},
    {"on_sync_profile": False}, {"sync_delisted_by_admin": True},
])
def test_unlisted_track_is_404(env, change):
    env.db._db.track_submissions.update_one({"id": "t1"}, {"$set": change})
    assert env.client.post("/api/sync/checkout", json=body()).status_code == 404


def test_stems_forced_off_when_disabled(env, monkeypatch):
    monkeypatch.setenv("SYNC_DELIVER_STEMS", "false")
    r = env.client.post("/api/sync/checkout", json=body())   # body asks for stems
    assert r.status_code == 200
    [o] = orders(env)
    assert o["include_stems"] is False and o["price_cents"] == 29900


def test_missing_token_secret_is_503_before_any_order(env, monkeypatch):
    monkeypatch.delenv("SYNC_TOKEN_SECRET")
    assert env.client.post("/api/sync/checkout", json=body()).status_code == 503
    assert orders(env) == []


def test_stripe_failure_marks_order_failed(env):
    env.sessions.fail = True
    r = env.client.post("/api/sync/checkout", json=body())
    assert r.status_code == 502
    [o] = orders(env)
    assert o["status"] == "failed"


def test_session_params_tax_and_urls(monkeypatch):
    monkeypatch.setenv("SYNC_TOKEN_SECRET", "s" * 64)
    monkeypatch.setenv("SYNC_STRIPE_TAX_CODE", "txcd_test")
    monkeypatch.delenv("SYNC_SITE_URL", raising=False)
    o = so.build_order(track=LISTED, tier="creator", include_stems=False, buyer_name="B", buyer_company="",
                       buyer_email="b@example.com", test_mode=True, now=NOW, artist_display_name="Kay Lune")
    p = so.checkout_session_params(o, now=NOW)
    pd = p["line_items"][0]["price_data"]
    assert pd["unit_amount"] == 4900 and pd["tax_behavior"] == "exclusive"
    assert pd["product_data"]["tax_code"] == "txcd_test"
    assert pd["product_data"]["name"] == "Sync license: Night Drive by Kay Lune"
    assert p["automatic_tax"] == {"enabled": True} and p["billing_address_collection"] == "required"
    assert p["success_url"] == "https://ovoxi.net/sync/success?session_id={CHECKOUT_SESSION_ID}"
    assert p["cancel_url"] == "https://ovoxi.net/sync/track/t1?checkout=cancelled"
    assert p["expires_at"] == int(NOW.timestamp()) + 35 * 60
    assert "customer_creation" not in p


def test_site_url_must_be_https(monkeypatch):
    monkeypatch.setenv("SYNC_SITE_URL", "http://evil.example")
    with pytest.raises(so.ConfigError):
        so.site_url()
