"""Subscriptions (Brief 19): Stripe-mirrored plans, access rules, caps, loyalty math.

Stripe is the source of truth; webhook handlers (added later in this module) always
re-fetch the subscription. `stripe` is imported lazily inside functions so the rest of
the app and the test suite never require the library.
"""
import asyncio
import logging
import os
import time
from datetime import datetime, timedelta, timezone

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from sync_constants import PLANS, SUB_DAY_CAP

logger = logging.getLogger(__name__)
CURRENCY = "usd"

# lookup_key -> (plan, interval). Resolved to Stripe price ids at startup and cached.
PRICE_LOOKUP = {
    "sub_creator_month": ("creator", "month"), "sub_creator_year": ("creator", "year"),
    "sub_pro_month": ("pro", "month"),          "sub_pro_year": ("pro", "year"),
    "sub_business_month": ("business", "month"), "sub_business_year": ("business", "year"),
}
LOYALTY_COUPONS = {15: "LOYALTY15", 20: "LOYALTY20"}
ACTIVE_STATES = ("active", "grace", "ending")   # may register and download


def grace_days() -> int:
    raw = os.environ.get("SUB_GRACE_DAYS", "").strip()
    return int(raw) if raw.isdigit() and int(raw) > 0 else 7


def lookup_key(plan: str, interval: str) -> str:
    return f"sub_{plan}_{'month' if interval == 'month' else 'year'}"


def _parse(ts: str) -> datetime:
    """Parse a stored ISO timestamp as timezone-aware UTC, tolerating naive values."""
    dt = datetime.fromisoformat(ts)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def period_bounds(sub: dict) -> tuple:
    """(start, end) unix seconds. On the 2025-03-31 (basil) API and later these live on the
    subscription items, not the subscription, so read both shapes."""
    start, end = sub.get("current_period_start"), sub.get("current_period_end")
    if start is None or end is None:
        item = ((sub.get("items") or {}).get("data") or [{}])[0]
        start = start if start is not None else item.get("current_period_start")
        end = end if end is not None else item.get("current_period_end")
    return start, end


# --------------------------------------------------------------------------- price cache

_PRICE_IDS: dict = {}
_LAST_LOAD = 0.0


def load_prices(client) -> None:
    """Resolve the six prices by lookup key and cache ids. Logs an error on any missing key
    or on a unit_amount that disagrees with PLANS."""
    global _LAST_LOAD
    _LAST_LOAD = time.monotonic()
    ids = {}
    for key, (plan, interval) in PRICE_LOOKUP.items():
        try:
            data = client.v1.prices.list({"lookup_keys": [key], "active": True, "limit": 1}).data
        except Exception as exc:
            logger.error("subscription price lookup failed key=%s: %s", key, exc)
            continue
        if not data:
            logger.error("subscription price missing for lookup key %s", key)
            continue
        price = data[0]
        expected = PLANS[plan]["month_cents" if interval == "month" else "year_cents"]
        if price.unit_amount != expected:
            logger.error("subscription price mismatch %s: stripe=%s PLANS=%s",
                         key, price.unit_amount, expected)
        ids[key] = price.id
    _PRICE_IDS.clear()
    _PRICE_IDS.update(ids)


def ensure_prices(client) -> bool:
    """True when all six prices are cached. Retries load at most once every 5 minutes so a
    Stripe outage at startup does not keep subscriptions off until the next deploy."""
    if prices_ready():
        return True
    if time.monotonic() - _LAST_LOAD >= 300:
        load_prices(client)
    return prices_ready()


def price_id(plan: str, interval: str) -> str | None:
    return _PRICE_IDS.get(lookup_key(plan, interval))


def prices_ready() -> bool:
    return len(_PRICE_IDS) == len(PRICE_LOOKUP)


# --------------------------------------------------------------------------- periods + usage

def month_key(now: datetime) -> str:
    return now.strftime("%Y-%m")


def day_key(now: datetime) -> str:
    return now.strftime("%Y-%m-%d")


async def ensure_indexes(db) -> None:
    await db.subscriptions.create_index([("stripe_subscription_id", 1)], unique=True)
    await db.subscriptions.create_index([("user_id", 1), ("status", 1)])
    await db.sub_usage.create_index([("user_id", 1), ("period", 1)], unique=True)
    await db.subscription_revenue.create_index([("kind", 1), ("invoice_id", 1), ("ref", 1)], unique=True)


