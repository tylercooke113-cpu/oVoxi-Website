"""Brief 17: license records, account + verify endpoints, and the fulfilment reconciler.

Runs against mongomock through a thin async adapter so conditional updates, unique
indexes, $lt/$or filters and modified_count behave like real MongoDB.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

mongomock = pytest.importorskip("mongomock")

import licenses as lic_mod  # noqa: E402
import server  # noqa: E402
import sync_orders as so  # noqa: E402

NOW = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
OLD = NOW - timedelta(minutes=5)   # older than FULFIL_MIN_AGE_MIN
UID = "user_buyer"


# --------------------------------------------------------------------------- harness

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

    async def insert_one(self, *a, **k):
        return self._c.insert_one(*a, **k)

    async def update_one(self, *a, **k):
        return self._c.update_one(*a, **k)

    async def update_many(self, *a, **k):
        return self._c.update_many(*a, **k)

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


TRACK = {
    "id": "t1", "track_name": "Golden Hour", "artist_name": "J Riv", "clerk_user_id": "user_artist",
    "mastered_r2_key": "catalog/a/b/mastered/t1.wav",
    "stem_paths": {n: f"catalog/a/b/stems/t1/{n}.wav" for n in so.STEM_NAMES},
    "rights": {
        "writers": [{"legal_name": "Jordan Rivera", "ipi_name_number": "00123456789", "society": "ASCAP"}],
        "publishers": [{"legal_name": "Rivera Songs", "ipi_name_number": None, "society": None}],
        "master_owners": [{"legal_name": "Jordan Rivera", "ipi_name_number": None, "society": None}],
    },
}


def make_order(**over):
    o = so.build_order(track=TRACK, tier="creator", include_stems=False, buyer_name="Dana Buyer",
                       buyer_company="Rivera Studio", buyer_email="Dana@Example.com", test_mode=True, now=NOW,
                       track_title="Golden Hour", artist_display_name="J. Riv",
                       project_name="Nike Summer teaser", project_client="Nike")
    o.update(over)
    return o


@pytest.fixture(autouse=True)
def secret(monkeypatch):
    monkeypatch.setenv("SYNC_TOKEN_SECRET", "s" * 64)
    monkeypatch.delenv("SYNC_TERMS_VERSION", raising=False)
    monkeypatch.delenv("SYNC_DELIVER_STEMS", raising=False)


# --------------------------------------------------------------------------- pure functions

def test_build_license_from_order():
    lic = lic_mod.build_license_from_order(make_order(), TRACK, NOW)
    assert lic["buyer_email"] == "dana@example.com"  # lowercased
    assert lic["project"] == {"name": "Nike Summer teaser", "client": "Nike"}
    assert lic["licensee_name"] == "Dana Buyer" and lic["licensee_company"] == "Rivera Studio"
    assert lic["source"] == "order" and lic["owner_user_id"] is None and lic["status"] == "active"
    assert lic["license_label"] == "Creator license" and lic["track_title"] == "Golden Hour"
    assert len(lic["cue_sheet"]) == 3


def test_build_cue_sheet():
    cs = lic_mod.build_cue_sheet(TRACK)
    assert [c["role"] for c in cs] == ["Writer", "Publisher", "Master owner"]
    assert [c["society"] for c in cs] == ["ASCAP", "Not affiliated", "Not affiliated"]
    assert cs[0]["ipi"] == "00123456789" and cs[1]["ipi"] == ""


def test_display_status():
    base = lic_mod.build_license_from_order(make_order(test_mode=False), TRACK, NOW)
    assert lic_mod.display_status(base, NOW) == "active"
    assert lic_mod.display_status({**base, "status": "refunded"}, NOW) == "refunded"
    assert lic_mod.display_status({**base, "status": "void"}, NOW) == "void"
    assert lic_mod.display_status({**base, "test_mode": True}, NOW) == "test"
    past = {**base, "scope": {**base["scope"], "term_end": (NOW - timedelta(days=1)).isoformat()}}
    assert lic_mod.display_status(past, NOW) == "expired"


def test_public_view_allowlist():
    lic = lic_mod.build_license_from_order(make_order(test_mode=False), TRACK, NOW)
    pv = lic_mod.public_view(lic, NOW)
    assert set(pv) == {"license_id", "track_title", "artist_display_name", "license_label", "licensed_to",
                       "project_name", "territory", "term_label", "term_end", "issued_at", "terms_version",
                       "status", "refunded_at"}
    assert pv["licensed_to"] == "Rivera Studio"
    for leaked in ("buyer_email", "client", "cue_sheet", "media_spend_cap_cents", "include_stems"):
        assert leaked not in pv


# --------------------------------------------------------------------------- HTTP: account + verify

@pytest.fixture
def api(monkeypatch):
    db = AsyncDB()
    run(lic_mod.ensure_indexes(db))
    monkeypatch.setattr(server, "db", db)
    monkeypatch.setattr(server.limiter, "enabled", False)
    r2 = MagicMock()
    r2.generate_presigned_url.return_value = "https://r2.test/signed"
    monkeypatch.setattr(server, "r2_client", r2)
    server.app.dependency_overrides[server.verify_clerk_token] = lambda: {"sub": UID}
    yield db
    server.app.dependency_overrides.clear()


def client():
    return TestClient(server.app)


def seed_license(db, **over):
    lic = lic_mod.build_license_from_order(make_order(), TRACK, NOW)
    lic.update(over)
    db._db.licenses.insert_one(dict(lic))
    return lic


def test_account_links_verified_email(api, monkeypatch):
    seed_license(api, buyer_email="buyer@x.com", owner_user_id=None)
    monkeypatch.setattr(server, "fetch_clerk_user",
                        AsyncMock(return_value={"email": "Buyer@X.com", "email_verified": True,
                                                "first_name": "B", "last_name": "Uyer"}))
    body = client().get("/api/account/licenses").json()
    assert body["linking"] == "ok" and len(body["licenses"]) == 1
    assert api._db.licenses.find_one({})["owner_user_id"] == UID


def test_account_unverified_email_no_link(api, monkeypatch):
    seed_license(api, buyer_email="buyer@x.com", owner_user_id=None)
    monkeypatch.setattr(server, "fetch_clerk_user",
                        AsyncMock(return_value={"email": "buyer@x.com", "email_verified": False,
                                                "first_name": "", "last_name": ""}))
    body = client().get("/api/account/licenses").json()
    assert body["linking"] == "ok" and body["licenses"] == []
    assert api._db.licenses.find_one({})["owner_user_id"] is None


def test_account_clerk_failure_returns_linked_only(api, monkeypatch):
    seed_license(api, owner_user_id=UID)
    from fastapi import HTTPException
    monkeypatch.setattr(server, "fetch_clerk_user", AsyncMock(side_effect=HTTPException(status_code=503)))
    body = client().get("/api/account/licenses").json()
    assert body["linking"] == "unavailable" and len(body["licenses"]) == 1


def test_certificate_non_owner_is_404(api, monkeypatch):
    lic = seed_license(api, owner_user_id="someone_else", pdf_key="licenses/x/y.pdf")
    monkeypatch.setattr(server, "fetch_clerk_user", AsyncMock(return_value={"email": "", "email_verified": False}))
    assert client().get(f"/api/account/licenses/{lic['license_id']}/certificate").status_code == 404


def test_files_on_refunded_is_409(api, monkeypatch):
    lic = seed_license(api, owner_user_id=UID, status="refunded")
    monkeypatch.setattr(server, "fetch_clerk_user", AsyncMock(return_value={"email": "", "email_verified": False}))
    assert client().post(f"/api/account/licenses/{lic['license_id']}/files/master").status_code == 409


@pytest.mark.parametrize("lid", ["abc", "OVX-shorty", "OVX-IIIIIIIIII", "notanid"])
def test_verify_bad_format_404(api, lid):
    assert client().get(f"/api/verify/{lid}").status_code == 404


def test_verify_unknown_404(api):
    assert client().get("/api/verify/OVX-AAAAAAAAAA").status_code == 404


def test_verify_active_refunded_test(api):
    active = seed_license(api, test_mode=False)
    refunded = seed_license(api, test_mode=False, status="refunded",
                            refunded_at=NOW.isoformat(), license_id=so.new_license_id())
    test = seed_license(api, test_mode=True, license_id=so.new_license_id())

    a = client().get(f"/api/verify/{active['license_id']}").json()
    assert a["status"] == "active" and a["licensed_to"] == "Rivera Studio" and "buyer_email" not in a
    assert client().get(f"/api/verify/{refunded['license_id']}").json()["status"] == "refunded"
    assert client().get(f"/api/verify/{test['license_id']}").json()["status"] == "test"


def test_checkout_without_project_name_is_422():
    base = {"track_id": "t1", "tier": "creator", "include_stems": False, "buyer_name": "B",
            "buyer_email": "b@example.com", "accept_terms": True, "terms_version": "draft-0"}
    with pytest.raises(Exception):
        server.CheckoutRequest(**base)                      # missing project_name
    with pytest.raises(Exception):
        server.CheckoutRequest(**base, project_name="   ")  # blank after cleaning


# --------------------------------------------------------------------------- fulfilment + reconciler

async def _pdf(order, title, artist, lic=None):
    return b"%PDF-reconcile"


async def _put(key, data, ct):
    return None


def paid_order(db, **over):
    o = make_order(status="paid", paid_at=OLD.isoformat(), **over)
    db._db.orders.insert_one(dict(o))
    db._db.track_submissions.insert_one(dict(TRACK)) if not db._db.track_submissions.find_one({"id": "t1"}) else None
    return o


def test_license_insert_failure_leaves_order_paid(monkeypatch):
    class _FailLicenses(AsyncCollection):
        async def insert_one(self, *a, **k):
            raise RuntimeError("licenses down")

    class FailDB(AsyncDB):
        def __getattr__(self, name):
            if name == "licenses":
                return _FailLicenses(self._db[name])
            return AsyncCollection(self._db[name])

    db = FailDB()
    o = paid_order(db)
    with pytest.raises(RuntimeError):
        run(so.fulfil_order(db, o["order_id"], render_pdf=_pdf, put_object=_put, now=NOW,
                            send_license=AsyncMock(return_value={"status": "sent", "id": "e", "error": None}),
                            build_license=lic_mod.build_license_from_order))
    assert db._db.orders.find_one({"order_id": o["order_id"]})["status"] == "paid"
    assert db._db.licenses.count_documents({}) == 0


def _wire(monkeypatch, db, sender):
    run(lic_mod.ensure_indexes(db))
    monkeypatch.setattr(server, "db", db)
    monkeypatch.setattr(server, "_render_license", _pdf)
    monkeypatch.setattr(server, "_r2_put", _put)
    monkeypatch.setattr(server, "_send_license_email", sender)


def test_reconcile_fulfils_once(monkeypatch):
    db = AsyncDB()
    o = paid_order(db)
    sender = AsyncMock(return_value={"status": "sent", "id": "e", "error": None})
    _wire(monkeypatch, db, sender)
    run(server._reconcile_fulfilment(NOW))
    assert db._db.orders.find_one({"order_id": o["order_id"]})["status"] == "fulfilled"
    assert db._db.licenses.count_documents({}) == 1
    run(server._reconcile_fulfilment(NOW))  # second pass: already fulfilled
    assert db._db.licenses.count_documents({}) == 1
    assert sender.await_count == 1


def test_reconcile_skips_other_statuses(monkeypatch):
    db = AsyncDB()
    db._db.orders.insert_one(dict(make_order(status="fulfilled", paid_at=OLD.isoformat())))
    db._db.orders.insert_one(dict(make_order(status="refunded", paid_at=OLD.isoformat())))
    db._db.orders.insert_one(dict(make_order(status="pending")))
    recent = make_order(status="paid", paid_at=NOW.isoformat())  # too new
    db._db.orders.insert_one(dict(recent))
    sender = AsyncMock(return_value={"status": "sent", "id": "e", "error": None})
    _wire(monkeypatch, db, sender)
    run(server._reconcile_fulfilment(NOW))
    assert db._db.licenses.count_documents({}) == 0 and sender.await_count == 0
    assert "fulfil_attempts" not in db._db.orders.find_one({"order_id": recent["order_id"]})


def test_reconcile_stops_after_max_attempts(monkeypatch, caplog):
    db = AsyncDB()
    o = paid_order(db, fulfil_attempts=9)
    boom = AsyncMock(side_effect=RuntimeError("render boom"))
    _wire(monkeypatch, db, AsyncMock())
    monkeypatch.setattr(server, "_render_license", boom)
    with caplog.at_level(logging.ERROR):
        run(server._reconcile_fulfilment(NOW))
    row = db._db.orders.find_one({"order_id": o["order_id"]})
    assert row["status"] == "paid" and row["fulfil_attempts"] == 10 and row["last_fulfil_error"]
    assert any("fulfilment stuck" in r.message for r in caplog.records)
    # At 10 it is no longer picked up.
    run(server._reconcile_fulfilment(NOW))
    assert db._db.orders.find_one({"order_id": o["order_id"]})["fulfil_attempts"] == 10


def test_two_fulfil_runs_leave_one_license_one_email(monkeypatch):
    db = AsyncDB()
    run(lic_mod.ensure_indexes(db))
    o = paid_order(db)
    sender = AsyncMock(return_value={"status": "sent", "id": "e", "error": None})
    kw = dict(render_pdf=_pdf, put_object=_put, now=NOW, send_license=sender,
              build_license=lic_mod.build_license_from_order)
    run(so.fulfil_order(db, o["order_id"], **kw))
    run(so.fulfil_order(db, o["order_id"], **kw))  # second run: order already fulfilled
    assert db._db.licenses.count_documents({}) == 1
    assert db._db.orders.find_one({"order_id": o["order_id"]})["status"] == "fulfilled"
    assert sender.await_count == 1


def test_refund_marks_license(monkeypatch):
    db = AsyncDB()
    run(lic_mod.ensure_indexes(db))
    o = paid_order(db)
    sender = AsyncMock(return_value={"status": "sent", "id": "e", "error": None})
    run(so.fulfil_order(db, o["order_id"], render_pdf=_pdf, put_object=_put, now=NOW,
                        send_license=sender, build_license=lic_mod.build_license_from_order))
    db._db.orders.update_one({"order_id": o["order_id"]}, {"$set": {"stripe_payment_intent": "pi_1"}})
    charge = {"payment_intent": "pi_1", "refunded": True, "amount": 1900, "amount_refunded": 1900}
    run(so.apply_refund(db, charge, now=NOW))
    assert db._db.licenses.find_one({"order_id": o["order_id"]})["status"] == "refunded"
