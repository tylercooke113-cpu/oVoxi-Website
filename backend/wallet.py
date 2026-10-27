"""OVOXI Wallet ledger (Brief 27 Part A). Artist Agreement v5 sections 7 and 8.

Money is integer cents. `wallet_entries` is append-only: a refund or a lost dispute
writes new negative lines, never edits old ones. Every write is idempotent through a
unique index on (source_type, source_id, track_id, payee_key), so a replayed Stripe
event or a second close writes nothing new.

Statuses: accrued (earned this month) -> available (after the month is closed) ->
in_payout -> paid. A track under a claim hold (8.5) gets `held` lines instead.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from pymongo.errors import DuplicateKeyError

from sync_constants import TOTAL_BP

RATE_STANDARD_BP = 3300    # 7.1: 33% of Net Revenue
RATE_EXCLUSIVE_BP = 4000   # 7.1 and 3.4(i): 40% for Exclusive Licenses
POOL_BP = 3300             # 7.6: Artist Pool is 33% of subscription Net Revenue

SOURCE_TYPES = ("order", "sub_pool", "exclusive", "refund", "dispute", "adjustment")
STATUSES = ("accrued", "held", "available", "in_payout", "paid", "reversed")


# --------------------------------------------------------------------------- pure helpers

def payee_key(user_id: Optional[str] = None, email: Optional[str] = None) -> str:
    """The Clerk user id when known, else email:<lowercased email>."""
    if user_id:
        return user_id
    if email:
        return f"email:{email.strip().lower()}"
    raise ValueError("A payee needs a user id or an email.")


def period_of(iso: str) -> str:
    """'2026-10-27T…' -> '2026-10'."""
    return (iso or "")[:7]


def net_revenue(amount_cents: int, *, fee_cents: int = 0, tax_cents: int = 0) -> int:
    """7.2: amount actually received, less processing and currency fees and taxes.
    Refunds and chargebacks are written as their own negative lines."""
    return int(amount_cents or 0) - int(fee_cents or 0) - int(tax_cents or 0)


def revenue_share(net_cents: int, rate_bp: int) -> int:
    """Rate applied to Net Revenue, rounded to the nearest cent (half up)."""
    n = int(net_cents) * int(rate_bp)
    return (n + TOTAL_BP // 2) // TOTAL_BP if n >= 0 else -((-n + TOTAL_BP // 2) // TOTAL_BP)


def _owns_everything(rights: dict) -> bool:
    if not rights or rights.get("owns_everything"):
        return True
    rows = [p for side in ("writers", "publishers", "master_owners") for p in (rights.get(side) or [])]
    return not rows or all(p.get("is_self") for p in rows)


def split_share(share_cents: int, *, rights: dict, licensor_user_id: str,
                registered_emails: set) -> list:
    """7.4 and 7.7. Returns [{payee_key, user_id, email, roles, share_bp, amount_cents}].

    - The Licensor owns 100% (or no splits entered): everything to the Licensor.
    - Otherwise 50% follows the composition (half to writers, half to publishers, each
      by share_bp) and 50% follows the master owners by share_bp.
    - A party who is not registered (no signed Co-owner Consent) is paid through the
      Licensor (7.4), as is any part of a side whose shares do not add up to 100%.
    - Rounding cents go to the Licensor, so the lines always add up to share_cents.
    """
    licensor = payee_key(licensor_user_id)
    lines: dict = {}

    def add(key, amount, *, role, user_id=None, email=None, weight=0):
        line = lines.setdefault(key, {"payee_key": key, "user_id": user_id, "email": email,
                                      "roles": [], "share_bp": 0, "amount_cents": 0})
        line["amount_cents"] += amount
        line["share_bp"] += weight
        if role not in line["roles"]:
            line["roles"].append(role)

    if _owns_everything(rights):
        add(licensor, share_cents, role="licensor", user_id=licensor_user_id, weight=TOTAL_BP)
        return list(lines.values())

    registered = {e.strip().lower() for e in registered_emails if e}
    # Weights in units of 1 / (4 * TOTAL_BP): writers and publishers each get a quarter of
    # the share at 100%, master owners half.
    unit = 4 * TOTAL_BP
    sides = (("writers", "writer", 1), ("publishers", "publisher", 1), ("master_owners", "master_owner", 2))
    allocated = 0
    for side, role, mult in sides:
        for p in (rights.get(side) or []):
            weight = int(p.get("share_bp") or 0) * mult
            amount = (share_cents * weight) // unit if share_cents >= 0 else -((-share_cents * weight) // unit)
            email = (p.get("email") or "").strip().lower()
            if p.get("is_self") or not email or email not in registered:
                add(licensor, amount, role="licensor", user_id=licensor_user_id)
            else:
                add(payee_key(email=email), amount, role=role, email=email, weight=int(p.get("share_bp") or 0))
            allocated += amount
    # Unassigned shares and rounding remainder: to the Licensor.
    remainder = share_cents - allocated
    if remainder or licensor not in lines:
        add(licensor, remainder, role="licensor", user_id=licensor_user_id)
    return [l for l in lines.values() if l["amount_cents"] or l["payee_key"] == licensor]


def scale_lines(original: list, target_cents: int) -> list:
    """Spread target_cents over the payees of `original` in proportion to their amounts,
    with the remainder on the first line (the Licensor's when present). Used for refunds."""
    total = sum(l["amount_cents"] for l in original)
    if not total:
        return []
    ordered = sorted(original, key=lambda l: 0 if "licensor" in (l.get("roles") or [l.get("role")]) else 1)
    out, used = [], 0
    for l in ordered:
        amt = int(target_cents * l["amount_cents"] / total)
        out.append({**l, "amount_cents": amt})
        used += amt
    out[0]["amount_cents"] += target_cents - used
    return out


# --------------------------------------------------------------------------- database

async def ensure_indexes(db) -> None:
    await db.wallet_entries.create_index(
        [("source_type", 1), ("source_id", 1), ("track_id", 1), ("payee_key", 1)], unique=True)
    await db.wallet_entries.create_index([("payee_key", 1), ("created_at", -1)])
    await db.wallet_entries.create_index([("status", 1), ("period", 1)])
    await db.wallet_holds.create_index([("track_id", 1), ("released_at", 1)])


async def registered_emails(db, track_id: str) -> set:
    """Co-owners registered on the Platform for a track: a signed Co-owner Consent (7.4;
    Co-owner Consent 3.1)."""
    rows = await db.cosign_requests.find({"track_id": track_id, "status": "signed"},
                                         {"_id": 0, "email": 1}).to_list(200)
    return {(r.get("email") or "").strip().lower() for r in rows if r.get("email")}


async def track_held(db, track_id: str) -> bool:
    return bool(await db.wallet_holds.find_one({"track_id": track_id, "released_at": None}, {"_id": 1}))


async def write_lines(db, lines: list, *, source_type: str, source_id: str, track_id: str,
                      field: str, period: str, net_cents: int, rate_bp: int, test_mode: bool,
                      now: datetime, status: Optional[str] = None, extra: Optional[dict] = None) -> int:
    """Append one entry per payee. Returns the number written (0 on a replay)."""
    if source_type not in SOURCE_TYPES:
        raise ValueError(f"Unknown source type {source_type}")
    held = await track_held(db, track_id)
    written = 0
    for l in lines:
        doc = {
            "id": str(uuid.uuid4()),
            "payee_key": l["payee_key"], "payee_user_id": l.get("user_id"), "payee_email": l.get("email"),
            "roles": l.get("roles") or [], "share_bp": l.get("share_bp", 0),
            "source_type": source_type, "source_id": source_id, "track_id": track_id,
            "field": field, "period": period, "net_cents": int(net_cents), "rate_bp": int(rate_bp),
            "amount_cents": int(l["amount_cents"]),
            "status": status or ("held" if held else "accrued"),
            "payout_id": None, "test_mode": bool(test_mode),
            "created_at": now.isoformat(), **(extra or {}),
        }
        try:
            await db.wallet_entries.insert_one(doc)
            written += 1
        except DuplicateKeyError:
            pass
    return written


async def credit_sale(db, *, track: dict, source_type: str, source_id: str, field: str,
                      amount_cents: int, fee_cents: int, tax_cents: int, rate_bp: int,
                      paid_at: str, test_mode: bool, now: Optional[datetime] = None,
                      extra: Optional[dict] = None) -> int:
    """Credit one sale of one track: Net Revenue, the rate, then the split."""
    now = now or datetime.now(timezone.utc)
    net = net_revenue(amount_cents, fee_cents=fee_cents, tax_cents=tax_cents)
    share = revenue_share(net, rate_bp)
    lines = split_share(share, rights=track.get("rights") or {},
                        licensor_user_id=track["clerk_user_id"],
                        registered_emails=await registered_emails(db, track["id"]))
    return await write_lines(db, lines, source_type=source_type, source_id=source_id, track_id=track["id"],
                             field=field, period=period_of(paid_at), net_cents=net, rate_bp=rate_bp,
                             test_mode=test_mode, now=now, extra={"fee_cents": int(fee_cents or 0),
                                                                  "tax_cents": int(tax_cents or 0),
                                                                  "gross_cents": int(amount_cents or 0),
                                                                  **(extra or {})})


async def credit_order(db, order: dict, track: dict, *, fee_cents: int, now: Optional[datetime] = None) -> int:
    """A paid single-track order (sync, 33%)."""
    return await credit_sale(db, track=track, source_type="order", source_id=order["order_id"], field="sync",
                             amount_cents=order.get("amount_total_cents") or 0, fee_cents=fee_cents,
                             tax_cents=order.get("tax_cents") or 0, rate_bp=RATE_STANDARD_BP,
                             paid_at=order.get("paid_at") or (now or datetime.now(timezone.utc)).isoformat(),
                             test_mode=bool(order.get("test_mode")), now=now)


async def credit_exclusive_payment(db, lic: dict, track: dict, *, payment_id: str, amount_cents: int,
                                   fee_cents: int, tax_cents: int, received_at: str,
                                   test_mode: bool = False, now: Optional[datetime] = None) -> int:
    """A payment received for an Exclusive License (40%). `lic` is the exclusive_licenses row."""
    uses = sorted(lic.get("uses") or [])
    field = "+".join(uses) if uses else "sync"
    return await credit_sale(db, track=track, source_type="exclusive", source_id=payment_id, field=field,
                             amount_cents=amount_cents, fee_cents=fee_cents, tax_cents=tax_cents,
                             rate_bp=RATE_EXCLUSIVE_BP, paid_at=received_at, test_mode=test_mode, now=now,
                             extra={"exclusive_license_id": lic.get("id")})


async def reverse_order(db, order: dict, *, kind: str, refunded_cents: int,
                        now: Optional[datetime] = None) -> int:
    """Refund or lost dispute on a single-track order: negative lines that mirror the sale.

    The reversal never exceeds what the sale credited, so a full refund or a lost dispute
    takes each payee back to exactly zero for that order (Stripe keeps its fee on a refund;
    OVOXI does not pass that fee on to the payees). A partial refund reverses the refunded
    amount less its proportional tax. `refunded_cents` is cumulative, as Stripe reports it,
    so each new refund writes only the difference.
    """
    now = now or datetime.now(timezone.utc)
    oid = order["order_id"]
    originals = await db.wallet_entries.find({"source_type": "order", "source_id": oid},
                                             {"_id": 0}).to_list(200)
    if not originals:
        return 0
    credited = sum(e["amount_cents"] for e in originals)
    gross = int(order.get("amount_total_cents") or 0)
    tax = int(order.get("tax_cents") or 0)
    rate = originals[0]["rate_bp"]
    if kind == "dispute" or refunded_cents >= gross:
        target = -credited
    else:
        tax_part = (refunded_cents * tax) // gross if gross else 0
        target = max(-credited, -revenue_share(refunded_cents - tax_part, rate))
    done = sum(e["amount_cents"] for e in await db.wallet_entries.find(
        {"source_type": {"$in": ["refund", "dispute"]}, "reverses": oid}, {"_id": 0, "amount_cents": 1}).to_list(200))
    delta = target - done
    if not delta:
        return 0
    lines = scale_lines([{"payee_key": e["payee_key"], "user_id": e.get("payee_user_id"),
                          "email": e.get("payee_email"), "roles": e.get("roles"), "share_bp": e.get("share_bp"),
                          "amount_cents": e["amount_cents"]} for e in originals], delta)
    src = f"{oid}:{kind}:{refunded_cents if kind == 'refund' else 'lost'}"
    return await write_lines(db, lines, source_type=kind, source_id=src, track_id=order["track_id"],
                             field="sync", period=period_of(now.isoformat()), net_cents=0, rate_bp=rate,
                             test_mode=bool(order.get("test_mode")), now=now, extra={"reverses": oid})


async def hold_track(db, track_id: str, *, reason: str, admin: str, now: Optional[datetime] = None) -> None:
    """8.5: hold a track's Revenue Share while a claim is open."""
    now = now or datetime.now(timezone.utc)
    if not await track_held(db, track_id):
        await db.wallet_holds.insert_one({"track_id": track_id, "reason": reason, "admin": admin,
                                          "created_at": now.isoformat(), "released_at": None})
    for status in ("accrued", "available"):    # remember where each line was, for the release
        await db.wallet_entries.update_many({"track_id": track_id, "status": status},
                                            {"$set": {"status": "held", "held_from": status, "hold_reason": reason}})


async def release_track(db, track_id: str, *, admin: str, now: Optional[datetime] = None) -> None:
    """End a hold. Lines go back to the status they had (new lines written during the
    hold go to accrued, and the next close makes them available)."""
    now = now or datetime.now(timezone.utc)
    await db.wallet_holds.update_many({"track_id": track_id, "released_at": None},
                                      {"$set": {"released_at": now.isoformat(), "released_by": admin}})
    await db.wallet_entries.update_many({"track_id": track_id, "status": "held", "held_from": "available"},
                                        {"$set": {"status": "available"}, "$unset": {"hold_reason": "", "held_from": ""}})
    await db.wallet_entries.update_many({"track_id": track_id, "status": "held"},
                                        {"$set": {"status": "accrued"}, "$unset": {"hold_reason": "", "held_from": ""}})


async def claim_email_entries(db, *, user_id: str, email: str) -> int:
    """A co-owner who signs up with the invited, verified email takes over the lines kept
    for that email (Co-owner Consent 3.2). Returns how many lines moved."""
    old = payee_key(email=email)
    moved = 0
    for e in await db.wallet_entries.find({"payee_key": old}, {"_id": 0, "id": 1}).to_list(100000):
        try:
            res = await db.wallet_entries.update_one({"id": e["id"], "payee_key": old},
                                                     {"$set": {"payee_key": user_id, "payee_user_id": user_id,
                                                               "claimed_from": old}})
            moved += res.modified_count
        except DuplicateKeyError:
            pass   # the same person already has a line for that sale under their account
    await db.statements.update_many({"payee_key": old}, {"$set": {"payee_key": user_id, "claimed_from": old}})
    return moved


ENTRY_LABELS = {"order": "Sync license", "sub_pool": "Subscription pool", "exclusive": "Exclusive License",
                "refund": "Refund", "dispute": "Chargeback", "adjustment": "Adjustment"}


def entry_view(e: dict, titles: dict) -> dict:
    return {"id": e["id"], "date": e["created_at"], "track_id": e["track_id"],
            "track_title": titles.get(e["track_id"]) or "", "kind": ENTRY_LABELS.get(e["source_type"], e["source_type"]),
            "field": e.get("field"), "share_bp": e.get("share_bp"), "roles": e.get("roles") or [],
            "amount_cents": e["amount_cents"], "status": e["status"], "period": e.get("period"),
            "test_mode": bool(e.get("test_mode"))}


def summarize(entries: list, *, this_period: str) -> dict:
    """The four Wallet numbers."""
    s = {"earned_this_month_cents": 0, "available_cents": 0, "held_cents": 0, "paid_cents": 0,
         "pending_cents": 0}
    for e in entries:
        amt, st = e["amount_cents"], e["status"]
        if st == "accrued":
            s["pending_cents"] += amt
            if e.get("period") == this_period:
                s["earned_this_month_cents"] += amt
        elif st == "available" or st == "in_payout":
            s["available_cents"] += amt
        elif st == "held":
            s["held_cents"] += amt
        elif st == "paid":
            s["paid_cents"] += amt
    return s