async def _used(db, user_id: str, period: str) -> int:
    doc = await db.sub_usage.find_one({"user_id": user_id, "period": period})
    return int((doc or {}).get("count") or 0)


async def _claim_period(db, user_id: str, period: str, cap: int) -> bool:
    """Atomically count one registration in `period` while under `cap`. The equality filter
    (user_id, period) seeds the doc on upsert; retries the upsert race once."""
    for _ in range(2):
        try:
            res = await db.sub_usage.find_one_and_update(
                {"user_id": user_id, "period": period, "count": {"$lt": cap}},
                {"$inc": {"count": 1}},
                upsert=True, return_document=ReturnDocument.AFTER)
            return res is not None
        except DuplicateKeyError:
            continue   # the period doc now exists; loop re-reads it under the cap filter
    return False


async def claim_download_slot(db, user_id: str, month_cap: int, day_cap: int, now: datetime):
    """Count one registration against both caps. Returns (ok, reason). Rolls the month back if the day fails."""
    if not await _claim_period(db, user_id, month_key(now), month_cap):
        return False, "month_cap"
    if not await _claim_period(db, user_id, day_key(now), day_cap):
        await db.sub_usage.update_one({"user_id": user_id, "period": month_key(now)}, {"$inc": {"count": -1}})
        return False, "day_cap"
    return True, None


# --------------------------------------------------------------------------- access rules

def _state(sub: dict, now: datetime) -> str:
    if not sub:
        return "none"
    if sub.get("dispute_open") is True:
        return "blocked_dispute"
    status = sub.get("status")
    if status in ("canceled", "ended", "incomplete_expired"):
        return "ended"
    if status == "past_due":
        since = sub.get("past_due_since")
        if since and now < _parse(since) + timedelta(days=grace_days()):
            return "grace"
        return "blocked_payment"
    if status in ("active", "trialing"):
        return "ending" if sub.get("cancel_at_period_end") else "active"
    return "blocked_payment"   # incomplete / unpaid


async def plan_access(db, user_id: str, now: datetime = None) -> dict:
    now = now or datetime.now(timezone.utc)
    sub = await db.subscriptions.find_one({"user_id": user_id}, sort=[("created_at", -1)])
    state = _state(sub, now)
    plan = sub.get("plan") if sub else None
    interval = sub.get("interval") if sub else None
    month_cap = PLANS.get(plan, {}).get("month_cap", 0)
    month_used = await _used(db, user_id, month_key(now)) if plan else 0
    day_used = await _used(db, user_id, day_key(now)) if plan else 0

    can, reason = True, None
    if state not in ACTIVE_STATES:
        can, reason = False, {"blocked_payment": "payment", "blocked_dispute": "dispute"}.get(state, "no_plan")
    elif month_used >= month_cap:
        can, reason = False, "month_cap"
    elif day_used >= SUB_DAY_CAP:
        can, reason = False, "day_cap"

    return {"plan": plan, "interval": interval, "state": state, "can_register": can, "reason": reason,
            "month_used": month_used, "month_cap": month_cap, "day_used": day_used, "day_cap": SUB_DAY_CAP}


# --------------------------------------------------------------------------- loyalty math (pure)

def _months_between(start_iso: str, period_start_iso: str) -> int:
    a, b = _parse(start_iso), _parse(period_start_iso)
    return (b.year - a.year) * 12 + (b.month - a.month)


def loyalty_target(subscribed_since: str, current_period_start: str) -> int:
    """0, 15 or 20 for a monthly plan. next_index 1 is the first month; 15 from 3, 20 from 7."""
    next_index = _months_between(subscribed_since, current_period_start) + 1
    return 20 if next_index >= 7 else 15 if next_index >= 3 else 0


def _add_months_iso(iso: str, months: int) -> str:
    """ISO timestamp `months` later in UTC, clamping the day to the target month's length."""
    import calendar
    dt = _parse(iso)
    base = dt.month - 1 + months
    year, month = dt.year + base // 12, base % 12 + 1
    return dt.replace(year=year, month=month, day=min(dt.day, calendar.monthrange(year, month)[1])).isoformat()


