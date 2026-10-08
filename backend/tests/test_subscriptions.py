"""Brief 19 subscriptions: pure rules, access/caps/loyalty, and the webhook handlers.

The handlers are exercised against BOTH synthetic payloads and the real Stripe events
captured by scripts/stripe_capture_events.py (tests/fixtures/stripe/*.json), so the
two-format (basil) field accessors are reconciled against payloads Stripe actually sends.
"""
import asyncio
import json
import os
from datetime import datetime, timedelta, timezone

import pytest

mongomock = pytest.importorskip("mongomock")

import subscriptions as subs  # noqa: E402

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
FIX = os.path.join(os.path.dirname(__file__), "fixtures", "stripe")


def has_fixtures():
    return os.path.isdir(FIX) and os.path.exists(os.path.join(FIX, "customer.subscription.created.json"))


def fixture(name):
    with open(os.path.join(FIX, name + ".json")) as fh:
        return json.load(fh)


def fx_obj(name):
    return fixture(name)["data"]["object"]


requires_fixtures = pytest.mark.skipif(not has_fixtures(), reason="run scripts/stripe_capture_events.py first")


# --------------------------------------------------------------------------- async mongomock harness

class AsyncCursor:
    def __init__(self, cur):
        self._cur = cur

    def sort(self, *a, **k):
        self._cur = self._cur.sort(*a, **k)
        return self

    async def to_list(self, n=None):
        return list(self._cur)


class AsyncCollection:
    def __init__(self, coll):
        self._c = coll

    async def find_one(self, *a, **k):
        return self._c.find_one(*a, **k)

    def find(self, *a, **k):
        return AsyncCursor(self._c.find(*a, **k))

    async def find_one_and_update(self, *a, **k):
        return self._c.find_one_and_update(*a, **k)

    async def insert_one(self, *a, **k):
        return self._c.insert_one(*a, **k)

    async def update_one(self, *a, **k):
        return self._c.update_one(*a, **k)

    async def update_many(self, *a, **k):
        return self._c.update_many(*a, **k)

    async def count_documents(self, *a, **k):
        return self._c.count_documents(*a, **k)

    async def create_index(self, keys, **k):
        k.pop("partialFilterExpression", None)
        return self._c.create_index(keys, **k)


class AsyncDB:
    def __init__(self):
        self._db = mongomock.MongoClient().db

    def __getattr__(self, name):
        return AsyncCollection(self._db[name])


def run(coro):
    return asyncio.run(coro)


# --------------------------------------------------------------------------- fake Stripe client

class Box:
    def __init__(self, d):
        self._d = d

    def to_dict(self):
        return self._d


class ListBox:
    def __init__(self, items):
        self.data = items

    def auto_paging_iter(self):
        return iter(self.data)


class FakeSvc:
    def __init__(self, **methods):
        self._m = methods
        self.calls = []

    def __getattr__(self, name):
        if name in ("_m", "calls"):
            raise AttributeError(name)

        def call(*a, **k):
            self.calls.append((name, a, k))
            fn = self._m.get(name)
            if fn is None:
                raise AssertionError(f"unexpected Stripe call: {name}{a}")
            return fn(*a, **k)
        return call


class FakeV1:
    def __init__(self, **svcs):
        for name, svc in svcs.items():
            setattr(self, name, svc)


class FakeClient:
    def __init__(self, **svcs):
        self.v1 = FakeV1(**svcs)


def _replay() -> dict:
    with open(os.path.join(FIX, "replay.json")) as fh:
        return json.load(fh)


