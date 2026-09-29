"""PRD-03 Phase 6a: orders, download tokens, status transitions and indexes (sync_orders.py).

Runs against mongomock through a thin async adapter, so the conditional
updates behave like real MongoDB. Requires mongomock (requirements-dev.txt).
"""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest

mongomock = pytest.importorskip("mongomock")

import sync_orders as so  # noqa: E402

NOW = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
SECRET = "s" * 64


class AsyncCollection:
    def __init__(self, coll):
        self._c = coll

    async def update_one(self, *a, **k):
        return self._c.update_one(*a, **k)

    async def find_one(self, *a, **k):
        return self._c.find_one(*a, **k)

    async def insert_one(self, *a, **k):
        return self._c.insert_one(*a, **k)

    async def create_index(self, keys, **k):
        k.pop("partialFilterExpression", None)  # mongomock ignores it; see test note
        return self._c.create_index(keys, **k)


class AsyncDB:
    def __init__(self):
        self._db = mongomock.MongoClient().db

    def __getattr__(self, name):
        return AsyncCollection(self._db[name])


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def env(monkeypatch):
    for name in ("SYNC_DELIVER_STEMS", "SYNC_DOWNLOAD_TTL_DAYS", "SYNC_TERMS_VERSION", "SYNC_PRICE_CREATOR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SYNC_TOKEN_SECRET", SECRET)


TRACK = {"id": "t1", "clerk_user_id": "user_artist", "mastered_r2_key": "catalog/a/b/mastered/t1.wav",
         "stem_paths": {n: f"catalog/a/b/stems/t1/{n}.wav" for n in so.STEM_NAMES}}


def order(**over):
    o = so.build_order(track=TRACK, tier="creator", include_stems=over.pop("include_stems", True),
                       buyer_name="Buyer", buyer_company="", buyer_email="b@example.com",
                       test_mode=True, now=NOW)
    o.update(over)
    return o


def test_build_order_prices_server_side():
    o = order()
    assert o["price_cents"] == 2300 and o["status"] == "pending" and o["artist_user_id"] == "user_artist"
    assert o["terms_version"] == "draft-0" and o["license_id"].startswith("OVX-") and len(o["license_id"]) == 14


def test_stems_refused_when_switched_off(monkeypatch):
    monkeypatch.setenv("SYNC_DELIVER_STEMS", "false")
    with pytest.raises(ValueError):
        order(include_stems=True)
    assert order(include_stems=False)["price_cents"] == 1900


def test_token_is_deterministic_and_version_bound():
    t1 = so.derive_token("o1", 1)
    assert t1 == so.derive_token("o1", 1)
    assert t1 != so.derive_token("o1", 2) and t1 != so.derive_token("o2", 1)
    assert len(t1) == 43 and "=" not in t1


def test_token_depends_on_secret(monkeypatch):
    t1 = so.derive_token("o1", 1)
    monkeypatch.setenv("SYNC_TOKEN_SECRET", "t" * 64)
    assert so.derive_token("o1", 1) != t1


def test_full_lifecycle_and_idempotent_transitions():
    db = AsyncDB()
    o = order()
    run(db.orders.insert_one(dict(o)))
    oid = o["order_id"]
    assert run(so.mark_paid(db, oid, payment_intent="pi_1", tax_cents=150, amount_total_cents=2450, now=NOW))
    assert not run(so.mark_paid(db, oid, payment_intent="pi_1", tax_cents=150, amount_total_cents=2450, now=NOW))
    assert run(so.mark_fulfilled(db, oid, license_pdf_key="licenses/x.pdf", now=NOW))
    assert not run(so.mark_fulfilled(db, oid, license_pdf_key="licenses/x.pdf", now=NOW))
    saved = run(db.orders.find_one({"order_id": oid}))
    assert saved["status"] == "fulfilled" and saved["tax_cents"] == 150 and saved["price_cents"] == 2300
    token = so.current_token(saved)
    assert saved["download_token_hash"] == so.hash_token(token)
    assert run(so.find_by_token(db, token, now=NOW))["order_id"] == oid


