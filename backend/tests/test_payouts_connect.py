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


def v2_account(transfers="pending", payouts="pending", due=("individual.id_number",)):
    """The v2 Account shape this code reads (include: configuration.recipient, requirements)."""
    return Obj(id="acct_1", object="v2.core.account", dashboard="express",
               configuration={"recipient": {"capabilities": {"stripe_balance": {
                   "stripe_transfers": {"status": transfers, "status_details": []},
                   "payouts": {"status": payouts, "status_details": []}}}}},
               requirements={"entries": [{"description": d, "awaiting_action_from": "user",
                                          "minimum_deadline": {"status": "currently_due"}} for d in due]})


class FakeStripe:
    def __init__(self):
        self.created, self.links, self.retrieved = [], [], []
        self.account = v2_account()
        real = __import__("stripe").StripeClient("sk_test_fake")
        core = SimpleNamespace(
            accounts=SimpleNamespace(
                create=lambda params: (self.created.append(params), self.account)[1],
                retrieve=lambda aid, params=None: (self.retrieved.append((aid, params)), self.account)[1]),
            account_links=SimpleNamespace(
                create=lambda p: (self.links.append(p), Obj(url=f"https://connect.stripe.com/setup/{p['account']}"))[1]))
        self.v2 = SimpleNamespace(core=core)
        self.v1 = SimpleNamespace(accounts=SimpleNamespace(
            login_links=SimpleNamespace(create=lambda aid: Obj(url="https://connect.stripe.com/express/x"))))
        self.parse_event_notification = real.parse_event_notification


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
    assert p["dashboard"] == "express" and p["identity"] == {"country": "us", "entity_type": "individual"}
    assert p["configuration"] == {"recipient": {"capabilities": {"stripe_balance": {"stripe_transfers": {"requested": True}}}}}
    assert p["defaults"] == {"responsibilities": {"fees_collector": "application", "losses_collector": "application"}}
    assert p["metadata"] == {"ovoxi_user_id": "user_1"} and p["contact_email"] == "artist@example.com"
    assert "type" not in p and "capabilities" not in p        # no v1 fields
    env.client.post("/api/wallet/connect", json={"country": "US"})       # resume onboarding
    assert len(env.fake.created) == 1
    acct = run(env.db.wallet_accounts.find_one({"user_id": "user_1"}))
    assert acct["livemode"] is False and acct["stripe_account_id"] == "acct_1"


def test_onboarding_returns_to_the_wallet_tab(env):
    env.client.post("/api/wallet/connect", json={"country": "US"})
    link = env.fake.links[0]
    assert link["account"] == "acct_1" and link["use_case"]["type"] == "account_onboarding"
    ob = link["use_case"]["account_onboarding"]
    assert ob["configurations"] == ["recipient"]
    assert ob["return_url"] == "https://ovoxi.net/vault?tab=wallet&connect=done"
    assert ob["refresh_url"] == "https://ovoxi.net/vault?tab=wallet&connect=refresh"


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
    s = env.client.get("/api/wallet/connect/status").json()
    assert s["connected"] and not s["payouts_enabled"] and s["currently_due"] == ["individual.id_number"]
    env.fake.account = v2_account("active", "active", due=())
    s = env.client.get("/api/wallet/connect/status").json()
    assert s["details_submitted"] and s["payouts_enabled"] and s["currently_due"] == []
    assert env.fake.retrieved[-1] == ("acct_1", {"include": ["configuration.recipient", "requirements"]})


def test_status_of_reads_v2_fields():
    st = payouts.status_of(v2_account("active", "pending", due=()))
    assert st["transfers_active"] and not st["payouts_enabled"] and not payouts.payout_ready(st)
    restricted = v2_account("restricted", "restricted", due=())
    restricted["configuration"]["recipient"]["capabilities"]["stripe_balance"]["stripe_transfers"]["status_details"] = [
        {"code": "requirements_past_due"}]
    assert payouts.status_of(restricted)["disabled_reason"] == "requirements_past_due"
    assert payouts.status_of({})["details_submitted"] is False


def test_payouts_need_transfers_active_too():
    assert payouts.payout_ready({"payouts_enabled": True, "transfers_active": True})
    assert not payouts.payout_ready({"payouts_enabled": True, "transfers_active": False})
    assert not payouts.payout_ready(None)


def test_dashboard_link_needs_onboarding(env):
    assert env.client.post("/api/wallet/dashboard-link").status_code == 409
    env.client.post("/api/wallet/connect", json={"country": "US"})
    env.fake.account = v2_account("active", "active", due=())
    env.client.get("/api/wallet/connect/status")
    r = env.client.post("/api/wallet/dashboard-link")
    assert r.status_code == 200 and r.json()["url"].startswith("https://connect.stripe.com/express/")


def signed(payload: dict, secret: str):
    import hashlib, hmac, json, time
    body = json.dumps(payload).encode()
    t = int(time.time())
    sig = hmac.new(secret.encode(), f"{t}.".encode() + body, hashlib.sha256).hexdigest()
    return body, f"t={t},v1={sig}"


def thin_event(etype="v2.core.account[configuration.recipient].capability_status_updated", acct="acct_1"):
    return {"id": "evt_test_1", "object": "v2.core.event", "type": etype, "livemode": False,
            "created": "2026-10-27T01:30:00.000Z",
            "related_object": {"id": acct, "type": "v2.core.account", "url": f"/v2/core/accounts/{acct}"}}


def test_connect_webhook_reads_a_v2_thin_event(env, monkeypatch):
    env.client.post("/api/wallet/connect", json={"country": "US"})
    monkeypatch.setenv("STRIPE_CONNECT_WEBHOOK_SECRET", "whsec_c")
    env.fake.account = v2_account("active", "active", due=())
    body, sig = signed(thin_event(), "whsec_c")
    r = env.client.post("/api/stripe/connect-webhook", content=body, headers={"stripe-signature": sig})
    assert r.status_code == 200, r.text
    saved = run(env.db.wallet_accounts.find_one({"stripe_account_id": "acct_1"}))
    assert saved["payouts_enabled"] and saved["transfers_active"]


def test_connect_webhook_ignores_unknown_accounts(env, monkeypatch):
    monkeypatch.setenv("STRIPE_CONNECT_WEBHOOK_SECRET", "whsec_c")
    body, sig = signed(thin_event(acct="acct_unknown"), "whsec_c")
    assert env.client.post("/api/stripe/connect-webhook", content=body, headers={"stripe-signature": sig}).status_code == 200
    assert env.fake.retrieved == []


def test_connect_webhook_without_secret_is_refused(env, monkeypatch):
    monkeypatch.delenv("STRIPE_CONNECT_WEBHOOK_SECRET", raising=False)
    assert env.client.post("/api/stripe/connect-webhook", content=b"{}").status_code == 503


def test_connect_webhook_bad_signature(env, monkeypatch):
    monkeypatch.setenv("STRIPE_CONNECT_WEBHOOK_SECRET", "whsec_c")
    assert env.client.post("/api/stripe/connect-webhook", content=b"{}",
                           headers={"stripe-signature": "t=1,v1=bad"}).status_code == 400