def recording_client(rec=None, **override_svcs):
    """A fake Stripe client that replays the real dahlia responses captured in replay.json,
    so the handler tests exercise the live two-format resolution instead of hand-written mocks."""
    rec = rec if rec is not None else _replay()
    svcs = dict(
        invoice_payments=FakeSvc(list=lambda p: ListBox(
            [Box(x) for x in rec["invoice_payments.list"].get(p["payment"]["payment_intent"], [])])),
        invoices=FakeSvc(retrieve=lambda _id, *a: Box(rec["invoices.retrieve"][_id])),
        payment_intents=FakeSvc(retrieve=lambda _id, *a: Box(rec["payment_intents.retrieve"][_id])),
        charges=FakeSvc(retrieve=lambda _id, *a: Box(rec["charges.retrieve"][_id])),
        balance_transactions=FakeSvc(retrieve=lambda _id, *a: Box(rec["balance_transactions.retrieve"][_id])),
        refunds=FakeSvc(list=lambda p: ListBox([Box(x) for x in rec["refunds.list"].get(p["charge"], [])])),
    )
    svcs.update(override_svcs)
    return FakeClient(**svcs)


@pytest.fixture(autouse=True)
def reset_prices():
    subs._PRICE_IDS.clear()
    subs._LAST_LOAD = 0.0
    yield
    subs._PRICE_IDS.clear()


# --------------------------------------------------------------------------- pure: loyalty

def test_loyalty_target_steps():
    # period_start of invoice N is subscribed_since + (N-1) months; 15% from invoice 3, 20% from 7.
    since = "2026-01-01T00:00:00+00:00"
    assert subs.loyalty_target(since, "2026-01-01T00:00:00+00:00") == 0   # invoice 1
    assert subs.loyalty_target(since, "2026-02-01T00:00:00+00:00") == 0   # invoice 2
    assert subs.loyalty_target(since, "2026-03-01T00:00:00+00:00") == 15  # invoice 3
    assert subs.loyalty_target(since, "2026-06-01T00:00:00+00:00") == 15  # invoice 6
    assert subs.loyalty_target(since, "2026-07-01T00:00:00+00:00") == 20  # invoice 7


# --------------------------------------------------------------------------- pure: state machine

def _sub(**over):
    base = {"status": "active", "plan": "creator", "interval": "month",
            "cancel_at_period_end": False, "dispute_open": False, "past_due_since": None}
    base.update(over)
    return base


def test_state_matrix():
    assert subs._state(None, NOW) == "none"
    assert subs._state(_sub(), NOW) == "active"
    assert subs._state(_sub(cancel_at_period_end=True), NOW) == "ending"
    assert subs._state(_sub(status="canceled"), NOW) == "ended"
    assert subs._state(_sub(dispute_open=True), NOW) == "blocked_dispute"
    recent = (NOW - timedelta(days=3)).isoformat()
    old = (NOW - timedelta(days=10)).isoformat()
    assert subs._state(_sub(status="past_due", past_due_since=recent), NOW) == "grace"
    assert subs._state(_sub(status="past_due", past_due_since=old), NOW) == "blocked_payment"
    assert subs._state(_sub(status="incomplete"), NOW) == "blocked_payment"


# --------------------------------------------------------------------------- pure: period bounds

def test_period_bounds_items_then_top():
    assert subs.period_bounds({"current_period_start": 10, "current_period_end": 20}) == (10, 20)
    sub = {"items": {"data": [{"current_period_start": 30, "current_period_end": 40}]}}
    assert subs.period_bounds(sub) == (30, 40)


# --------------------------------------------------------------------------- caps

def test_claim_download_slot_month_then_day_and_rollback():
    db = AsyncDB()
    run(subs.ensure_indexes(db))   # the unique (user_id, period) index is what caps the upsert race
    # month cap 2, day cap 3: third registration in the month is refused, usage not corrupted.
    assert run(subs.claim_download_slot(db, "u", 2, 3, NOW)) == (True, None)
    assert run(subs.claim_download_slot(db, "u", 2, 3, NOW)) == (True, None)
    assert run(subs.claim_download_slot(db, "u", 2, 3, NOW)) == (False, "month_cap")
    assert run(subs._used(db, "u", subs.month_key(NOW))) == 2
    assert run(subs._used(db, "u", subs.day_key(NOW))) == 2   # the failed attempt did not leave a day count


def test_claim_download_slot_day_cap_rolls_back_month():
    db = AsyncDB()
    run(subs.ensure_indexes(db))
    assert run(subs.claim_download_slot(db, "u", 10, 1, NOW)) == (True, None)
    assert run(subs.claim_download_slot(db, "u", 10, 1, NOW)) == (False, "day_cap")
    assert run(subs._used(db, "u", subs.month_key(NOW))) == 1   # rolled back, not 2


