"""Payouts through Stripe Connect Express (Brief 27 Parts B and C).

Separate charges and transfers: buyers pay OVOXI; each month OVOXI transfers each
payee's available Wallet balance to their connected account, and Stripe pays it to
their bank. Connect pays connected accounts in the US, UK, EEA, Canada and
Switzerland only (Stripe docs, cross-border payouts). Payees elsewhere accrue until
Global Payouts is added in a later brief.
"""
import asyncio
import os
from datetime import datetime, timezone
from typing import Optional

UNSUPPORTED_MESSAGE = "Payouts are not available in your country yet. Email tyler@ovoxi.net."

# Countries Connect can pay from a US platform: US, UK, EEA, Canada, Switzerland.
CONNECT_COUNTRIES = {
    "US": "United States", "CA": "Canada", "GB": "United Kingdom", "CH": "Switzerland",
    "AT": "Austria", "BE": "Belgium", "BG": "Bulgaria", "HR": "Croatia", "CY": "Cyprus",
    "CZ": "Czech Republic", "DK": "Denmark", "EE": "Estonia", "FI": "Finland", "FR": "France",
    "DE": "Germany", "GR": "Greece", "HU": "Hungary", "IS": "Iceland", "IE": "Ireland",
    "IT": "Italy", "LV": "Latvia", "LI": "Liechtenstein", "LT": "Lithuania", "LU": "Luxembourg",
    "MT": "Malta", "NL": "Netherlands", "NO": "Norway", "PL": "Poland", "PT": "Portugal",
    "RO": "Romania", "SK": "Slovakia", "SI": "Slovenia", "ES": "Spain", "SE": "Sweden",
}
_ALIASES = {
    "usa": "US", "us": "US", "u.s.": "US", "u.s.a.": "US", "united states of america": "US",
    "america": "US", "uk": "GB", "u.k.": "GB", "england": "GB", "scotland": "GB", "wales": "GB",
    "great britain": "GB", "britain": "GB", "northern ireland": "GB",
}


def guess_country(text: Optional[str]) -> Optional[str]:
    """The agreement's free-text country -> an ISO code Connect supports, or None."""
    t = (text or "").strip().lower()
    if not t:
        return None
    if t.upper() in CONNECT_COUNTRIES:
        return t.upper()
    if t in _ALIASES:
        return _ALIASES[t]
    for code, name in CONNECT_COUNTRIES.items():
        if name.lower() == t:
            return code
    return None


def is_live_key(key: str) -> bool:
    return (key or "").startswith(("sk_live", "rk_live"))


def stripe_livemode() -> bool:
    return is_live_key(os.environ.get("STRIPE_SECRET_KEY", ""))


def account_params(*, user_id: str, email: str, country: str) -> dict:
    """An Express account that can only receive transfers (no card payments)."""
    return {
        "type": "express",
        "country": country,
        "email": email or None,
        "capabilities": {"transfers": {"requested": True}},
        "business_type": "individual",
        "business_profile": {"product_description": "Royalties for music licensed through OVOXI"},
        "metadata": {"ovoxi_user_id": user_id},
    }


def status_of(account: dict) -> dict:
    req = account.get("requirements") or {}
    return {
        "details_submitted": bool(account.get("details_submitted")),
        "payouts_enabled": bool(account.get("payouts_enabled")),
        "transfers_active": ((account.get("capabilities") or {}).get("transfers") == "active"),
        "currently_due": list(req.get("currently_due") or []),
        "disabled_reason": req.get("disabled_reason"),
    }


def payout_ready(acct: Optional[dict]) -> bool:
    return bool(acct and acct.get("payouts_enabled") and acct.get("transfers_active"))


def _d(obj) -> dict:
    return obj.to_dict() if hasattr(obj, "to_dict") else dict(obj)


async def ensure_indexes(db) -> None:
    await db.wallet_accounts.create_index([("user_id", 1), ("livemode", 1)], unique=True)
    await db.wallet_accounts.create_index([("stripe_account_id", 1)])
    await ensure_payout_indexes(db)


