"""Public sync pages. See docs/PRD-03 sections 3.2, 6.2, 6.3, 11 and
decisions 17 and 18. Pure: no DB, no R2.

Everything that leaves the server on a public page goes through
public_track_view() or public_profile_view(). Both are allowlists.
"""
from typing import Optional

# PRD-03 3.2 and Brief 25b Part D1: a track is in the OVOXI Catalog when it is
# listed for at least one use. on_sync_profile is the listing flag for every use.
_LISTED_COMMON = {
    "on_sync_profile": True,
    "sync_delisted_by_admin": {"$ne": True},
}
SYNC_LISTED = {
    "sync_status": "cleared",
    "consent.sync": True,
    "intake.content_id": "no",
    "exclusive_sold.sync": None,        # sold exclusively for sync -> down at once
}
AI_LISTED = {
    "ai_status": "cleared",
    "consent.ai_training": True,
    "exclusive_sold.ai": None,          # sold exclusively for AI training -> down at once
}
SYNC_LISTING_FILTER = {**_LISTED_COMMON, **SYNC_LISTED}
AI_LISTING_FILTER = {**_LISTED_COMMON, **AI_LISTED}
LISTING_FILTER = {**_LISTED_COMMON, "$or": [SYNC_LISTED, AI_LISTED]}

PROFILE_FIELDS = ("slug", "display_name", "location", "bio", "spotify_url", "instagram_url")


def listed_for(doc: dict, use: str) -> bool:
    """Listed in the catalog for one use: "sync" or "ai"."""
    if doc.get("on_sync_profile") is not True or doc.get("sync_delisted_by_admin") is True:
        return False
    consent = doc.get("consent") or {}
    sold = doc.get("exclusive_sold") or {}
    if use == "sync":
        return (doc.get("sync_status") == "cleared" and consent.get("sync") is True
                and (doc.get("intake") or {}).get("content_id") == "no" and not sold.get("sync"))
    if use == "ai":
        return (doc.get("ai_status") == "cleared" and consent.get("ai_training") is True
                and not sold.get("ai"))
    raise ValueError(f"unknown use {use!r}")


def available_for(doc: dict) -> list:
    return [u for u in ("sync", "ai") if listed_for(doc, u)]


def is_listed(doc: dict) -> bool:
    """In the catalog for at least one use."""
    return bool(available_for(doc))


def public_track_view(doc: dict, profile: Optional[dict]) -> dict:
    meta = doc.get("metadata") or {}
    return {
        "id": doc.get("id"),
        "track_name": doc.get("track_name"),
        "artist_display_name": (profile or {}).get("display_name") or doc.get("artist_name"),
        "artist_slug": (profile or {}).get("slug"),
        "genre": doc.get("genre"),
        "moods": list(meta.get("moods") or []),
        "vocals": meta.get("vocals"),
        "bpm": meta.get("bpm"),
        "key": meta.get("key"),
        "duration_s": meta.get("duration_s"),
        "has_preview": bool(doc.get("preview_key")),
        "has_waveform": bool(doc.get("waveform_key")),
        "exclusive": (doc.get("consent") or {}).get("exclusive") is True,
        "ai_training": (doc.get("consent") or {}).get("ai_training") is True,
        "available_for": available_for(doc),
    }


def public_profile_view(profile: dict, show_hidden: bool) -> dict:
    """Photo and bio are removed when an admin has hidden them, for everyone
    except admins (PRD-03 9: admin can hide a profile's photo and bio)."""
    hidden = profile.get("hidden_by_admin") is True
    view = {k: profile.get(k) for k in PROFILE_FIELDS}
    view["hidden_by_admin"] = hidden if show_hidden else False
    if hidden and not show_hidden:
        view["bio"] = ""
    return view


def photo_visible(profile: dict, show_hidden: bool) -> bool:
    return bool(profile.get("photo_key")) and (show_hidden or profile.get("hidden_by_admin") is not True)