def loyalty_view(plan: str, interval: str, loyalty_pct: int, subscribed_since: str) -> dict:
    """Server-computed price and next-discount fields so the client never does loyalty math.
    Monthly steps 0 -> 15 (month 3) -> 20 (month 7); annual plans never discount. Cents are integers."""
    cents = PLANS.get(plan, {}).get("month_cents" if interval == "month" else "year_cents", 0)
    pct = loyalty_pct or 0
    out = {"price_cents": cents if interval != "month" else cents * (100 - pct) // 100,
           "next_loyalty_pct": None, "next_loyalty_price_cents": None,
           "next_loyalty_month": None, "next_loyalty_date": None}
    if interval == "month" and pct < 20 and subscribed_since:
        nxt_pct, nxt_month = (15, 3) if pct < 15 else (20, 7)
        out["next_loyalty_pct"] = nxt_pct
        out["next_loyalty_month"] = nxt_month
        out["next_loyalty_price_cents"] = cents * (100 - nxt_pct) // 100
        out["next_loyalty_date"] = _add_months_iso(subscribed_since, nxt_month - 1)
    return out


def grace_ends_at(sub: dict) -> str | None:
    """When the payment grace window closes, or None outside grace (brief item 5 / SUB_GRACE_DAYS)."""
    since = (sub or {}).get("past_due_since")
    if sub and sub.get("status") == "past_due" and since:
        return (_parse(since) + timedelta(days=grace_days())).isoformat()
    return None


# --------------------------------------------------------------------------- Stripe field accessors
# One place for every event-payload read, resilient to the 2025-03-31 (basil) field moves.
# Each logs ERROR (never returns silently) when a field is absent from BOTH shapes.

def _get(obj, *path):
    cur = obj
    for k in path:
        cur = cur.get(k) if isinstance(cur, dict) else getattr(cur, k, None)
        if cur is None:
            return None
    return cur


def _iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def invoice_subscription_id(inv: dict) -> str | None:
    sid = inv.get("subscription") or _get(inv, "parent", "subscription_details", "subscription")
    if not sid and str(inv.get("billing_reason") or "").startswith("subscription"):
        logger.error("subscription invoice %s has no subscription id (both shapes)", inv.get("id"))
    return sid


def invoice_tax_cents(inv: dict) -> int:
    if inv.get("tax") is not None:
        return int(inv["tax"])
    taxes = inv.get("total_taxes") or inv.get("total_tax_amounts") or []
    return sum(int(t.get("amount") or 0) for t in taxes)


def invoice_charge_id(inv: dict) -> str | None:
    cid = inv.get("charge")
    if cid:
        return cid
    for p in ((inv.get("payments") or {}).get("data") or []):
        c = _get(p, "payment", "charge")
        if c:
            return c
    return None


async def charge_invoice_id(client, charge: dict) -> str | None:
    """Charge -> invoice id on the dahlia account default, where both charge.invoice and
    payment_intent.invoice are gone. Resolve via the paid invoice_payment for the charge's
    payment_intent. Returns None for non-invoiced charges (e.g. single-track orders). Lookup
    errors are not caught: they propagate so the webhook returns 500 and Stripe retries."""
    cid = charge.get("invoice")                       # legacy / pre-basil direct
    if cid:
        return cid
    pi_id = charge.get("payment_intent")
    if not pi_id:
        return None
    ips = await asyncio.to_thread(
        client.v1.invoice_payments.list,
        {"payment": {"type": "payment_intent", "payment_intent": pi_id}, "status": "paid", "limit": 10})
    for ip in ips.data:
        ip = ip.to_dict() if hasattr(ip, "to_dict") else dict(ip)
        if ip.get("status") == "paid" and ip.get("invoice"):
            return ip["invoice"]
    return None


async def invoice_charge(client, inv: dict) -> str | None:
    """Invoice -> charge id for the fee. dahlia exposes neither invoice.charge nor
    payments[].payment.charge; resolve through the paid payment's payment_intent -> latest_charge.
    Lookup errors propagate (webhook 500)."""
    cid = invoice_charge_id(inv)                       # legacy / pre-basil direct
    if cid:
        return cid
    for p in ((inv.get("payments") or {}).get("data") or []):
        p = p.to_dict() if hasattr(p, "to_dict") else dict(p)
        if p.get("status") != "paid":
            continue
        pi_id = (p.get("payment") or {}).get("payment_intent")
        if pi_id:
            pi = await asyncio.to_thread(client.v1.payment_intents.retrieve, pi_id)
            pi = pi.to_dict() if hasattr(pi, "to_dict") else dict(pi)
            if pi.get("latest_charge"):
                return pi["latest_charge"]
    return None


