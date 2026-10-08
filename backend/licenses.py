"""The `licenses` collection: one record per issued license, separate from orders
(Brief 17). Subscription licenses (Brief 19) will reuse build logic without an order.

Pure module: no DB or R2. Imports only pricing labels from sync_orders.
"""
import calendar
import re
from datetime import datetime, timezone

from sync_constants import COUNTRIES, PLANS
from sync_orders import TIER_DESCRIPTIONS, tier_label

# Verification IDs: "OVX-" + 10 Crockford base32 chars (no I, L, O, U). Matches new_license_id.
LICENSE_ID_RE = re.compile(r"^OVX-[0-9A-HJKMNP-TV-Z]{10}$")


def license_label(license_type: str) -> str:
    try:
        return f"{tier_label(license_type)} license"
    except ValueError:
        return "License"


def _add_months(dt: datetime, months: int) -> datetime:
    """Calendar math. Adding months to Jan 31 lands on the last day of the target month."""
    total = dt.month - 1 + months
    year = dt.year + total // 12
    month = total % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


_YEARS = {"1y": 1, "2y": 2, "3y": 3, "5y": 5}


def _years_label(n: int) -> str:
    return f"{n} year{'s' if n != 1 else ''} from the license date"


def license_scope(license_type: str, issued_at: str, term: str = None, territory: str = None) -> dict:
    """Real per-tier scope (Brief 18). Terms run from the license date."""
    issued = datetime.fromisoformat(issued_at)
    base = {"territory": "Worldwide", "media_summary": "", "term_label": "Perpetual for the project",
            "term_start": issued_at, "term_end": None, "paid_term_end": None, "media_spend_cap_cents": None}
    if license_type == "creator":
        return {**base, "media_summary": "Your own channels, monetized. No client work, sponsored content or paid ads."}
    if license_type == "digital":
        return {**base, "media_summary": "Client and brand work, sponsored content, paid social and digital ads.",
                "term_label": "Organic use perpetual. Paid ads 12 months from the license date.",
                "paid_term_end": _add_months(issued, 12).isoformat(), "media_spend_cap_cents": 2500000}
    if license_type == "campaign":
        if term == "perpetual":
            term_label, end = "Perpetual", None
        else:
            n = _YEARS.get(term)
            if not n:
                raise ValueError(f"bad campaign term {term!r}")
            end, term_label = _add_months(issued, n * 12).isoformat(), _years_label(n)
        return {**base, "media_summary": "Digital uses plus out-of-home, retail, events, trade shows and displays.",
                "term_label": term_label, "term_end": end, "paid_term_end": end, "media_spend_cap_cents": 10000000}
    if license_type == "broadcast":
        n = _YEARS.get(term)
        if not n:
            raise ValueError(f"bad broadcast term {term!r}")
        return {**base, "territory": COUNTRIES.get(territory, territory or "Worldwide"),
                "media_summary": "Campaign uses plus TV, radio, OTT, CTV, VOD and film in one country.",
                "term_label": f"Ads: {_years_label(n)}. Programs and films: perpetual.",
                "term_end": None, "paid_term_end": _add_months(issued, n * 12).isoformat(),
                "media_spend_cap_cents": 25000000}
    if license_type == "sub_creator":
        return {**base, "media_summary": "Your own channels, including monetized content. "
                "No client work, sponsored content or paid ads."}
    if license_type == "sub_pro":
        return {**base, "media_summary": "Client and brand work, sponsored content, corporate video, "
                "paid social and digital ads.",
                "term_label": "Organic use perpetual. Paid placements 12 months from registration.",
                "paid_term_end": _add_months(issued, 12).isoformat(), "media_spend_cap_cents": 2500000}
    if license_type == "sub_business":
        return {**base, "media_summary": "Pro uses plus campaigns, events, trade shows, retail, "
                "digital displays and out-of-home.",
                "term_label": "Organic use perpetual. Paid, out-of-home and event use 1 year from registration.",
                "paid_term_end": _add_months(issued, 12).isoformat(), "media_spend_cap_cents": 10000000}
    # Legacy / unknown ids: perpetual, worldwide.
    return {**base, "media_summary": TIER_DESCRIPTIONS.get(license_type, "")}


SUB_TYPES = {"creator": "sub_creator", "pro": "sub_pro", "business": "sub_business"}


def build_subscription_license(*, license_id, user_id, buyer_email, plan, subscription_id, invoice_id,
                               track, project_name, client, include_stems, terms_version, now) -> dict:
    """A subscription-registered project license (Brief 19). owner_user_id is the subscriber."""
    issued_at = now.isoformat()
    lic_type = SUB_TYPES[plan]
    return {
        "license_id": license_id, "source": "subscription", "order_id": None,
        "subscription_id": subscription_id, "invoice_id": invoice_id,
        "owner_user_id": user_id, "buyer_email": (buyer_email or "").lower(),
        "licensee_name": "", "licensee_company": client or "",
        "track_id": track.get("id"), "track_title": track.get("track_name") or "",
        "artist_display_name": track.get("artist_name") or "", "artist_user_id": track.get("clerk_user_id"),
        "license_type": lic_type, "license_label": f"{PLANS[plan]['label']} plan", "plan": plan,
        "project": {"name": project_name, "client": client or ""},
        "scope": license_scope(lic_type, issued_at), "include_stems": bool(include_stems),
        "terms_version": terms_version, "test_mode": False, "status": "active",
        "cue_sheet": build_cue_sheet(track), "pdf_key": None,
        "publish_by": _add_months(now, 6).isoformat(),
        "issued_at": issued_at, "refunded_at": None, "created_at": issued_at,
    }