async def get_account(db, user_id: str) -> Optional[dict]:
    return await db.wallet_accounts.find_one({"user_id": user_id, "livemode": stripe_livemode()}, {"_id": 0})


async def save_status(db, stripe_account_id: str, account: dict, now: datetime) -> None:
    await db.wallet_accounts.update_one({"stripe_account_id": stripe_account_id},
                                        {"$set": {**status_of(account), "updated_at": now.isoformat()}})


async def create_or_get(db, client, *, user_id: str, email: str, country: str, now: datetime) -> dict:
    """The payee's wallet account for the current Stripe mode, creating the Express account once."""
    existing = await get_account(db, user_id)
    if existing and existing.get("stripe_account_id"):
        return existing
    acct = _d(await asyncio.to_thread(client.v1.accounts.create,
                                      account_params(user_id=user_id, email=email, country=country)))
    doc = {"user_id": user_id, "livemode": stripe_livemode(), "stripe_account_id": acct["id"],
           "country": country, "created_at": now.isoformat(), "updated_at": now.isoformat(),
           **status_of(acct)}
    await db.wallet_accounts.update_one({"user_id": user_id, "livemode": doc["livemode"]},
                                        {"$set": doc}, upsert=True)
    return doc


async def onboarding_link(client, stripe_account_id: str, *, site: str) -> str:
    link = _d(await asyncio.to_thread(client.v1.account_links.create, {
        "account": stripe_account_id, "type": "account_onboarding",
        "refresh_url": f"{site}/vault?tab=wallet&connect=refresh",
        "return_url": f"{site}/vault?tab=wallet&connect=done",
    }))
    return link["url"]


async def refresh_status(db, client, acct: dict, now: datetime) -> dict:
    account = _d(await asyncio.to_thread(client.v1.accounts.retrieve, acct["stripe_account_id"]))
    await save_status(db, acct["stripe_account_id"], account, now)
    return {**acct, **status_of(account)}


async def dashboard_link(client, stripe_account_id: str) -> str:
    link = _d(await asyncio.to_thread(client.v1.accounts.login_links.create, stripe_account_id))
    return link["url"]


# --------------------------------------------------------------------------- payout run (Part C)

PAYOUT_MIN_CENTS = 2500


def is_december(period: str) -> bool:
    return period.endswith("-12")


async def preview(db, period: str, *, livemode: bool) -> dict:
    """Who would be paid for `period`, and why the others are not."""
    test_mode = not livemode
    rows = await db.wallet_entries.find({"status": "available", "test_mode": test_mode},
                                        {"_id": 0, "payee_key": 1, "payee_user_id": 1, "payee_email": 1,
                                         "amount_cents": 1}).to_list(200000)
    totals: dict = {}
    for r in rows:
        t = totals.setdefault(r["payee_key"], {"payee_key": r["payee_key"], "user_id": r.get("payee_user_id"),
                                               "email": r.get("payee_email"), "amount_cents": 0})
        t["amount_cents"] += r["amount_cents"]
    out = {"pay": [], "below_minimum": [], "not_verified": [], "no_account": [], "unsupported": [], "negative": []}
    for key, t in sorted(totals.items()):
        acct = await db.wallet_accounts.find_one({"user_id": key, "livemode": livemode}, {"_id": 0}) \
            if not key.startswith("email:") else None
        t["stripe_account_id"] = (acct or {}).get("stripe_account_id")
        if t["amount_cents"] <= 0:
            out["negative" if t["amount_cents"] < 0 else "below_minimum"].append(t)
        elif key.startswith("email:") or not acct:
            out["no_account"].append(t)
        elif acct.get("unsupported_country"):
            out["unsupported"].append(t)
        elif not payout_ready(acct):
            out["not_verified"].append(t)
        elif t["amount_cents"] < PAYOUT_MIN_CENTS and not is_december(period):
            out["below_minimum"].append(t)
        else:
            out["pay"].append(t)
    out["total_to_pay_cents"] = sum(t["amount_cents"] for t in out["pay"])
    return out