def sub_item_price_id(sub: dict) -> str | None:
    item = ((sub.get("items") or {}).get("data") or [{}])[0]
    pid = _get(item, "price", "id") or _get(item, "pricing", "price_details", "price")
    if not pid:
        logger.error("subscription %s item has no price id (both shapes)", sub.get("id"))
    return pid


def _reverse_prices() -> dict:
    return {pid: PRICE_LOOKUP[lk] for lk, pid in _PRICE_IDS.items()}


def plan_interval_from_price_id(price_id: str) -> tuple:
    return _reverse_prices().get(price_id, (None, None))


# --------------------------------------------------------------------------- mirror + revenue + loyalty apply

async def _resolve_user(db, user_id, customer_id):
    if user_id:
        return user_id
    prof = await db.buyer_profiles.find_one({"stripe_customer_id": customer_id}) if customer_id else None
    return (prof or {}).get("user_id")


async def mirror_subscription(db, sub: dict, now, *, user_id=None, customer_id=None) -> dict:
    """Upsert the mirror from a freshly fetched Stripe subscription. subscribed_since is set once."""
    plan, interval = plan_interval_from_price_id(sub_item_price_id(sub))
    start, end = period_bounds(sub)
    customer_id = customer_id or sub.get("customer")
    uid = user_id or _get(sub, "metadata", "user_id") or await _resolve_user(db, None, customer_id)
    latest = sub.get("latest_invoice")
    latest = latest if isinstance(latest, str) else _get(sub, "latest_invoice", "id")
    fields = {"status": sub.get("status"), "plan": plan, "interval": interval,
              "stripe_customer_id": customer_id, "cancel_at_period_end": bool(sub.get("cancel_at_period_end")),
              "current_period_start": _iso(start) if start else None,
              "current_period_end": _iso(end) if end else None,
              "latest_invoice": latest, "updated_at": now.isoformat()}
    if uid:
        fields["user_id"] = uid
    on_insert = {"created_at": now.isoformat(), "dispute_open": False, "loyalty_pct": 0, "past_due_since": None}
    if start:
        on_insert["subscribed_since"] = _iso(start)
    await db.subscriptions.update_one({"stripe_subscription_id": sub["id"]},
                                      {"$set": fields, "$setOnInsert": on_insert}, upsert=True)
    doc = await db.subscriptions.find_one({"stripe_subscription_id": sub["id"]})
    if uid:
        actives = await db.subscriptions.count_documents(
            {"user_id": uid, "status": {"$in": ["active", "trialing", "past_due"]}})
        if actives > 1:
            logger.error("user %s has %d active subscriptions (two checkout tabs?)", uid, actives)
    return doc


async def _add_revenue(db, *, kind, invoice_id, ref, user_id, plan, interval, period_start, period_end,
                       amount_cents, tax_cents, fee_cents, currency, now):
    try:
        await db.subscription_revenue.insert_one({
            "kind": kind, "invoice_id": invoice_id or "", "ref": ref or "", "user_id": user_id,
            "plan": plan, "interval": interval, "period_start": period_start, "period_end": period_end,
            "amount_cents": amount_cents, "tax_cents": tax_cents, "stripe_fee_cents": fee_cents,
            "currency": currency, "created_at": now.isoformat()})
    except DuplicateKeyError:
        pass   # already recorded; handlers are safe to replay


async def apply_loyalty(db, client, sub_doc: dict, now) -> None:
    sub_id = sub_doc["stripe_subscription_id"]
    if sub_doc.get("interval") != "month":                 # annual: ensure no coupon
        if sub_doc.get("loyalty_pct"):
            await asyncio.to_thread(client.v1.subscriptions.update, sub_id, {"discounts": []})
            await db.subscriptions.update_one({"stripe_subscription_id": sub_id},
                                              {"$set": {"loyalty_pct": 0, "updated_at": now.isoformat()}})
        return
    if not sub_doc.get("subscribed_since") or not sub_doc.get("current_period_end"):
        return
    # The upcoming invoice's period starts at the current period end (matches stripe_loyalty_check.py).
    target = loyalty_target(sub_doc["subscribed_since"], sub_doc["current_period_end"])
    if target != sub_doc.get("loyalty_pct"):
        coupon = LOYALTY_COUPONS.get(target)
        await asyncio.to_thread(client.v1.subscriptions.update, sub_id,
                                {"discounts": [{"coupon": coupon}] if coupon else []})
        await db.subscriptions.update_one({"stripe_subscription_id": sub_id},
                                          {"$set": {"loyalty_pct": target, "updated_at": now.isoformat()}})


