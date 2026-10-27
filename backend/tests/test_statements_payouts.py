"""Brief 27 Part C: Subscription Artist Pool (7.6), Close month, statements (8.2) and the
payout run (8.1): $25 rollover, the December rule, unverified payees, idempotent
transfers and failures."""
import io
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import payouts
import server
import statements
import sync_orders
import wallet
from test_subscriptions import AsyncDB, run

NOV = datetime(2026, 12, 2, 7, tzinfo=timezone.utc)      # after November ends
ME, CO = "user_artist", "email:jordan@example.com"


def text_of(pdf: bytes) -> str:
    from pypdf import PdfReader
    return " ".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)


@pytest.fixture
def db():
    d = AsyncDB()
    run(wallet.ensure_indexes(d))
    run(payouts.ensure_indexes(d))
    return d


def add_track(db, tid="t1", rights=None, name="Night Drive"):
    run(db.track_submissions.insert_one({"id": tid, "clerk_user_id": ME, "track_name": name,
                                         "rights": rights or {"owns_everything": True}}))


def co_rights():
    p = lambda n, bp, e=None, s=False: {"legal_name": n, "share_bp": bp, "email": e, "is_self": s}
    return {"owns_everything": False,
            "writers": [p("Me", 5000, s=True), p("Jordan", 5000, "jordan@example.com")],
            "publishers": [p("Me", 10000, s=True)], "master_owners": [p("Me", 10000, s=True)]}


def entry(db, payee, amount, status="available", period="2026-11", test_mode=True, src="o1", user=None):
    run(db.wallet_entries.insert_one({
        "id": f"{payee}{src}", "payee_key": payee, "payee_user_id": user or (None if payee.startswith("email:") else payee),
        "payee_email": payee[6:] if payee.startswith("email:") else None, "roles": [], "share_bp": 0,
        "source_type": "order", "source_id": src, "track_id": "t1", "field": "sync", "period": period,
        "net_cents": 0, "rate_bp": 3300, "amount_cents": amount, "status": status, "payout_id": None,
        "test_mode": test_mode, "created_at": "2026-11-05T00:00:00+00:00"}))


def account(db, uid=ME, ready=True, unsupported=False):
    run(db.wallet_accounts.insert_one({"user_id": uid, "livemode": False, "stripe_account_id": None if unsupported else f"acct_{uid}",
                                       "payouts_enabled": ready, "transfers_active": ready,
                                       "unsupported_country": unsupported}))


# --------------------------------------------------------------------------- helpers

def test_dates():
    assert statements.payment_due("2026-10") == "2026-12-15"
    assert statements.payment_due("2026-11") == "2027-01-14"
    assert statements.previous_period(datetime(2027, 1, 1, tzinfo=timezone.utc)) == "2026-12"
    assert statements.month_bounds("2026-12")[1] == datetime(2027, 1, 1, tzinfo=timezone.utc)


def test_allocate_is_exact():
    got = statements.allocate(1000, {"a": 2, "b": 1})
    assert got == {"a": 667, "b": 333} and sum(got.values()) == 1000
    assert statements.allocate(0, {"a": 1}) == {"a": 0}
    assert statements.allocate(500, {}) == {}


# --------------------------------------------------------------------------- pool (7.6)