# --------------------------------------------------------------------------- plan_access

def test_plan_access_reasons():
    db = AsyncDB()
    db._db.subscriptions.insert_one(_sub(user_id="u", stripe_subscription_id="s1",
                                         created_at=NOW.isoformat()))
    acc = run(subs.plan_access(db, "u", NOW))
    assert acc["state"] == "active" and acc["can_register"] is True and acc["month_cap"] == 100

    db._db.subscriptions.update_one({"user_id": "u"}, {"$set": {"status": "canceled"}})
    assert run(subs.plan_access(db, "u", NOW))["reason"] == "no_plan"

    db2 = AsyncDB()
    assert run(subs.plan_access(db2, "nobody", NOW))["state"] == "none"


def test_plan_access_month_cap_blocks():
    db = AsyncDB()
    db._db.subscriptions.insert_one(_sub(user_id="u", plan="creator", stripe_subscription_id="s1",
                                         created_at=NOW.isoformat()))
    db._db.sub_usage.insert_one({"user_id": "u", "period": subs.month_key(NOW), "count": 100})
    acc = run(subs.plan_access(db, "u", NOW))
    assert acc["can_register"] is False and acc["reason"] == "month_cap"


# --------------------------------------------------------------------------- price cache

def test_load_prices_caches_and_flags_mismatch(caplog):
    correct = {"sub_creator_year": 19000, "sub_pro_month": 4900, "sub_pro_year": 49000,
               "sub_business_month": 14900, "sub_business_year": 149000}

    def _list(params):
        lk = params["lookup_keys"][0]
        amount = 999 if lk == "sub_creator_month" else correct[lk]   # creator_month wrong on purpose
        return ListBox([type("P", (), {"id": f"price_{lk}", "unit_amount": amount})()])
    client = FakeClient(prices=FakeSvc(list=_list))
    with caplog.at_level("ERROR"):
        subs.load_prices(client)
    assert subs.prices_ready() is True
    assert subs.price_id("pro", "month") == "price_sub_pro_month"
    assert any("price mismatch" in r.message and "sub_creator_month" in r.message for r in caplog.records)


# --------------------------------------------------------------------------- accessors vs REAL fixtures

@requires_fixtures
def test_real_subscription_accessors():
    s = fx_obj("customer.subscription.created")
    assert s.get("current_period_start") is None          # basil: moved onto the item
    start, end = subs.period_bounds(s)
    assert isinstance(start, int) and isinstance(end, int) and end > start
    assert subs.sub_item_price_id(s).startswith("price_")


@requires_fixtures
def test_real_invoice_accessors():
    inv = fx_obj("invoice.paid")
    assert "subscription" not in inv                       # basil: no top-level subscription
    assert subs.invoice_subscription_id(inv).startswith("sub_")
    assert isinstance(subs.invoice_tax_cents(inv), int)


@requires_fixtures
def test_charge_invoice_id_resolves_via_invoice_payments():
    # dahlia: neither charge.invoice nor payment_intent.invoice exist; resolution is the paid
    # invoice_payment for the charge's payment_intent (replayed from the recorded response).
    ch = fx_obj("charge.refunded")
    assert not ch.get("invoice") and ch.get("payment_intent")
    rec = _replay()
    expected = rec["invoice_payments.list"][ch["payment_intent"]][0]["invoice"]
    assert run(subs.charge_invoice_id(recording_client(rec), ch)) == expected


def test_charge_invoice_id_legacy_direct():
    # Legacy / pre-basil shape: charge.invoice is present, so no client call is made.
    assert run(subs.charge_invoice_id(None, {"invoice": "in_legacy"})) == "in_legacy"


def test_charge_invoice_id_none_when_no_invoice_payment():
    client = FakeClient(invoice_payments=FakeSvc(list=lambda p: ListBox([])))
    assert run(subs.charge_invoice_id(client, {"id": "ch_x", "payment_intent": "pi_x"})) is None


