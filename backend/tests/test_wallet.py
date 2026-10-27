"""Brief 27 Part A: Net Revenue, the split engine (Agreement v5 7.4 and 7.7) and the
append-only ledger, including refunds, disputes, holds and idempotency."""
from datetime import datetime, timezone

import pytest

import wallet
from test_subscriptions import AsyncDB, run

NOW = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
ME = "user_artist"


def party(name, bp, email=None, self_=False):
    return {"legal_name": name, "share_bp": bp, "email": email, "is_self": self_}


def three_side_rights():
    # Writers 50/50 (me + Jordan), publishers 100% me, masters 60/40 (me + Sam).
    return {"owns_everything": False,
            "writers": [party("Me", 5000, self_=True), party("Jordan", 5000, "jordan@example.com")],
            "publishers": [party("Me", 10000, self_=True)],
            "master_owners": [party("Me", 6000, self_=True), party("Sam", 4000, "Sam@Example.com")]}


def amounts(lines):
    return {l["payee_key"]: l["amount_cents"] for l in lines}


# --------------------------------------------------------------------------- pure math

def test_net_revenue_less_fee_and_tax():
    assert wallet.net_revenue(10875, fee_cents=345, tax_cents=875) == 9655


def test_revenue_share_rounds_half_up():
    assert wallet.revenue_share(9655, 3300) == 3186          # 3186.15
    assert wallet.revenue_share(15, 3300) == 5                # 4.95
    assert wallet.revenue_share(10000, 4000) == 4000
    assert wallet.revenue_share(-15, 3300) == -5


def test_owner_of_everything_gets_it_all():
    lines = wallet.split_share(3186, rights={"owns_everything": True}, licensor_user_id=ME, registered_emails=set())
    assert amounts(lines) == {ME: 3186}


def test_no_rights_doc_pays_the_licensor():
    assert amounts(wallet.split_share(100, rights={}, licensor_user_id=ME, registered_emails=set())) == {ME: 100}


def test_three_side_split_with_registered_co_owners():
    lines = wallet.split_share(10000, rights=three_side_rights(), licensor_user_id=ME,
                               registered_emails={"jordan@example.com", "sam@example.com"})
    got = amounts(lines)
    # Composition 50%: writers 25% (me 12.5, Jordan 12.5), publishers 25% (me). Master 50%: me 30, Sam 20.
    assert got == {ME: 6750, "email:jordan@example.com": 1250, "email:sam@example.com": 2000}
    assert sum(got.values()) == 10000
    shares = {l["payee_key"]: l["share_bp"] for l in lines}
    assert shares == {ME: 6750, "email:jordan@example.com": 1250, "email:sam@example.com": 2000}


def test_unregistered_party_is_paid_through_the_licensor():
    got = amounts(wallet.split_share(10000, rights=three_side_rights(), licensor_user_id=ME,
                                     registered_emails={"jordan@example.com"}))
    assert got == {ME: 8750, "email:jordan@example.com": 1250}


def test_rounding_cents_go_to_the_licensor_and_total_is_exact():
    got = amounts(wallet.split_share(3187, rights=three_side_rights(), licensor_user_id=ME,
                                     registered_emails={"jordan@example.com", "sam@example.com"}))
    assert sum(got.values()) == 3187
    assert got["email:jordan@example.com"] == 398 and got["email:sam@example.com"] == 637
    assert got[ME] == 3187 - 398 - 637


def test_sides_that_do_not_add_up_send_the_rest_to_the_licensor():
    r = three_side_rights()
    r["publishers"] = []                                      # no publisher listed
    got = amounts(wallet.split_share(10000, rights=r, licensor_user_id=ME,
                                     registered_emails={"jordan@example.com", "sam@example.com"}))
    assert got == {ME: 6750, "email:jordan@example.com": 1250, "email:sam@example.com": 2000}


def test_scale_lines_keeps_the_total_exact():
    orig = [{"payee_key": ME, "roles": ["licensor"], "amount_cents": 2125},
            {"payee_key": "email:a@x.com", "roles": ["writer"], "amount_cents": 531}]
    out = wallet.scale_lines(orig, -1000)
    assert sum(l["amount_cents"] for l in out) == -1000
    assert out[0]["payee_key"] == ME


# --------------------------------------------------------------------------- ledger

def track(rights=None):
    return {"id": "t1", "clerk_user_id": ME, "rights": rights or {"owns_everything": True}}


def order(**over):
    o = {"order_id": "o1", "track_id": "t1", "amount_total_cents": 10875, "tax_cents": 875,
         "paid_at": "2026-11-02T10:00:00+00:00", "status": "paid", "test_mode": True}
    o.update(over)
    return o