async def _charge_fee(client, charge_id) -> int:
    """The Stripe processing fee for a charge, from its balance transaction. Errors propagate
    (webhook 500, Stripe retries). A paid charge whose balance transaction has not posted yet
    is an error too, so the retry picks it up once it settles."""
    if not charge_id:
        return 0
    ch = await asyncio.to_thread(client.v1.charges.retrieve, charge_id)
    ch = ch.to_dict() if hasattr(ch, "to_dict") else dict(ch)
    bt_id = ch.get("balance_transaction")
    if not bt_id:
        logger.error("charge %s has no balance_transaction yet; retrying", charge_id)
        raise RuntimeError(f"charge {charge_id} has no balance_transaction yet")
    bt = await asyncio.to_thread(client.v1.balance_transactions.retrieve, bt_id)
    bt = bt.to_dict() if hasattr(bt, "to_dict") else dict(bt)
    return int(bt.get("fee") or 0)


# --------------------------------------------------------------------------- webhook handlers
# Each re-fetches from Stripe and is idempotent. Blocking client.v1.* calls go through to_thread.

async def on_subscription_event(db, client, sub_id, now, *, user_id=None, customer_id=None):
    sub = await asyncio.to_thread(client.v1.subscriptions.retrieve, sub_id)
    sub = sub.to_dict() if hasattr(sub, "to_dict") else dict(sub)
    doc = await mirror_subscription(db, sub, now, user_id=user_id, customer_id=customer_id)
    await apply_loyalty(db, client, doc, now)   # idempotent; also covers annual<->monthly switches
    return doc


async def on_checkout_completed(db, client, session, now):
    if session.get("mode") != "subscription" or not session.get("subscription"):
        return
    uid, customer = session.get("client_reference_id"), session.get("customer")
    if uid:
        await db.buyer_profiles.update_one({"user_id": uid}, {"$set": {"stripe_customer_id": customer}}, upsert=True)
    await on_subscription_event(db, client, session["subscription"], now, user_id=uid, customer_id=customer)


async def on_invoice_paid(db, client, invoice, now):
    sub_id = invoice_subscription_id(invoice)
    if not sub_id:
        return
    sub_doc = await db.subscriptions.find_one({"stripe_subscription_id": sub_id})
    if sub_doc and sub_doc.get("past_due_since"):
        await db.subscriptions.update_one({"stripe_subscription_id": sub_id},
                                          {"$set": {"past_due_since": None, "updated_at": now.isoformat()}})
    # Mirror and set the loyalty coupon for the next invoice BEFORE the fee fetch, so a slow or
    # not-yet-posted balance transaction (which raises below) cannot delay the coupon to a retry.
    fresh = await on_subscription_event(db, client, sub_id, now)
    line = ((invoice.get("lines") or {}).get("data") or [{}])[0]
    period = line.get("period") or {}
    # Webhook invoice payloads are not expanded, so the charge lives neither at invoice.charge nor
    # in an (absent) payments list -- re-fetch with payments to resolve it and read the fee.
    charge_id = invoice_charge_id(invoice)
    if not charge_id and invoice.get("id"):
        full = await asyncio.to_thread(client.v1.invoices.retrieve, invoice["id"], {"expand": ["payments"]})
        full = full.to_dict() if hasattr(full, "to_dict") else dict(full)
        charge_id = await invoice_charge(client, full)
    if not charge_id and int(invoice.get("amount_paid") or 0) > 0:
        logger.error("invoice %s paid %s but no charge resolved; retrying",
                     invoice.get("id"), invoice.get("amount_paid"))
        raise RuntimeError(f"invoice {invoice.get('id')} paid but no charge resolved")
    fee = await _charge_fee(client, charge_id)
    await _add_revenue(db, kind="invoice_paid", invoice_id=invoice.get("id"), ref="",
                       user_id=(fresh or sub_doc or {}).get("user_id"), plan=(fresh or sub_doc or {}).get("plan"),
                       interval=(fresh or sub_doc or {}).get("interval"),
                       period_start=_iso(period["start"]) if period.get("start") else None,
                       period_end=_iso(period["end"]) if period.get("end") else None,
                       amount_cents=invoice.get("amount_paid"), tax_cents=invoice_tax_cents(invoice),
                       fee_cents=fee, currency=invoice.get("currency") or "usd", now=now)
    return fresh