def test_invoice_subscription_id_legacy_top_level():
    assert subs.invoice_subscription_id({"id": "in_1", "subscription": "sub_legacy"}) == "sub_legacy"


@requires_fixtures
def test_invoice_charge_reads_paid_balance_transaction_fee():
    # Multi-step: the invoice exposes no direct charge; resolve the PAID payment's
    # payment_intent -> latest_charge, then read the balance-transaction fee.
    rec = _replay()
    full = rec["invoices.retrieve"][fx_obj("invoice.paid")["id"]]
    pi = full["payments"]["data"][0]["payment"]["payment_intent"]
    client = recording_client(rec)
    charge_id = run(subs.invoice_charge(client, full))
    assert charge_id == rec["payment_intents.retrieve"][pi]["latest_charge"]
    assert run(subs._charge_fee(client, charge_id)) == 85


def test_invoice_charge_skips_non_paid_payments():
    # Only PAID payments are followed (item 3); a non-paid one must not be looked up.
    inv = {"payments": {"data": [
        {"status": "open", "payment": {"payment_intent": "pi_bad"}},
        {"status": "paid", "payment": {"payment_intent": "pi_good"}}]}}

    def _retrieve(_id, *a):
        assert _id == "pi_good", "a non-paid payment was followed"
        return Box({"latest_charge": "ch_good"})

    client = FakeClient(payment_intents=FakeSvc(retrieve=_retrieve))
    assert run(subs.invoice_charge(client, inv)) == "ch_good"


def test_charge_fee_strict_raises_when_balance_transaction_missing(caplog):
    client = FakeClient(charges=FakeSvc(retrieve=lambda _id: Box({"id": _id, "balance_transaction": None})))
    with caplog.at_level("ERROR"), pytest.raises(RuntimeError):
        run(subs._charge_fee(client, "ch_nobt"))
    assert any("no balance_transaction" in r.message for r in caplog.records)


# --------------------------------------------------------------------------- handler: mirror (real fixture)

@requires_fixtures
def test_mirror_subscription_from_real_created_event():
    db = AsyncDB()
    s = fx_obj("customer.subscription.created")
    # Map the fixture's real price id to a known lookup key so plan/interval resolve.
    subs._PRICE_IDS["sub_creator_month"] = subs.sub_item_price_id(s)
    doc = run(subs.mirror_subscription(db, s, NOW))
    assert doc["plan"] == "creator" and doc["interval"] == "month"
    assert doc["status"] == "active"
    assert doc["user_id"] == (s.get("metadata") or {}).get("user_id")
    assert doc["subscribed_since"] is not None and doc["loyalty_pct"] == 0


# --------------------------------------------------------------------------- handler: payment failed (real fixture)

@requires_fixtures
def test_on_invoice_payment_failed_sets_grace_start():
    db = AsyncDB()
    inv = fx_obj("invoice.payment_failed")
    sid = subs.invoice_subscription_id(inv)
    db._db.subscriptions.insert_one(_sub(stripe_subscription_id=sid, user_id="u", created_at=NOW.isoformat()))
    run(subs.on_invoice_payment_failed(db, inv, NOW))
    doc = db._db.subscriptions.find_one({"stripe_subscription_id": sid})
    assert doc["past_due_since"] == NOW.isoformat()
    # a second failure must not move the grace start
    later = NOW + timedelta(days=1)
    run(subs.on_invoice_payment_failed(db, inv, later))
    assert db._db.subscriptions.find_one({"stripe_subscription_id": sid})["past_due_since"] == NOW.isoformat()


# --------------------------------------------------------------------------- handler: refund voids projects (real fixture)

