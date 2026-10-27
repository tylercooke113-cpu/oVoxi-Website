"""Brief 27 Part B: Stripe Connect Express onboarding, status and the Connect webhook.
The fake client returns the dahlia shapes this code reads (id, details_submitted,
payouts_enabled, capabilities.transfers, requirements)."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import payouts
import server
import sync_orders
from test_subscriptions import AsyncDB, run

USER = {"sub": "user_1", "metadata": {"role": "artist"}}


class Obj(dict):
    def to_dict(self):
        return dict(self)


class FakeStripe:
    def __init__(self):
        self.created = []
        self.account = Obj(id="acct_1", details_submitted=False, payouts_enabled=False,
                           capabilities={"transfers": "inactive"},
                           requirements={"currently_due": ["individual.ssn_last_4"], "disabled_reason": None})
        accounts = SimpleNamespace(
            create=lambda params: (self.created.append(params), self.account)[1],
            retrieve=lambda aid: self.account,
            login_links=SimpleNamespace(create=lambda aid: Obj(url="https://connect.stripe.com/express/x")))
        self.v1 = SimpleNamespace(
            accounts=accounts,
            account_links=SimpleNamespace(create=lambda p: Obj(url=f"https://connect.stripe.com/setup/{p['account']}",
                                                               params=p)))


@pytest.fixture
def env(monkeypatch):
    db = AsyncDB()
    run(payouts.ensure_indexes(db))
    fake = FakeStripe()
    monkeypatch.setattr(server, "db", db)
    monkeypatch.setattr(server.limiter, "enabled", False)
    monkeypatch.setattr(sync_orders, "stripe_client", lambda: fake)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setenv("SYNC_SITE_URL", "https://ovoxi.net")

    async def clerk_user(uid):
        return {"email": "artist@example.com"}

    async def agreement(uid):
        return {"fields": {"country": "USA"}}
    monkeypatch.setattr(server, "fetch_clerk_user", clerk_user)
    monkeypatch.setattr(server, "_current_agreement", agreement)
    server.app.dependency_overrides[server.verify_clerk_token] = lambda: USER
    yield SimpleNamespace(db=db, fake=fake, client=TestClient(server.app))
    server.app.dependency_overrides.clear()


@pytest.mark.parametrize("text, code", [
    ("USA", "US"), ("United States", "US"), ("us", "US"), ("United Kingdom", "GB"), ("UK", "GB"),
    ("Germany", "DE"), ("CA", "CA"), ("Nigeria", None), ("South Africa", None), ("", None), (None, None),
])
def test_guess_country(text, code):
    assert payouts.guess_country(text) == code


def test_status_suggests_the_agreement_country(env):
    r = env.client.get("/api/wallet/connect/status")
    assert r.status_code == 200
    body = r.json()
    assert body["connected"] is False and body["suggested_country"] == "US"
    assert {"code": "US", "name": "United States"} in body["countries"]


def test_connect_creates_one_express_account_and_returns_the_link(env):
    r = env.client.post("/api/wallet/connect", json={"country": "us"})
    assert r.status_code == 200, r.text
    assert r.json()["url"] == "https://connect.stripe.com/setup/acct_1"
    p = env.fake.created[0]
    assert p["type"] == "express" and p["country"] == "US"
    assert p["capabilities"] == {"transfers": {"requested": True}}
    assert p["metadata"] == {"ovoxi_user_id": "user_1"} and p["email"] == "artist@example.com"
    env.client.post("/api/wallet/connect", json={"country": "US"})       # resume onboarding
    assert len(env.fake.created) == 1
    acct = run(env.db.wallet_accounts.find_one({"user_id": "user_1"}))
    assert acct["livemode"] is False and acct["stripe_account_id"] == "acct_1"


def test_onboarding_returns_to_the_wallet_tab(env):
    seen = {}
    env.fake.v1.account_links.create = lambda p: (seen.update(p), Obj(url="u"))[1]
    env.client.post("/api/wallet/connect", json={"country": "US"})
    assert seen["type"] == "account_onboarding"
    assert seen["return_url"] == "https://ovoxi.net/vault?tab=wallet&connect=done"
    assert seen["refresh_url"] == "https://ovoxi.net/vault?tab=wallet&connect=refresh"


def test_unsupported_country_accrues_with_the_message(env):
    r = env.client.post("/api/wallet/connect", json={"country": "NG"})
    assert r.status_code == 200
    assert r.json() == {"url": None, "unsupported": True, "message": payouts.UNSUPPORTED_MESSAGE}
    assert env.fake.created == []
    s = env.client.get("/api/wallet/connect/status").json()
    assert s["unsupported"] is True and s["message"] == payouts.UNSUPPORTED_MESSAGE


def test_payout_country_cannot_change_after_connecting(env):
    env.client.post("/api/wallet/connect", json={"country": "US"})
    r = env.client.post("/api/wallet/connect", json={"country": "GB"})
    assert r.status_code == 409


def test_status_refreshes_from_stripe(env):
    env.client.post("/api/wallet/connect", json={"country": "US"})
    env.fake.account.update(details_submitted=True, payouts_enabled=True,
                            capabilities={"transfers": "active"}, requirements={"currently_due": []})
    s = env.client.get("/api/wallet/connect/status").json()
    assert s["connected"] and s["details_submitted"] and s["payouts_enabled"] and s["currently_due"] == []


def test_payouts_need_transfers_active_too():
    assert payouts.payout_ready({"payouts_enabled": True, "transfers_active": True})
    assert not payouts.payout_ready({"payouts_enabled": True, "transfers_active": False})
    assert not payouts.payout_ready(None)


def test_dashboard_link_needs_onboarding(env):
    assert env.client.post("/api/wallet/dashboard-link").status_code == 409
    env.client.post("/api/wallet/connect", json={"country": "US"})
    env.fake.account.update(details_submitted=True)
    env.client.get("/api/wallet/connect/status")
    r = env.client.post("/api/wallet/dashboard-link")
    assert r.status_code == 200 and r.json()["url"].startswith("https://connect.stripe.com/express/")


def test_connect_webhook_updates_status(env, monkeypatch):
    import stripe
    env.client.post("/api/wallet/connect", json={"country": "US"})
    monkeypatch.setenv("STRIPE_CONNECT_WEBHOOK_SECRET", "whsec_c")
    acct = Obj(id="acct_1", details_submitted=True, payouts_enabled=True, capabilities={"transfers": "active"},
               requirements={"currently_due": []})
    event = SimpleNamespace(type="account.updated", data=SimpleNamespace(object=acct))
    monkeypatch.setattr(stripe.Webhook, "construct_event", lambda body, sig, secret: event)
    assert env.client.post("/api/stripe/connect-webhook", content=b"{}", headers={"stripe-signature": "x"}).status_code == 200
    saved = run(env.db.wallet_accounts.find_one({"stripe_account_id": "acct_1"}))
    assert saved["payouts_enabled"] and saved["transfers_active"]


def test_connect_webhook_without_secret_is_refused(env, monkeypatch):
    monkeypatch.delenv("STRIPE_CONNECT_WEBHOOK_SECRET", raising=False)
    assert env.client.post("/api/stripe/connect-webhook", content=b"{}").status_code == 503


def test_connect_webhook_bad_signature(env, monkeypatch):
    monkeypatch.setenv("STRIPE_CONNECT_WEBHOOK_SECRET", "whsec_c")
    assert env.client.post("/api/stripe/connect-webhook", content=b"{}",
                           headers={"stripe-signature": "t=1,v1=bad"}).status_code == 400