async def on_invoice_payment_failed(db, invoice, now):
    sub_id = invoice_subscription_id(invoice)
    if sub_id:
        await db.subscriptions.update_one(
            {"stripe_subscription_id": sub_id, "past_due_since": None},
            {"$set": {"past_due_since": now.isoformat(), "updated_at": now.isoformat()}})


async def on_charge_refunded(db, client, charge, now) -> str | None:
    """Subscription refund path. Returns the invoice id when it handled a subscription charge, else None."""
    invoice_id = await charge_invoice_id(client, charge)
    if not invoice_id:
        return None
    inv = await asyncio.to_thread(client.v1.invoices.retrieve, invoice_id, {"expand": ["payments"]})
    inv = inv.to_dict() if hasattr(inv, "to_dict") else dict(inv)
    sub_doc = await db.subscriptions.find_one({"stripe_subscription_id": invoice_subscription_id(inv)})
    refunds = (await asyncio.to_thread(client.v1.refunds.list, {"charge": charge.get("id"), "limit": 100})).data
    for rf in refunds:
        rf = rf.to_dict() if hasattr(rf, "to_dict") else dict(rf)
        await _add_revenue(db, kind="refund", invoice_id=invoice_id, ref=rf["id"],
                           user_id=(sub_doc or {}).get("user_id"), plan=(sub_doc or {}).get("plan"),
                           interval=(sub_doc or {}).get("interval"), period_start=None, period_end=None,
                           amount_cents=-int(rf.get("amount") or 0), tax_cents=0, fee_cents=0,
                           currency=charge.get("currency") or "usd", now=now)
    fully = charge.get("refunded") is True or int(charge.get("amount_refunded") or 0) >= int(charge.get("amount") or 0) > 0
    if fully:
        from licenses import void_invoice_projects
        await void_invoice_projects(db, invoice_id, "refund")
    else:
        logger.info("partial subscription refund invoice=%s, voiding nothing", invoice_id)
    return invoice_id


async def on_dispute(db, client, dispute, now, *, closed: bool) -> str | None:
    charge = await asyncio.to_thread(client.v1.charges.retrieve, dispute.get("charge"))
    charge = charge.to_dict() if hasattr(charge, "to_dict") else dict(charge)
    invoice_id = await charge_invoice_id(client, charge)
    if not invoice_id:
        return None   # not a subscription charge; the webhook dispatcher logs if it is also not an order
    inv = await asyncio.to_thread(client.v1.invoices.retrieve, invoice_id)
    inv = inv.to_dict() if hasattr(inv, "to_dict") else dict(inv)
    sub_id = invoice_subscription_id(inv)
    await db.subscriptions.update_one({"stripe_subscription_id": sub_id},
                                      {"$set": {"dispute_open": not closed, "updated_at": now.isoformat()}})
    if closed and dispute.get("status") == "lost":
        sub_doc = await db.subscriptions.find_one({"stripe_subscription_id": sub_id})
        fee = sum(int(bt.get("fee") or 0) for bt in (dispute.get("balance_transactions") or []))
        await _add_revenue(db, kind="dispute_lost", invoice_id=invoice_id, ref=dispute.get("id"),
                           user_id=(sub_doc or {}).get("user_id"), plan=(sub_doc or {}).get("plan"),
                           interval=(sub_doc or {}).get("interval"), period_start=None, period_end=None,
                           amount_cents=-int(dispute.get("amount") or 0), tax_cents=0, fee_cents=fee,
                           currency=dispute.get("currency") or "usd", now=now)
        from licenses import void_invoice_projects
        await void_invoice_projects(db, invoice_id, "dispute_lost")
    return invoice_id