@requires_fixtures
def test_on_charge_refunded_full_voids_projects():
    db = AsyncDB()
    ch = fx_obj("charge.refunded")
    assert ch.get("refunded") is True
    rec = _replay()
    invoice_id = rec["invoice_payments.list"][ch["payment_intent"]][0]["invoice"]
    refund_amount = rec["refunds.list"][ch["id"]][0]["amount"]
    db._db.licenses.insert_one({"license_id": "OVX-1", "source": "subscription", "invoice_id": invoice_id,
                                "status": "active"})
    out = run(subs.on_charge_refunded(db, recording_client(rec), ch, NOW))
    assert out == invoice_id
    assert db._db.licenses.find_one({"license_id": "OVX-1"})["status"] == "refunded"
    rows = list(db._db.subscription_revenue.find({"kind": "refund"}))
    assert len(rows) == 1 and rows[0]["amount_cents"] == -refund_amount and rows[0]["stripe_fee_cents"] == 0


def test_on_charge_refunded_partial_keeps_projects():
    # Legacy / pre-basil synthetic: charge.invoice is present directly.
    db = AsyncDB()
    ch = {"id": "ch_1", "invoice": "in_sub_123", "payment_intent": "pi_1", "currency": "usd",
          "refunded": False, "amount": 4900, "amount_refunded": 1000}
    invoice_id = "in_sub_123"
    db._db.licenses.insert_one({"license_id": "OVX-2", "source": "subscription", "invoice_id": invoice_id,
                                "status": "active"})
    client = FakeClient(
        invoices=FakeSvc(retrieve=lambda _id, *a: Box(
            {"id": invoice_id, "parent": {"subscription_details": {"subscription": "sub_x"}}})),
        refunds=FakeSvc(list=lambda params: ListBox([Box({"id": "re_1", "amount": 1000})])))
    run(subs.on_charge_refunded(db, client, ch, NOW))
    assert db._db.licenses.find_one({"license_id": "OVX-2"})["status"] == "active"   # not voided


# --------------------------------------------------------------------------- handler: dispute lost (real fixtures)

@requires_fixtures
def test_on_dispute_lost_voids_and_charges_fee():
    db = AsyncDB()
    dc = fx_obj("charge.dispute.closed")
    assert dc.get("status") == "lost"
    rec = _replay()
    pi = rec["charges.retrieve"][dc["charge"]]["payment_intent"]
    invoice_id = rec["invoice_payments.list"][pi][0]["invoice"]
    sub_id = subs.invoice_subscription_id(rec["invoices.retrieve"][invoice_id])
    db._db.licenses.insert_one({"license_id": "OVX-3", "source": "subscription", "invoice_id": invoice_id,
                                "status": "active"})
    db._db.subscriptions.insert_one(_sub(stripe_subscription_id=sub_id, user_id="u",
                                         created_at=NOW.isoformat()))
    out = run(subs.on_dispute(db, recording_client(rec), dc, NOW, closed=True))
    assert out == invoice_id
    assert db._db.licenses.find_one({"license_id": "OVX-3"})["status"] == "refunded"
    assert db._db.subscriptions.find_one({"stripe_subscription_id": sub_id})["dispute_open"] is False
    row = db._db.subscription_revenue.find_one({"kind": "dispute_lost"})
    expected_fee = sum(int(bt.get("fee") or 0) for bt in (dc.get("balance_transactions") or []))
    assert row is not None and row["amount_cents"] == -dc["amount"] and row["stripe_fee_cents"] == expected_fee


# --------------------------------------------------------------------------- handler: checkout completed (synthetic)

def test_on_checkout_completed_links_customer_and_mirrors():
    db = AsyncDB()
    subs._PRICE_IDS["sub_creator_month"] = "price_creator_m"
    sub_obj = {"id": "sub_new", "status": "active", "customer": "cus_1",
               "cancel_at_period_end": False, "latest_invoice": "in_1",
               "current_period_start": 1800000000, "current_period_end": 1802592000,
               "items": {"data": [{"price": {"id": "price_creator_m"}}]},
               "metadata": {"user_id": "user_x"}}
    client = FakeClient(subscriptions=FakeSvc(
        retrieve=lambda _id: Box(sub_obj),
        update=lambda _id, params: Box(sub_obj)))
    session = {"mode": "subscription", "subscription": "sub_new", "customer": "cus_1",
               "client_reference_id": "user_x"}
    run(subs.on_checkout_completed(db, client, session, NOW))
    prof = db._db.buyer_profiles.find_one({"user_id": "user_x"})
    assert prof["stripe_customer_id"] == "cus_1"
    doc = db._db.subscriptions.find_one({"stripe_subscription_id": "sub_new"})
    assert doc["plan"] == "creator" and doc["user_id"] == "user_x"


