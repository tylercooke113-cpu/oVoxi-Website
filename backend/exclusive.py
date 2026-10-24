"""Exclusive songs (Brief 25b Part B; Artist Agreement v5 section 3.4).

An exclusive song is never sold to multiple buyers. Its only offer is one outright
exclusive license per use, by quote: sync, AI training, or both. When one is
recorded, the song comes down at once for the licensed use(s).

Pure helpers, plus record_exclusive_license(), the one writer of an exclusive sale.
"""
import uuid
from datetime import datetime
from typing import Optional

USES = ("sync", "ai")
CONSENT_KEY = {"sync": "sync", "ai": "ai_training"}
USE_LABELS = {"sync": "sync", "ai": "AI training"}
EXCLUSIVE_RATE_BP = 4000          # Agreement 3.4(i): 40% of Net Revenue, used by Brief 27
EXCLUSIVE_ONLY_DETAIL = "This song is offered as an exclusive license only. Request a quote."
DEFAULT_TERM = "Perpetual"
DEFAULT_TERRITORY = "Worldwide"


class ExclusiveError(ValueError):
    """A sale that cannot be recorded. str(exc) is safe to show an admin."""


def is_exclusive(doc: dict) -> bool:
    return (doc.get("consent") or {}).get("exclusive") is True


def opted_uses(doc: dict) -> list:
    c = doc.get("consent") or {}
    return [u for u in USES if c.get(CONSENT_KEY[u]) is True]


def sold_uses(doc: dict) -> list:
    sold = doc.get("exclusive_sold") or {}
    return [u for u in USES if sold.get(u)]


def use_available(doc: dict, use: str) -> bool:
    """Opted into the use and not already sold exclusively for it."""
    return use in opted_uses(doc) and use not in sold_uses(doc)


def fully_sold(doc: dict) -> bool:
    """Every opted use has been sold exclusively: nothing is left to offer."""
    opted = opted_uses(doc)
    return bool(opted) and all(u in sold_uses(doc) for u in opted)


def uses_label(uses) -> str:
    return " and ".join(USE_LABELS[u] for u in USES if u in uses)


def _price(v, name: str) -> int:
    if not isinstance(v, int) or isinstance(v, bool) or v <= 0:
        raise ExclusiveError(f"Enter a price for {name}.")
    return v


def build_exclusive_license(*, track: dict, uses: list, buyer_name: str, buyer_company: str,
                            buyer_email: str, price_cents_sync: Optional[int],
                            price_cents_ai: Optional[int], granted_by: str, now: datetime,
                            term: str = DEFAULT_TERM, territory: str = DEFAULT_TERRITORY,
                            quote_id: Optional[str] = None) -> dict:
    """Validate and build one exclusive_licenses record. Raises ExclusiveError."""
    uses = [u for u in USES if u in (uses or [])]
    if not uses or len(uses) != len(set(uses or [])):
        raise ExclusiveError("Choose sync, AI training or both.")
    if not is_exclusive(track):
        raise ExclusiveError("This song is not offered as exclusive.")
    for u in uses:
        if u not in opted_uses(track):
            raise ExclusiveError(f"This song is not opted into {USE_LABELS[u]}.")
        if u in sold_uses(track):
            raise ExclusiveError(f"This song is already licensed exclusively for {USE_LABELS[u]}.")
    if not (buyer_name or "").strip() or not (buyer_email or "").strip():
        raise ExclusiveError("Enter the buyer's name and email.")
    p_sync = _price(price_cents_sync, "sync") if "sync" in uses else None
    p_ai = _price(price_cents_ai, "AI training") if "ai" in uses else None
    return {
        "id": str(uuid.uuid4()),
        "track_id": track["id"],
        "uses": uses,
        "buyer_name": buyer_name.strip(),
        "buyer_company": (buyer_company or "").strip(),
        "buyer_email": buyer_email.strip().lower(),
        "price_cents_sync": p_sync,
        "price_cents_ai": p_ai,
        "total_cents": (p_sync or 0) + (p_ai or 0),     # the price for both is the sum (3.4(b))
        "rate_bp": EXCLUSIVE_RATE_BP,
        "term": (term or "").strip() or DEFAULT_TERM,
        "territory": (territory or "").strip() or DEFAULT_TERRITORY,
        "granted_at": now.isoformat(),
        "granted_by": granted_by,
        "quote_id": quote_id,
    }


async def record_exclusive_license(db, lic: dict) -> None:
    """Mark the track sold for the license's uses (guarded, so two sales of the same
    use cannot both land), then store the license. Takedown is immediate: every
    listing and sale path reads exclusive_sold."""
    guard = {"id": lic["track_id"], "consent.exclusive": True,
             **{f"exclusive_sold.{u}": None for u in lic["uses"]}}
    res = await db.track_submissions.update_one(
        guard, {"$set": {f"exclusive_sold.{u}": lic["id"] for u in lic["uses"]}})
    if getattr(res, "matched_count", 0) != 1:
        raise ExclusiveError("This song was just licensed exclusively. Reload and check.")
    try:
        await db.exclusive_licenses.insert_one(dict(lic))
    except Exception:
        await db.track_submissions.update_one(
            {"id": lic["track_id"]}, {"$set": {f"exclusive_sold.{u}": None for u in lic["uses"]}})
        raise
