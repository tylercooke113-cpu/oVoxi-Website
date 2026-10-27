"""Brief 27 Part E: single-track chargebacks per License Terms A13."""
from datetime import datetime, timezone

import pytest

import licenses
import sync_orders
import wallet
from test_subscriptions import AsyncDB, run

NOW = datetime(2026, 11, 20, tzinfo=timezone.utc)


@pytest.fixture
def db():
    d = AsyncDB()
    run(wallet.ensure_indexes(d))
    run(d.orders.insert_one({"order_id": "o1", "track_id": "t1", "stripe_payment_intent": "pi_1", "status": "fulfilled",
                             "artist_user_id": "user_a", "amount_total_cents": 10000, "tax_cents": 0,
                             "paid_at": "2026-11-02T00:00:00+00:00", "test_mode": False}))
    run(d.licenses.insert_one({"order_id": "o1", "license_id": "OVX-1", "status": "active"}))
    run(d.sync_profiles.insert_one({"user_id": "user_a", "sales_count": 1}))
    run(d.track_submissions.insert_one({"id": "t1", "clerk_user_id": "user_a", "rights": {"owns_everything": True}}))
    return d


def dispute(status="needs_response"):
    return {"id": "dp_1", "payment_intent": "pi_1", "status": status}


def state(db):
    return run(db.orders.find_one({"order_id": "o1"}))["status"], run(db.licenses.find_one({}))["status"]


def test_open_dispute_suspends_the_license_and_downloads(db):
    out = run(sync_orders.apply_dispute(db, dispute(), closed=False, now=NOW))
    assert out["dispute_outcome"] == "open"
    assert state(db) == ("disputed", "suspended")
    assert run(sync_orders.find_by_token(db, "anything", now=NOW)) is None          # only fulfilled orders download
    assert licenses.display_status(run(db.licenses.find_one({})), NOW) == "suspended"


def test_won_dispute_restores_everything(db):
    run(sync_orders.apply_dispute(db, dispute(), closed=False, now=NOW))
    out = run(sync_orders.apply_dispute(db, dispute("won"), closed=True, now=NOW))
    assert out["dispute_outcome"] == "won" and state(db) == ("fulfilled", "active")


def test_lost_dispute_ends_the_license_and_reverses_the_wallet(db):
    order = run(db.orders.find_one({"order_id": "o1"}, {"_id": 0}))
    track = run(db.track_submissions.find_one({"id": "t1"}, {"_id": 0}))
    run(wallet.credit_order(db, order, track, fee_cents=320, now=NOW))
    run(sync_orders.apply_dispute(db, dispute(), closed=False, now=NOW))
    out = run(sync_orders.apply_dispute(db, dispute("lost"), closed=True, now=NOW))
    assert out["dispute_outcome"] == "lost" and state(db) == ("refunded", "void")
    run(wallet.reverse_order(db, out, kind="dispute", refunded_cents=0, now=NOW))
    run(wallet.reverse_order(db, out, kind="dispute", refunded_cents=0, now=NOW))     # replayed event
    rows = run(db.wallet_entries.find({}, {"_id": 0}).to_list(10))
    assert sum(r["amount_cents"] for r in rows) == 0 and len(rows) == 2
    assert run(db.sync_profiles.find_one({}))["sales_count"] == 0


def test_not_a_single_track_charge(db):
    assert run(sync_orders.apply_dispute(db, {"id": "dp", "payment_intent": "pi_other"}, closed=False, now=NOW)) is None


def test_dispute_on_a_refunded_order_changes_nothing(db):
    run(db.orders.update_one({"order_id": "o1"}, {"$set": {"status": "refunded"}}))
    run(sync_orders.apply_dispute(db, dispute(), closed=False, now=NOW))
    assert state(db) == ("refunded", "active")