@pytest.fixture
def db():
    d = AsyncDB()
    run(wallet.ensure_indexes(d))
    return d


def entries(db, **q):
    return run(db.wallet_entries.find(q, {"_id": 0}).to_list(100))


def sign(db, email):
    run(db.cosign_requests.insert_one({"track_id": "t1", "email": email, "status": "signed"}))


def test_order_credit_and_replay_writes_once(db):
    assert run(wallet.credit_order(db, order(), track(), fee_cents=345, now=NOW)) == 1
    assert run(wallet.credit_order(db, order(), track(), fee_cents=345, now=NOW)) == 0
    [e] = entries(db)
    assert (e["net_cents"], e["rate_bp"], e["amount_cents"]) == (9655, 3300, 3186)
    assert (e["status"], e["period"], e["field"], e["test_mode"]) == ("accrued", "2026-11", "sync", True)
    assert (e["fee_cents"], e["tax_cents"], e["gross_cents"]) == (345, 875, 10875)


def test_order_credit_with_co_owners(db):
    sign(db, "jordan@example.com")
    sign(db, "sam@example.com")
    run(wallet.credit_order(db, order(), track(three_side_rights()), fee_cents=345, now=NOW))
    got = {e["payee_key"]: e["amount_cents"] for e in entries(db)}
    assert sum(got.values()) == 3186 and set(got) == {ME, "email:jordan@example.com", "email:sam@example.com"}


def test_full_refund_takes_every_payee_to_zero(db):
    sign(db, "jordan@example.com")
    sign(db, "sam@example.com")
    run(wallet.credit_order(db, order(), track(three_side_rights()), fee_cents=345, now=NOW))
    run(wallet.reverse_order(db, order(), kind="refund", refunded_cents=10875, now=NOW))
    run(wallet.reverse_order(db, order(), kind="refund", refunded_cents=10875, now=NOW))   # replay
    by = {}
    for e in entries(db):
        by[e["payee_key"]] = by.get(e["payee_key"], 0) + e["amount_cents"]
    assert set(by.values()) == {0}
    assert {e["source_type"] for e in entries(db)} == {"order", "refund"}


def test_partial_refunds_are_cumulative(db):
    run(wallet.credit_order(db, order(), track(), fee_cents=345, now=NOW))
    run(wallet.reverse_order(db, order(), kind="refund", refunded_cents=5000, now=NOW))
    first = sum(e["amount_cents"] for e in entries(db, source_type="refund"))
    # 5000 refunded includes 402 of tax (875/10875): reversal is 33% of 4598.
    assert first == -wallet.revenue_share(4598, 3300)
    run(wallet.reverse_order(db, order(), kind="refund", refunded_cents=10875, now=NOW))
    assert sum(e["amount_cents"] for e in entries(db)) == 0


def test_lost_dispute_reverses_everything(db):
    run(wallet.credit_order(db, order(), track(), fee_cents=345, now=NOW))
    run(wallet.reverse_order(db, order(), kind="dispute", refunded_cents=0, now=NOW))
    assert sum(e["amount_cents"] for e in entries(db)) == 0


def test_reverse_without_a_credit_does_nothing(db):
    assert run(wallet.reverse_order(db, order(), kind="refund", refunded_cents=100, now=NOW)) == 0


def test_exclusive_payment_pays_40_percent(db):
    lic = {"id": "x1", "uses": ["sync", "ai"]}
    run(wallet.credit_exclusive_payment(db, lic, track(), payment_id="pay1", amount_cents=500000,
                                        fee_cents=0, tax_cents=0, received_at="2026-11-10T00:00:00Z", now=NOW))
    [e] = entries(db)
    assert (e["source_type"], e["rate_bp"], e["amount_cents"], e["field"]) == ("exclusive", 4000, 200000, "ai+sync")


def test_hold_and_release(db):
    run(wallet.credit_order(db, order(), track(), fee_cents=345, now=NOW))
    run(wallet.hold_track(db, "t1", reason="Claim from a label", admin="admin_1", now=NOW))
    assert [e["status"] for e in entries(db)] == ["held"]
    run(wallet.credit_order(db, order(order_id="o2"), track(), fee_cents=345, now=NOW))
    assert {e["status"] for e in entries(db)} == {"held"}          # new lines are held too
    run(wallet.release_track(db, "t1", admin="admin_1", now=NOW))
    assert {e["status"] for e in entries(db)} == {"accrued"}