async def void_invoice_projects(db, invoice_id: str, reason: str) -> int:
    """Void every subscription license tied to this invoice (refund or lost dispute).
    Idempotent; never deletes. /verify then shows them as refunded (Brief 19 item 9)."""
    now = datetime.now(timezone.utc).isoformat()
    res = await db.licenses.update_many(
        {"source": "subscription", "invoice_id": invoice_id, "status": {"$ne": "refunded"}},
        {"$set": {"status": "refunded", "void_reason": reason, "voided_at": now, "refunded_at": now}})
    return res.modified_count


def build_cue_sheet(track: dict) -> list:
    """Writers, publishers and master owners from the track's stored rights."""
    rights = track.get("rights") or {}
    out = []
    for side, role in (("writers", "Writer"), ("publishers", "Publisher"),
                       ("master_owners", "Master owner")):
        for p in rights.get(side) or []:
            out.append({
                "name": p.get("legal_name") or "",
                "role": role,
                "society": p.get("society") or "Not affiliated",
                "ipi": p.get("ipi_name_number") or "",
            })
    return out


def build_license_from_order(order: dict, track: dict, now: datetime) -> dict:
    issued_at = order.get("paid_at") or order.get("created_at") or now.isoformat()
    lic_type = order["tier"]
    project = order.get("project") or {}
    return {
        "license_id": order["license_id"],
        "source": "order",
        "order_id": order["order_id"],
        "subscription_id": None,
        "owner_user_id": None,
        "buyer_email": (order.get("buyer_email") or "").lower(),
        "licensee_name": order.get("buyer_name") or "",
        "licensee_company": order.get("buyer_company") or "",
        "track_id": order.get("track_id"),
        "track_title": order.get("track_title") or "",
        "artist_display_name": order.get("artist_display_name") or "",
        "artist_user_id": order.get("artist_user_id"),
        "license_type": lic_type,
        "license_label": license_label(lic_type),
        "project": {"name": project.get("name") or "", "client": project.get("client") or ""},
        "scope": license_scope(lic_type, issued_at, term=order.get("term"), territory=order.get("territory")),
        "include_stems": bool(order.get("include_stems")),
        "terms_version": order.get("terms_version"),
        "test_mode": bool(order.get("test_mode")),
        "status": "active",
        "cue_sheet": build_cue_sheet(track),
        "pdf_key": order.get("license_pdf_key"),
        "issued_at": issued_at,
        "refunded_at": None,
        "created_at": now.isoformat(),
    }


def display_status(lic: dict, now: datetime) -> str:
    """Computed, never stored. Expiry derives from scope.term_end."""
    if lic.get("status") in ("refunded", "void"):
        return lic["status"]
    if lic.get("test_mode"):
        return "test"
    term_end = (lic.get("scope") or {}).get("term_end")
    if term_end and datetime.fromisoformat(term_end) < now:
        return "expired"
    return "active"


def public_view(lic: dict, now: datetime) -> dict:
    """Allowlist for the public verification page. No email, price, IPI or client."""
    scope = lic.get("scope") or {}
    return {
        "license_id": lic.get("license_id"),
        "track_title": lic.get("track_title"),
        "artist_display_name": lic.get("artist_display_name"),
        "license_label": lic.get("license_label"),
        "licensed_to": lic.get("licensee_company") or lic.get("licensee_name") or "",
        "project_name": (lic.get("project") or {}).get("name") or "",
        "territory": scope.get("territory"),
        "term_label": scope.get("term_label"),
        "term_end": scope.get("term_end"),
        "issued_at": lic.get("issued_at"),
        "terms_version": lic.get("terms_version"),
        "status": display_status(lic, now),
        "refunded_at": lic.get("refunded_at"),
    }


def owner_view(lic: dict, now: datetime, files=None) -> dict:
    """Everything the owner sees. Never buyer_email."""
    scope = lic.get("scope") or {}
    view = public_view(lic, now)
    view.update({
        "licensee_company": lic.get("licensee_company") or "",
        "client": (lic.get("project") or {}).get("client") or "",
        "media_summary": scope.get("media_summary"),
        "media_spend_cap_cents": scope.get("media_spend_cap_cents"),
        "paid_term_end": scope.get("paid_term_end"),
        "include_stems": bool(lic.get("include_stems")),
        "cue_sheet": lic.get("cue_sheet") or [],
        "files": files or [],
    })
    return view


async def ensure_indexes(db) -> None:
    await db.licenses.create_index([("license_id", 1)], unique=True)
    await db.licenses.create_index([("owner_user_id", 1), ("issued_at", -1)])
    await db.licenses.create_index([("buyer_email", 1), ("owner_user_id", 1)])
    await db.licenses.create_index([("order_id", 1)])
