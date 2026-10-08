"""PRD-03 Phase 6a: Stripe webhook, fulfilment and refunds.

Events are signed exactly as Stripe signs them (HMAC-SHA256 over "t.payload"),
so signature verification runs for real. R2 is replaced by a recorder.
"""
import asyncio
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("mongomock")
pytest.importorskip("stripe")

import server  # noqa: E402
import sync_orders as so  # noqa: E402
from test_checkout import LISTED  # noqa: E402
from test_sync_orders import AsyncDB  # noqa: E402

WHSEC = "whsec_test_secret"
STEMS = {n: f"catalog/a/b/stems/t1/{n}.wav" for n in so.STEM_NAMES}


def sign(payload: str, secret: str = WHSEC, t: int | None = None) -> str:
    t = t or int(time.time())
    sig = hmac.new(secret.encode(), f"{t}.{payload}".encode(), hashlib.sha256).hexdigest()
    return f"t={t},v1={sig}"


def event(etype, obj, eid="evt_1"):
    return json.dumps({"id": eid, "object": "event", "type": etype, "data": {"object": obj}})


def session(order, **over):
    s = {"id": "cs_test_123", "object": "checkout.session", "payment_status": "paid",
         "metadata": {"order_id": order["order_id"]}, "payment_intent": "pi_1",
         "amount_subtotal": order["price_cents"], "amount_total": order["price_cents"] + 420,
         "total_details": {"amount_tax": 420}}
    s.update(over)
    return s


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", WHSEC)
    monkeypatch.setenv("SYNC_TOKEN_SECRET", "s" * 64)
    for name in ("SYNC_DELIVER_STEMS", "SYNC_TERMS_VERSION"):
        monkeypatch.delenv(name, raising=False)
    db = AsyncDB()
    db._db.track_submissions.insert_one(dict(LISTED, stem_paths=STEMS))
    db._db.sync_profiles.insert_one({"user_id": "user_artist", "display_name": "Kay Lune", "sales_count": 0})
    order = so.build_order(track=LISTED, tier="creator", include_stems=True, buyer_name="Dana",
                           buyer_company="", buyer_email="d@example.com", test_mode=False,
                           now=datetime.now(timezone.utc),
                           artist_display_name="Kay Lune")
    order["stripe_session_id"] = "cs_test_123"
    db._db.orders.insert_one(dict(order))
    puts = []

    async def fake_put(key, data, content_type):
        puts.append((key, data[:5], content_type))

    monkeypatch.setattr(server, "db", db)
    monkeypatch.setattr(server, "_r2_put", fake_put)
    client = TestClient(server.app)

    def post(etype, obj, eid="evt_1", sig=None):
        body = event(etype, obj, eid)
        return client.post("/api/stripe/webhook", content=body,
                           headers={"stripe-signature": sig or sign(body), "content-type": "application/json"})

    yield SimpleNamespace(db=db, order=order, puts=puts, post=post)


def get(env):
    return env.db._db.orders.find_one({"order_id": env.order["order_id"]}, {"_id": 0})


def sales(env):
    return env.db._db.sync_profiles.find_one({"user_id": "user_artist"})["sales_count"]


def test_completed_pays_and_fulfils(env):
    r = env.post("checkout.session.completed", session(env.order))
    assert r.status_code == 200, r.text
    o = get(env)
    assert o["status"] == "fulfilled" and o["tax_cents"] == 420 and o["amount_total_cents"] == 2720
    assert o["stripe_payment_intent"] == "pi_1" and o["email_status"] == "skipped"
    assert o["license_pdf_key"] == f"licenses/{o['order_id']}/{o['license_id']}.pdf"
    assert env.puts == [(o["license_pdf_key"], b"%PDF-", "application/pdf")]
    assert so.current_token(o) and sales(env) == 1
    assert env.db._db.stripe_events.count_documents({"event_id": "evt_1"}) == 1


def test_bad_signature_rejected(env):
    body = event("checkout.session.completed", session(env.order))
    assert env.post("checkout.session.completed", session(env.order),
                    sig=sign(body, secret="whsec_wrong")).status_code == 400
    assert env.post("checkout.session.completed", session(env.order), sig="garbage").status_code == 400
    assert get(env)["status"] == "pending"


def test_stale_timestamp_rejected(env):
    body = event("checkout.session.completed", session(env.order))
    old = sign(body, t=int(time.time()) - 3600)
    assert env.post("checkout.session.completed", session(env.order), sig=old).status_code == 400


def test_missing_webhook_secret_is_503(env, monkeypatch):
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET")
    assert env.post("checkout.session.completed", session(env.order)).status_code == 503


def test_duplicate_event_is_noop(env):
    env.post("checkout.session.completed", session(env.order))
    r = env.post("checkout.session.completed", session(env.order))
    assert r.json().get("duplicate") is True and len(env.puts) == 1 and sales(env) == 1


def test_same_session_new_event_id_does_not_double_fulfil(env):
    env.post("checkout.session.completed", session(env.order), eid="evt_1")
    env.post("checkout.session.async_payment_succeeded", session(env.order), eid="evt_2")
    assert len(env.puts) == 1 and sales(env) == 1