async def run(db, client, period: str, *, livemode: bool, admin: str, now: datetime) -> dict:
    """Pay every eligible payee once. One Stripe Transfer per payee, with an idempotency
    key, so a second click or a retry after a crash never pays twice. A failed transfer
    puts that payee's lines back to available and records the error."""
    test_mode = not livemode
    results = {"paid": [], "failed": []}
    # 1. Finish any payout a previous run started but did not record (for example a crash).
    pending = await db.payouts.find({"status": "pending", "livemode": livemode}, {"_id": 0}).to_list(1000)
    plan = await preview(db, period, livemode=livemode)
    for t in plan["pay"]:
        attempt = await db.payouts.count_documents({"period": period, "payee_key": t["payee_key"],
                                                    "livemode": livemode})
        payout = {"id": f"po_{period}_{t['payee_key']}_{attempt + 1}".replace(":", "_"), "period": period,
                  "payee_key": t["payee_key"], "stripe_account_id": t["stripe_account_id"],
                  "amount_cents": t["amount_cents"], "livemode": livemode, "status": "pending",
                  "idempotency_key": f"payout:{period}:{t['payee_key']}:{attempt + 1}",
                  "created_at": now.isoformat(), "created_by": admin}
        res = await db.wallet_entries.update_many(
            {"payee_key": t["payee_key"], "status": "available", "test_mode": test_mode},
            {"$set": {"status": "in_payout", "payout_id": payout["id"]}})
        if not res.modified_count:
            continue
        claimed = await db.wallet_entries.find({"payout_id": payout["id"]}, {"_id": 0, "amount_cents": 1}).to_list(100000)
        payout["amount_cents"] = sum(c["amount_cents"] for c in claimed)
        await db.payouts.insert_one(dict(payout))
        pending.append(payout)
    for p in pending:
        try:
            tr = _d(await asyncio.to_thread(
                client.v1.transfers.create,
                {"amount": p["amount_cents"], "currency": "usd", "destination": p["stripe_account_id"],
                 "transfer_group": f"ovoxi-{p['period']}",
                 "metadata": {"payout_id": p["id"], "payee_key": p["payee_key"], "period": p["period"]}},
                {"idempotency_key": p["idempotency_key"]}))
        except Exception as exc:
            err = f"{type(exc).__name__}: {getattr(exc, 'user_message', None) or exc}"[:300]
            await db.wallet_entries.update_many({"payout_id": p["id"], "status": "in_payout"},
                                                {"$set": {"status": "available", "payout_id": None}})
            await db.payouts.update_one({"id": p["id"]}, {"$set": {"status": "failed", "error": err,
                                                                   "failed_at": now.isoformat()}})
            results["failed"].append({"payee_key": p["payee_key"], "amount_cents": p["amount_cents"], "error": err})
            continue
        await db.wallet_entries.update_many({"payout_id": p["id"], "status": "in_payout"},
                                            {"$set": {"status": "paid", "paid_at": now.isoformat()}})
        await db.payouts.update_one({"id": p["id"]}, {"$set": {"status": "paid", "stripe_transfer_id": tr.get("id"),
                                                               "paid_at": now.isoformat()}})
        results["paid"].append({"payee_key": p["payee_key"], "amount_cents": p["amount_cents"],
                                "stripe_transfer_id": tr.get("id")})
    results["paid_total_cents"] = sum(r["amount_cents"] for r in results["paid"])
    return results


async def ensure_payout_indexes(db) -> None:
    await db.payouts.create_index([("id", 1)], unique=True)
    await db.payouts.create_index([("period", 1), ("payee_key", 1)])
    await db.statements.create_index([("payee_key", 1), ("period", 1), ("test_mode", 1)], unique=True)
    await db.wallet_closes.create_index([("period", 1), ("test_mode", 1)], unique=True)