def test_summary_numbers():
    es = [{"amount_cents": 100, "status": "accrued", "period": "2026-11"},
          {"amount_cents": 50, "status": "accrued", "period": "2026-10"},
          {"amount_cents": 200, "status": "available", "period": "2026-10"},
          {"amount_cents": 30, "status": "held", "period": "2026-11"},
          {"amount_cents": 400, "status": "paid", "period": "2026-09"}]
    s = wallet.summarize(es, this_period="2026-11")
    assert (s["earned_this_month_cents"], s["available_cents"], s["held_cents"], s["paid_cents"]) == (100, 200, 30, 400)


def test_payee_key():
    assert wallet.payee_key("user_1", "a@b.com") == "user_1"
    assert wallet.payee_key(None, " A@B.com ") == "email:a@b.com"
    with pytest.raises(ValueError):
        wallet.payee_key()


# --------------------------------------------------------------------------- server hook

def test_server_credit_order_reads_the_fee_and_credits(db, monkeypatch):
    import server
    monkeypatch.setattr(server, "db", db)
    run(db.orders.insert_one(order(stripe_payment_intent="pi_1")))
    run(db.track_submissions.insert_one(track()))

    async def fee(o):
        return 345
    monkeypatch.setattr(server, "_order_fee_cents", fee)
    run(server._credit_order("o1"))
    run(server._credit_order("o1"))                     # a second webhook writes nothing new
    assert [e["amount_cents"] for e in entries(db)] == [3186]


def test_server_credit_order_defers_when_the_fee_is_not_posted(db, monkeypatch):
    import server
    monkeypatch.setattr(server, "db", db)
    run(db.orders.insert_one(order(stripe_payment_intent="pi_1")))
    run(db.track_submissions.insert_one(track()))

    async def fee(o):
        raise RuntimeError("no balance_transaction yet")
    monkeypatch.setattr(server, "_order_fee_cents", fee)
    run(server._credit_order("o1"))                     # logged, not raised
    assert entries(db) == []


def test_catch_up_reverses_a_lost_dispute_the_webhook_missed(db, monkeypatch):
    import server
    monkeypatch.setattr(server, "db", db)
    run(db.orders.insert_one(order(stripe_payment_intent="pi_1")))
    run(db.track_submissions.insert_one(track()))

    async def fee(o):
        return 345
    monkeypatch.setattr(server, "_order_fee_cents", fee)
    run(server._wallet_catch_up("2026-11", min_age_min=0))            # credits the sale
    run(db.orders.update_one({"order_id": "o1"}, {"$set": {"status": "refunded", "dispute_lost": True}}))
    run(server._wallet_catch_up("2026-11", min_age_min=0))            # reverses it
    run(server._wallet_catch_up("2026-11", min_age_min=0))            # safe to repeat
    rows = entries(db)
    assert {e["source_type"] for e in rows} == {"order", "dispute"} and sum(e["amount_cents"] for e in rows) == 0
    assert len(rows) == 2


def test_an_order_refunded_before_any_credit_stays_at_zero(db, monkeypatch):
    import server
    monkeypatch.setattr(server, "db", db)
    run(db.orders.insert_one(order(stripe_payment_intent="pi_1", status="refunded",
                                   refunds=[{"amount_refunded_cents": 10875, "full": True}])))
    run(db.track_submissions.insert_one(track()))

    async def fee(o):
        return 345
    monkeypatch.setattr(server, "_order_fee_cents", fee)
    run(server._wallet_catch_up("2026-11", min_age_min=0))
    assert entries(db) == []


def test_entry_view_date_and_share_for_older_lines():
    old = {"id": "x", "created_at": "2026-10-26T00:00:00+00:00", "track_id": "t1", "source_type": "order",
           "field": "sync", "share_bp": 0, "net_cents": 10000, "rate_bp": 3300, "amount_cents": 2475,
           "status": "accrued", "period": "2026-10"}
    v = wallet.entry_view(old, {"t1": "Song"})
    assert v["share_bp"] == 7500 and v["date"] == "2026-10-26T00:00:00+00:00"
    new = {**old, "share_bp": 6750, "occurred_at": "2026-10-03T00:00:00+00:00"}
    v = wallet.entry_view(new, {})
    assert v["share_bp"] == 6750 and v["date"] == "2026-10-03T00:00:00+00:00"


def test_new_credit_records_the_sale_date(db):
    run(wallet.credit_order(db, order(), track(), fee_cents=345, now=NOW))
    assert entries(db)[0]["occurred_at"] == "2026-11-02T10:00:00+00:00"
