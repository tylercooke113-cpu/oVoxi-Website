"""PRD-03 Phase 6c: admin order list, CSV export, resend email, reissue link."""
import asyncio
import csv
import io
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

mongomock = pytest.importorskip("mongomock")

import server  # noqa: E402
import sync_orders as so  # noqa: E402
from test_sync_orders import AsyncCollection, AsyncDB  # noqa: E402

ADMIN = {"sub": "user_admin", "metadata": {"role": "admin"}}
NOW = datetime.now(timezone.utc)


class _Cursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, key, direction):
        self._docs = sorted(self._docs, key=lambda d: d.get(key) or "", reverse=direction < 0)
        return self

    async def to_list(self, n):
        return self._docs[:n]


class FullCollection(AsyncCollection):
    def find(self, *a, **k):
        return _Cursor(list(self._c.find(*a, **k)))

    def aggregate(self, pipeline):
        return _Cursor(list(self._c.aggregate(pipeline)))


class FullDB(AsyncDB):
    def __getattr__(self, name):
        return FullCollection(self._db[name])


def make_order(db, *, created, artist="a1", name="Kay Lune", test=False, status="fulfilled", buyer="Dana",
               **over):
    track = {"id": "t1", "clerk_user_id": artist, "track_name": "Night Drive"}
    o = so.build_order(track=track, tier="creator", include_stems=False, buyer_name=buyer, buyer_company="",
                       buyer_email="d@example.com", test_mode=test, now=created, artist_display_name=name)
    o.update(status=status, tax_cents=133, amount_total_cents=2033, license_pdf_key="licenses/x.pdf", **over)
    if status == "fulfilled":
        o.update(token_version=1, download_token_hash=so.hash_token(so.derive_token(o["order_id"], 1)),
                 token_expires_at=(created + timedelta(days=30)).isoformat())
    db._db.orders.insert_one(dict(o))
    return o


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("SYNC_TOKEN_SECRET", "s" * 64)
    monkeypatch.delenv("SYNC_SITE_URL", raising=False)
    db = FullDB()
    sent = []

    async def fake_send(order, pdf=None, *, reissued=False):
        sent.append((order["order_id"], order.get("token_version"), reissued))
        return {"status": "sent", "id": "email_x", "error": None}

    monkeypatch.setattr(server, "db", db)
    monkeypatch.setattr(server, "_send_license_email", fake_send)
    monkeypatch.setattr(server.limiter, "enabled", False)
    server.app.dependency_overrides[server.require_admin] = lambda: ADMIN
    yield SimpleNamespace(client=TestClient(server.app), db=db, sent=sent)
    server.app.dependency_overrides.clear()


def test_list_hides_test_orders_by_default_and_never_exposes_token_hash(env):
    make_order(env.db, created=NOW)
    make_order(env.db, created=NOW, test=True)
    body = env.client.get("/api/admin/sync/orders").json()
    assert len(body["orders"]) == 1 and body["orders"][0]["test_mode"] is False
    assert "download_token_hash" not in body["orders"][0]
    assert len(env.client.get("/api/admin/sync/orders?include_test=true").json()["orders"]) == 2
    assert body["artists"] == [{"artist_user_id": "a1", "artist_display_name": "Kay Lune"}]


def test_filters_status_artist_and_inclusive_dates(env):
    d = datetime(2026, 9, 15, 23, 30, tzinfo=timezone.utc)
    make_order(env.db, created=d)
    make_order(env.db, created=d + timedelta(days=1), artist="a2", name="Other")
    make_order(env.db, created=d, status="refunded")
    c = env.client
    assert len(c.get("/api/admin/sync/orders?date_from=2026-09-15&date_to=2026-09-15").json()["orders"]) == 2
    assert len(c.get("/api/admin/sync/orders?artist=a2").json()["orders"]) == 1
    assert len(c.get("/api/admin/sync/orders?status=refunded").json()["orders"]) == 1


@pytest.mark.parametrize("q", ["status=shipped", "date_from=15-09-2026", "date_to=yesterday"])
def test_bad_filters_rejected(env, q):
    assert env.client.get(f"/api/admin/sync/orders?{q}").status_code == 422


def test_csv_columns_money_and_formula_injection(env):
    make_order(env.db, created=NOW, buyer="=HYPERLINK(\"http://evil\")")
    r = env.client.get("/api/admin/sync/orders.csv")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(r.text)))
    header, row = rows[0], dict(zip(rows[0], rows[1]))
    assert header[:3] == ["Order date (UTC)", "License ID", "Status"]
    assert row["License price"] == "19.00" and row["Tax"] == "1.33" and row["Total paid"] == "20.33"
    assert row["Currency"] == "USD" and row["Tier"] == "Creator" and row["Test order"] == "no"
    assert row["Buyer name"].startswith("'=")
    assert env.db._db.admin_actions.count_documents({"action": "export_orders_csv"}) == 1


def test_resend_email_only_for_fulfilled_and_logged(env):
    ok = make_order(env.db, created=NOW)
    pending = make_order(env.db, created=NOW, status="pending")
    r = env.client.post(f"/api/admin/sync/orders/{ok['order_id']}/resend-email")
    assert r.json()["email_status"] == "sent" and env.sent == [(ok["order_id"], 1, False)]
    assert env.client.post(f"/api/admin/sync/orders/{pending['order_id']}/resend-email").status_code == 409
    assert env.client.post("/api/admin/sync/orders/nope/resend-email").status_code == 404
    assert env.db._db.admin_actions.count_documents({"action": "resend_license_email"}) == 1


def test_reissue_kills_old_link_and_emails_new_one(env):
    o = make_order(env.db, created=NOW)
    old = so.derive_token(o["order_id"], 1)
    r = env.client.post(f"/api/admin/sync/orders/{o['order_id']}/reissue-link", json={"send_email": True})
    body = r.json()
    assert r.status_code == 200 and body["email_status"] == "sent"
    new = body["download_url"].rsplit("/", 1)[1]
    assert body["download_url"].startswith("https://ovoxi.net/license/") and new != old
    assert env.sent == [(o["order_id"], 2, True)]
    assert asyncio.run(so.find_by_token(env.db, old, now=NOW)) is None
    assert asyncio.run(so.find_by_token(env.db, new, now=NOW))["token_version"] == 2


def test_reissue_without_email(env):
    o = make_order(env.db, created=NOW)
    body = env.client.post(f"/api/admin/sync/orders/{o['order_id']}/reissue-link", json={"send_email": False}).json()
    assert body["email_status"] == "skipped" and env.sent == []


def test_refunded_order_cannot_be_reissued(env):
    o = make_order(env.db, created=NOW, status="refunded")
    assert env.client.post(f"/api/admin/sync/orders/{o['order_id']}/reissue-link", json={}).status_code == 409


def test_admin_only(env):
    server.app.dependency_overrides.clear()
    assert env.client.get("/api/admin/sync/orders").status_code in (401, 403)
    assert env.client.get("/api/admin/sync/orders.csv").status_code in (401, 403)