def test_pool_is_33_percent_of_net_split_by_registered_projects(db):
    add_track(db, "t1")
    add_track(db, "t2", name="Second")
    for kind, amt, tax, fee in (("invoice_paid", 4900, 0, 172), ("invoice_paid", 14900, 0, 462), ("refund", -4900, 0, 0)):
        run(db.subscription_revenue.insert_one({"kind": kind, "amount_cents": amt, "tax_cents": tax,
                                                "stripe_fee_cents": fee, "created_at": "2026-11-10T00:00:00+00:00"}))
    run(db.subscription_revenue.insert_one({"kind": "invoice_paid", "amount_cents": 99999, "tax_cents": 0,
                                            "stripe_fee_cents": 0, "created_at": "2026-12-01T00:00:00+00:00"}))   # December: not counted
    for t, n in (("t1", 3), ("t2", 1)):
        for i in range(n):
            run(db.licenses.insert_one({"source": "subscription", "track_id": t, "status": "active",
                                        "issued_at": "2026-11-12T00:00:00+00:00"}))
    run(db.licenses.insert_one({"source": "subscription", "track_id": "t2", "status": "void",
                                "issued_at": "2026-11-12T00:00:00+00:00"}))          # voided: not counted
    res = run(statements.build_pool(db, "2026-11", test_mode=True, now=NOV))
    net = 4900 + 14900 - 4900 - 172 - 462
    assert res["net_cents"] == net and res["projects"] == 4
    pool = wallet.revenue_share(net, 3300)
    got = {e["track_id"]: e["amount_cents"] for e in run(db.wallet_entries.find({}, {"_id": 0}).to_list(10))}
    assert sum(got.values()) == pool
    assert got == statements.allocate(pool, {"t1": 3, "t2": 1})
    assert run(statements.build_pool(db, "2026-11", test_mode=True, now=NOV))["lines"] == 0      # idempotent


def test_negative_pool_month_pays_nothing(db):
    add_track(db)
    run(db.subscription_revenue.insert_one({"kind": "refund", "amount_cents": -4900, "tax_cents": 0,
                                            "stripe_fee_cents": 0, "created_at": "2026-11-10T00:00:00+00:00"}))
    run(db.licenses.insert_one({"source": "subscription", "track_id": "t1", "status": "active",
                                "issued_at": "2026-11-12T00:00:00+00:00"}))
    assert run(statements.build_pool(db, "2026-11", test_mode=True, now=NOV))["pool_cents"] == 0


# --------------------------------------------------------------------------- close month

def close(db, sent, put):
    async def put_object(key, data, ct):
        put[key] = data

    async def send_email(**kw):
        sent.append(kw)
        return {"status": "sent"}
    return run(statements.close_month(db, "2026-11", test_mode=True, now=NOV, admin="admin_1",
                                      put_object=put_object, send_email=send_email, site="https://ovoxi.net"))


def test_close_makes_balances_available_and_writes_statements(db):
    add_track(db, rights=co_rights())
    run(db.cosign_requests.insert_one({"track_id": "t1", "email": "jordan@example.com", "status": "signed"}))
    order = {"order_id": "o1", "track_id": "t1", "amount_total_cents": 10000, "tax_cents": 0,
             "paid_at": "2026-11-03T00:00:00+00:00", "test_mode": True}
    run(wallet.credit_order(db, order, run(db.track_submissions.find_one({"id": "t1"})), fee_cents=320, now=NOV))
    sent, put = [], {}
    summary = close(db, sent, put)
    assert summary["made_available"] == 2 and summary["statements"] == 2
    assert {e["status"] for e in run(db.wallet_entries.find({}, {"_id": 0}).to_list(10))} == {"available"}
    st = run(db.statements.find_one({"payee_key": ME, "period": "2026-11"}, {"_id": 0}))
    assert st["payment_due"] == "2027-01-14" and st["pdf_key"] in put
    # Co-owner without an account gets the statement by email (Co-owner Consent 3.3).
    assert [m["to"] for m in sent] == ["jordan@example.com"]
    assert sent[0]["attachments"][0][0] == "OVOXI statement 2026-11.pdf"
    assert "Create an account with this email" in sent[0]["text"]
    # 8.2 items on the PDF.
    pdf = " ".join(text_of(put[st["pdf_key"]]).split())      # ignore line wrapping
    for item in ("Night Drive", "Sync license", "Your split", "Earnings for the month",
                 "Registered Projects", "Exclusive Licenses", "Held for a claim", "Payment due by",
                 "Net Revenue and deductions behind this statement"):
        assert item in pdf, item
    for gone in ("Received", "Rate", "Fees", "Tax", "Your share", "$96.80"):   # columns removed (Oct 27, 8.2)
        assert gone not in pdf, gone
    # Closing again changes nothing and the email key stops a second email.
    close(db, sent, put)
    assert run(db.wallet_entries.count_documents({})) == 2
    assert sent[1]["idempotency_key"] == sent[0]["idempotency_key"]


