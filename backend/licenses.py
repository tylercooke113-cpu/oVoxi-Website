"""The `licenses` collection: one record per issued license, separate from orders
(Brief 17). Subscription licenses (Brief 19) will reuse build logic without an order.

Pure module: no DB or R2. Imports only pricing labels from sync_orders.
"""
import re
from datetime import datetime

from sync_orders import TIER_DESCRIPTIONS, tier_label

# Verification IDs: "OVX-" + 10 Crockford base32 chars (no I, L, O, U). Matches new_license_id.
LICENSE_ID_RE = re.compile(r"^OVX-[0-9A-HJKMNP-TV-Z]{10}$")


def license_label(license_type: str) -> str:
    try:
        return f"{tier_label(license_type)} license"
    except ValueError:
        return "License"


def license_scope(license_type: str, issued_at: str) -> dict:
    """Scope for the current tiers. Brief 18 replaces this with real per-tier scopes."""
    return {
        "territory": "Worldwide",
        "media_summary": TIER_DESCRIPTIONS.get(license_type, ""),
        "term_label": "Perpetual for the project",
        "term_start": None,
        "term_end": None,
        "paid_term_end": None,
        "media_spend_cap_cents": None,
    }


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
        "scope": license_scope(lic_type, issued_at),
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