def test_unpaid_completed_waits_for_async_success(env):
    env.post("checkout.session.completed", session(env.order, payment_status="unpaid"), eid="evt_1")
    assert get(env)["status"] == "pending"
    env.post("checkout.session.async_payment_succeeded", session(env.order), eid="evt_2")
    assert get(env)["status"] == "fulfilled"


def test_session_id_mismatch_ignored(env):
    env.post("checkout.session.completed", session(env.order, id="cs_other"))
    assert get(env)["status"] == "pending"


def test_amount_mismatch_flagged_but_delivered(env):
    env.post("checkout.session.completed", session(env.order, amount_subtotal=1))
    o = get(env)
    assert o["amount_mismatch"] is True and o["status"] == "fulfilled"


def test_expired_marks_failed(env):
    env.post("checkout.session.expired", session(env.order, payment_status="unpaid"))
    assert get(env)["status"] == "failed"


def test_missing_stem_leaves_order_paid_for_retry(env):
    env.db._db.track_submissions.update_one({"id": "t1"}, {"$unset": {"stem_paths.bass": ""}})
    r = env.post("checkout.session.completed", session(env.order))
    assert r.status_code == 200 and get(env)["status"] == "paid" and env.puts == [] and sales(env) == 0


def test_single_track_refund_skips_subscription_path(env, monkeypatch):
    """A refund that matches a single-track order must not touch the subscription path:
    on_charge_refunded (and therefore invoice_payments.list) is never called."""
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    calls = []

    class _IP:
        def list(self, *a, **k):
            calls.append((a, k))
            raise AssertionError("invoice_payments.list must not run for a single-track refund")

    class _FakeClient:
        v1 = SimpleNamespace(invoice_payments=_IP())

    monkeypatch.setattr(so, "stripe_client", lambda: _FakeClient())
    env.db._db.orders.update_one({"order_id": env.order["order_id"]},
                                 {"$set": {"stripe_payment_intent": "pi_single", "status": "fulfilled"}})
    charge = {"id": "ch_single", "payment_intent": "pi_single", "currency": "usd",
              "refunded": True, "amount": 4900, "amount_refunded": 4900}
    r = env.post("charge.refunded", charge, eid="evt_refund_single")
    assert r.status_code == 200, r.text
    assert calls == []                                   # subscription path skipped entirely
    assert get(env)["status"] == "refunded"


def test_subscription_lookup_exception_returns_500_and_not_recorded(env, monkeypatch):
    """A Stripe lookup failure inside a subscription handler must 500 (so Stripe retries) and
    leave the event unrecorded, since the event id is only stored after the handlers succeed."""
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")

    class _Boom:
        def list(self, *a, **k):
            raise RuntimeError("stripe lookup down")

    class _FakeClient:
        v1 = SimpleNamespace(invoice_payments=_Boom())

    monkeypatch.setattr(so, "stripe_client", lambda: _FakeClient())
    charge = {"id": "ch_boom", "payment_intent": "pi_boom", "currency": "usd",
              "refunded": True, "amount": 4900, "amount_refunded": 4900}
    body = event("charge.refunded", charge, eid="evt_boom")
    client = TestClient(server.app, raise_server_exceptions=False)
    r = client.post("/api/stripe/webhook", content=body,
                    headers={"stripe-signature": sign(body), "content-type": "application/json"})
    assert r.status_code == 500
    assert env.db._db.stripe_events.count_documents({"event_id": "evt_boom"}) == 0


def test_test_mode_orders_do_not_count_as_sales(env):
    env.db._db.orders.update_one({"order_id": env.order["order_id"]}, {"$set": {"test_mode": True}})
    env.post("checkout.session.completed", session(env.order))
    assert get(env)["status"] == "fulfilled" and sales(env) == 0


def charge(**over):
    c = {"id": "ch_1", "object": "charge", "payment_intent": "pi_1", "amount": 2720,
         "amount_refunded": 2720, "refunded": True}
    c.update(over)
    return c


def test_full_refund_revokes_and_decrements(env):
    env.post("checkout.session.completed", session(env.order), eid="evt_1")
    token = so.current_token(get(env))
    env.post("charge.refunded", charge(), eid="evt_2")
    o = get(env)
    assert o["status"] == "refunded" and o["refunds"][0]["full"] is True and sales(env) == 0
    assert asyncio.run(so.find_by_token(env.db, token, now=datetime.now(timezone.utc))) is None


def test_partial_refund_only_logged(env):
    env.post("checkout.session.completed", session(env.order), eid="evt_1")
    env.post("charge.refunded", charge(amount_refunded=500, refunded=False), eid="evt_2")
    o = get(env)
    assert o["status"] == "fulfilled" and o["refunds"] == [
        {"amount_refunded_cents": 500, "full": False, "at": o["refunds"][0]["at"]}] and sales(env) == 1


def test_sales_count_never_negative(env):
    env.post("checkout.session.completed", session(env.order), eid="evt_1")
    env.db._db.sync_profiles.update_one({"user_id": "user_artist"}, {"$set": {"sales_count": 0}})
    env.post("charge.refunded", charge(), eid="evt_2")
    assert sales(env) == 0


def test_unhandled_event_type_ignored(env):
    r = env.post("customer.created", {"id": "cus_1", "object": "customer"})
    assert r.status_code == 200 and r.json()["ignored"] == "customer.created"