def test_close_refuses_a_month_that_has_not_ended(db):
    async def noop(*a, **k):
        return {"status": "sent"}
    with pytest.raises(ValueError):
        run(statements.close_month(db, "2026-12", test_mode=True, now=NOV, admin="a",
                                   put_object=noop, send_email=noop, site="x"))


def test_held_lines_stay_held_through_close(db):
    add_track(db)
    entry(db, ME, 5000, status="held")
    close(db, [], {})
    assert run(db.wallet_entries.find_one({}))["status"] == "held"


# --------------------------------------------------------------------------- payout run

class Transfers:
    def __init__(self, fail_for=()):
        self.calls, self.fail_for, self.by_key = [], set(fail_for), {}

    def create(self, params, options):
        self.calls.append((params, options))
        if params["destination"] in self.fail_for:
            raise RuntimeError("insufficient available funds")
        key = options["idempotency_key"]
        self.by_key.setdefault(key, {"id": f"tr_{len(self.by_key) + 1}", **params})
        return self.by_key[key]


def fake(transfers):
    return SimpleNamespace(v1=SimpleNamespace(transfers=transfers))


def test_preview_sorts_payees(db):
    entry(db, ME, 3000)
    entry(db, "user_small", 1000, user="user_small")
    entry(db, "user_unverified", 9000, user="user_unverified")
    entry(db, "user_ng", 9000, user="user_ng")
    entry(db, CO, 9000)
    entry(db, "user_neg", -500, user="user_neg")
    entry(db, "user_live", 9000, test_mode=False, user="user_live")       # other mode: ignored
    account(db)
    account(db, "user_small")
    account(db, "user_unverified", ready=False)
    account(db, "user_ng", unsupported=True)
    account(db, "user_neg")
    p = run(payouts.preview(db, "2026-11", livemode=False))
    keys = {k: [t["payee_key"] for t in v] for k, v in p.items() if isinstance(v, list)}
    assert keys["pay"] == [ME] and keys["below_minimum"] == ["user_small"]
    assert keys["not_verified"] == ["user_unverified"] and keys["unsupported"] == ["user_ng"]
    assert keys["no_account"] == [CO] and keys["negative"] == ["user_neg"]
    assert p["total_to_pay_cents"] == 3000


def test_december_pays_balances_under_25(db):
    entry(db, ME, 1000, period="2026-12")
    account(db)
    assert [t["payee_key"] for t in run(payouts.preview(db, "2026-12", livemode=False))["pay"]] == [ME]


def test_run_pays_once_even_when_clicked_twice(db):
    entry(db, ME, 3000, src="o1")
    entry(db, ME, 500, src="o2")
    account(db)
    tr = Transfers()
    r1 = run(payouts.run(db, fake(tr), "2026-11", livemode=False, admin="a", now=NOV))
    r2 = run(payouts.run(db, fake(tr), "2026-11", livemode=False, admin="a", now=NOV))
    assert r1["paid_total_cents"] == 3500 and r2["paid"] == [] and len(tr.calls) == 1
    params, opts = tr.calls[0]
    assert params == {"amount": 3500, "currency": "usd", "destination": f"acct_{ME}", "transfer_group": "ovoxi-2026-11",
                      "metadata": params["metadata"]}
    assert opts == {"idempotency_key": f"payout:2026-11:{ME}:1"}
    assert {e["status"] for e in run(db.wallet_entries.find({}, {"_id": 0}).to_list(10))} == {"paid"}
    assert run(db.payouts.find_one({}))["stripe_transfer_id"] == "tr_1"