# --------------------------------------------------------------------------- loyalty apply (synthetic)

def test_apply_loyalty_sets_coupon_at_month_three():
    db = AsyncDB()
    updates = []
    client = FakeClient(subscriptions=FakeSvc(update=lambda _id, params: updates.append(params) or Box({})))
    sub_doc = {"stripe_subscription_id": "s1", "interval": "month", "loyalty_pct": 0,
               "subscribed_since": "2026-01-01T00:00:00+00:00",
               "current_period_end": "2026-03-01T00:00:00+00:00"}   # upcoming invoice is #3 -> 15%
    db._db.subscriptions.insert_one(dict(sub_doc))
    run(subs.apply_loyalty(db, client, sub_doc, NOW))
    assert updates == [{"discounts": [{"coupon": "LOYALTY15"}]}]
    assert db._db.subscriptions.find_one({"stripe_subscription_id": "s1"})["loyalty_pct"] == 15


def test_apply_loyalty_annual_clears_any_coupon():
    db = AsyncDB()
    updates = []
    client = FakeClient(subscriptions=FakeSvc(update=lambda _id, params: updates.append(params) or Box({})))
    sub_doc = {"stripe_subscription_id": "s1", "interval": "year", "loyalty_pct": 15,
               "subscribed_since": "2026-01-01T00:00:00+00:00", "current_period_end": None}
    db._db.subscriptions.insert_one(dict(sub_doc))
    run(subs.apply_loyalty(db, client, sub_doc, NOW))
    assert updates == [{"discounts": []}]
    assert db._db.subscriptions.find_one({"stripe_subscription_id": "s1"})["loyalty_pct"] == 0


# --------------------------------------------------------------------------- endpoints: gate (9a) + dup guard (9b)

def test_sub_gate_admin_only_while_single_track_checkout_closed(monkeypatch):
    import fastapi
    import server

    async def _ready():
        return True

    monkeypatch.setattr(server, "_subscriptions_ready", _ready)
    monkeypatch.delenv("SYNC_CHECKOUT_ENABLED", raising=False)      # public checkout still closed
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    with pytest.raises(fastapi.HTTPException) as ei:
        run(server._sub_gate({"metadata": {"role": "artist"}}))
    assert ei.value.status_code == 403
    run(server._sub_gate({"metadata": {"role": "admin"}}))          # admin with a test key passes


def test_register_duplicate_guard_normalizes_project(monkeypatch):
    import server
    import sync_orders as so
    from fastapi.testclient import TestClient

    db = AsyncDB()
    db._db.licenses.insert_one(
        {"license_id": "OVX-DUP", "source": "subscription", "owner_user_id": "u", "track_id": "t1",
         "created_at": datetime.now(timezone.utc).isoformat(), "project": {"name": "My  Project"},
         "track_title": "T", "license_label": "Pro plan"})

    async def _ready():
        return True

    monkeypatch.setattr(server, "db", db)
    monkeypatch.setattr(server, "_subscriptions_ready", _ready)
    monkeypatch.setattr(server.limiter, "enabled", False)
    monkeypatch.setenv("SYNC_CHECKOUT_ENABLED", "true")            # pass the admin gate for any role
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("SYNC_TOKEN_SECRET", "s" * 64)
    server.app.dependency_overrides[server.verify_clerk_token] = lambda: {"sub": "u", "metadata": {"role": "artist"}}
    try:
        resp = TestClient(server.app).post("/api/subscriptions/register", json={
            "track_id": "t1", "project_name": "my project", "project_client": "",
            "include_stems": False, "accept_terms": True, "terms_version": so.terms_version()})
        assert resp.status_code == 200, resp.text
        assert resp.json()["license_id"] == "OVX-DUP"            # same user+track+normalized name
        assert db._db.sub_usage.count_documents({}) == 0         # no new slot consumed
    finally:
        server.app.dependency_overrides.clear()
