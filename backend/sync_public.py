"""Public sync pages. See docs/PRD-03 sections 3.2, 6.2, 6.3, 11 and
decisions 17 and 18. Pure: no DB, no R2.

Everything that leaves the server on a public page goes through
public_track_view() or public_profile_view(). Both are allowlists.
"""
from typing import Optional

# PRD-03 3.2: a track is listed only when all of these hold.
LISTING_FILTER = {
    "sync_status": "cleared",
    "consent.sync": True,
    "intake.content_id": "no",
    "on_sync_profile": True,
    "sync_delisted_by_admin": {"$ne": True},
}

PROFILE_FIELDS = ("slug", "display_name", "location", "bio", "spotify_url", "instagram_url")


def is_listed(doc: dict) -> bool:
    return (doc.get("sync_status") == "cleared"
            and (doc.get("consent") or {}).get("sync") is True
            and (doc.get("intake") or {}).get("content_id") == "no"
            and doc.get("on_sync_profile") is True
            and doc.get("sync_delisted_by_admin") is not True)


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