def test_failed_transfer_leaves_balance_available(db):
    entry(db, ME, 3000)
    account(db)
    r = run(payouts.run(db, fake(Transfers(fail_for={f"acct_{ME}"})), "2026-11", livemode=False, admin="a", now=NOV))
    assert r["paid"] == [] and "insufficient" in r["failed"][0]["error"]
    e = run(db.wallet_entries.find_one({}))
    assert e["status"] == "available" and e["payout_id"] is None
    # The next run tries again with a new key.
    tr = Transfers()
    run(payouts.run(db, fake(tr), "2026-11", livemode=False, admin="a", now=NOV))
    assert tr.calls[0][1]["idempotency_key"] == f"payout:2026-11:{ME}:2"


def test_a_crash_after_claiming_is_finished_with_the_same_key(db):
    entry(db, ME, 3000)
    account(db)
    run(db.wallet_entries.update_many({}, {"$set": {"status": "in_payout", "payout_id": "po_x"}}))
    run(db.payouts.insert_one({"id": "po_x", "period": "2026-11", "payee_key": ME, "stripe_account_id": f"acct_{ME}",
                               "amount_cents": 3000, "livemode": False, "status": "pending",
                               "idempotency_key": f"payout:2026-11:{ME}:1"}))
    tr = Transfers()
    run(payouts.run(db, fake(tr), "2026-11", livemode=False, admin="a", now=NOV))
    assert [c[1]["idempotency_key"] for c in tr.calls] == [f"payout:2026-11:{ME}:1"]
    assert run(db.wallet_entries.find_one({}))["status"] == "paid"


# --------------------------------------------------------------------------- admin endpoints

ADMIN = {"sub": "admin_1", "metadata": {"role": "admin"}}


@pytest.fixture
def api(db, monkeypatch):
    monkeypatch.setattr(server, "db", db)
    monkeypatch.setattr(server.limiter, "enabled", False)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_1")
    server.app.dependency_overrides[server.require_admin] = lambda: ADMIN
    yield TestClient(server.app)
    server.app.dependency_overrides.clear()


def test_payouts_need_the_month_closed(api):
    assert api.post("/api/admin/wallet/payouts", json={"period": "2026-11"}).status_code == 409


def test_overview_shows_the_deadline(api, db):
    r = api.get("/api/admin/wallet/overview?period=2026-10").json()
    assert r["payment_due"] == "2026-12-15" and r["period_label"] == "October 2026" and r["livemode"] is False


def test_exclusive_payment_credits_40_percent_once(api, db):
    add_track(db)
    run(db.exclusive_licenses.insert_one({"id": "x1", "track_id": "t1", "uses": ["sync"]}))
    body = {"amount_cents": 100000, "fee_cents": 2900, "tax_cents": 0, "received_at": "2026-11-20", "reference": "INV-7"}
    r = api.post("/api/admin/sync/exclusive-licenses/x1/payments", json=body)
    assert r.status_code == 200 and r.json()["revenue_share_cents"] == 38840 and r.json()["recorded"]
    assert api.post("/api/admin/sync/exclusive-licenses/x1/payments", json=body).json()["duplicate"] is True
    [e] = run(db.wallet_entries.find({}, {"_id": 0}).to_list(5))
    assert (e["rate_bp"], e["amount_cents"], e["period"]) == (4000, 38840, "2026-11")
    assert run(db.admin_actions.count_documents({"action": "exclusive_payment_recorded"})) == 2


def test_exclusive_payment_validation(api, db):
    bad = {"amount_cents": 100, "fee_cents": 100, "tax_cents": 0, "received_at": "2026-11-20", "reference": "r"}
    assert api.post("/api/admin/sync/exclusive-licenses/x1/payments", json=bad).status_code == 422


def test_hold_and_release_endpoints(api, db):
    add_track(db)
    entry(db, ME, 3000)
    assert api.post("/api/admin/wallet/holds", json={"track_id": "t1", "reason": "Label claim"}).json() == {"held": True}
    assert run(db.wallet_entries.find_one({}))["status"] == "held"
    assert api.delete("/api/admin/wallet/holds/t1").json() == {"held": False}
    assert run(db.wallet_entries.find_one({}))["status"] == "available"     # back where it was