def test_fulfil_requires_paid_and_failed_requires_pending():
    db = AsyncDB()
    o = order()
    run(db.orders.insert_one(dict(o)))
    assert not run(so.mark_fulfilled(db, o["order_id"], license_pdf_key="k", now=NOW))
    assert run(so.mark_failed(db, o["order_id"], now=NOW))
    assert not run(so.mark_paid(db, o["order_id"], payment_intent="pi", tax_cents=0,
                                amount_total_cents=0, now=NOW))


def test_token_expiry_and_refund_block_lookup():
    db = AsyncDB()
    o = order()
    run(db.orders.insert_one(dict(o)))
    run(so.mark_paid(db, o["order_id"], payment_intent="pi", tax_cents=0, amount_total_cents=2300, now=NOW))
    run(so.mark_fulfilled(db, o["order_id"], license_pdf_key="k", now=NOW))
    token = so.derive_token(o["order_id"], 1)
    assert run(so.find_by_token(db, token, now=NOW + timedelta(days=29)))
    assert run(so.find_by_token(db, token, now=NOW + timedelta(days=30))) is None
    run(db.orders.update_one({"order_id": o["order_id"]}, {"$set": {"status": "refunded"}}))
    assert run(so.find_by_token(db, token, now=NOW)) is None


def test_unknown_or_oversized_token():
    db = AsyncDB()
    assert run(so.find_by_token(db, "nope", now=NOW)) is None
    assert run(so.find_by_token(db, "x" * 500, now=NOW)) is None


def test_reissue_kills_old_link_and_resets_counts():
    db = AsyncDB()
    o = order()
    run(db.orders.insert_one(dict(o)))
    run(so.mark_paid(db, o["order_id"], payment_intent="pi", tax_cents=0, amount_total_cents=2300, now=NOW))
    run(so.mark_fulfilled(db, o["order_id"], license_pdf_key="k", now=NOW))
    old = so.derive_token(o["order_id"], 1)
    run(db.orders.update_one({"order_id": o["order_id"]}, {"$set": {"download_counts": {"master": 10}}}))
    new = run(so.reissue_token(db, o["order_id"], now=NOW + timedelta(days=40)))
    assert new and new != old
    assert run(so.find_by_token(db, old, now=NOW + timedelta(days=40))) is None
    found = run(so.find_by_token(db, new, now=NOW + timedelta(days=40)))
    assert found["download_counts"] == {} and found["token_version"] == 2


def test_reissue_refused_unless_fulfilled():
    db = AsyncDB()
    o = order()
    run(db.orders.insert_one(dict(o)))
    assert run(so.reissue_token(db, o["order_id"], now=NOW)) is None


def test_delivery_files_with_and_without_stems():
    o = order(license_pdf_key="licenses/x.pdf")
    files = so.delivery_files(o, TRACK)
    assert set(files) == {"license", "master", *so.STEM_NAMES}
    o2 = order(include_stems=False, license_pdf_key="licenses/x.pdf")
    assert set(so.delivery_files(o2, TRACK)) == {"license", "master"}


def test_delivery_honours_purchase_even_if_stems_switched_off_later(monkeypatch):
    o = order(license_pdf_key="licenses/x.pdf")
    monkeypatch.setenv("SYNC_DELIVER_STEMS", "false")
    assert "vocals" in so.delivery_files(o, TRACK)


def test_delivery_missing_file_raises():
    o = order(license_pdf_key="licenses/x.pdf")
    track = dict(TRACK, stem_paths={"vocals": "k"})
    with pytest.raises(so.DeliveryError, match="bass"):
        so.delivery_files(o, track)


def test_unique_order_and_event_indexes():
    db = AsyncDB()
    run(so.ensure_indexes(db))
    run(db.stripe_events.insert_one({"event_id": "evt_1"}))
    with pytest.raises(Exception):
        run(db.stripe_events.insert_one({"event_id": "evt_1"}))
