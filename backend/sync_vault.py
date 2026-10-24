"""Vault helpers for PRD-03 Phase 4a. Pure: no DB access.

vault_track_view() is the ONLY place that decides what the Vault returns for
a track. It is an allowlist: anything not listed here never reaches the
artist (no intake answers, no splits, no ACRCloud match detail).
"""
import re
import unicodedata
from typing import Optional

from clearance import AI_CHECK_NAMES, SYNC_CHECK_NAMES
from exclusive import is_exclusive, sold_uses

VAULT_METADATA_FIELDS = (
    "moods", "vocals", "duration_s",
    "bpm", "bpm_source", "bpm_detected", "bpm_needs_confirmation",
    "key", "key_source", "key_detected", "key_needs_confirmation",
)

SPOTIFY_ARTIST_URL = re.compile(r"^https://open\.spotify\.com/artist/[A-Za-z0-9]{10,40}/?(\?[^\s]*)?$")
INSTAGRAM_URL = re.compile(r"^https://(www\.)?instagram\.com/[A-Za-z0-9._]{1,30}/?$")


def is_legacy(doc: dict) -> bool:
    """Uploaded before Phase 1: no usage choices were recorded."""
    return not isinstance(doc.get("consent"), dict)


def failed_reasons(doc: dict, names=None) -> list:
    """Reasons for checks that did not pass, limited to one use's checks when given."""
    checks = doc.get("checks") or {}
    return [c.get("reason") for n, c in checks.items()
            if (names is None or n in names)
            and isinstance(c, dict) and c.get("result") != "pass" and c.get("reason")]


def vault_track_view(doc: dict) -> dict:
    """Extra Vault fields for one track (added to the existing base fields)."""
    if is_legacy(doc):
        return {"legacy": True}
    meta = doc.get("metadata") or {}
    consent = doc.get("consent") or {}
    sync_on = consent.get("sync") is True
    ai_on = consent.get("ai_training") is True
    intake = doc.get("intake") or {}
    return {
        "legacy": False,
        "consent": {"ai_training": consent.get("ai_training") is True, "sync": sync_on,
                    "exclusive": is_exclusive(doc),
                    # Uses already licensed exclusively (Brief 25b): those stay off the catalog.
                    "exclusive_sold": {u: u in sold_uses(doc) for u in ("sync", "ai")}},
        "metadata": {k: meta.get(k) for k in VAULT_METADATA_FIELDS},
        "sync_status": doc.get("sync_status") if sync_on else None,
        "sync_reasons": failed_reasons(doc, SYNC_CHECK_NAMES) if sync_on else [],
        "ai_status": doc.get("ai_status") if ai_on else None,
        "ai_reasons": failed_reasons(doc, AI_CHECK_NAMES) if ai_on else [],
        # The catalog-listing flag for every use (Brief 25b D1).
        "on_sync_profile": bool(doc.get("on_sync_profile")) if (sync_on or ai_on) else False,
        # Older uploads never answered the samples / AI-tools questions (Brief 25b D1).
        "needs_declarations": not (intake.get("samples") and intake.get("ai_tools")),
        "delisted_by_admin": doc.get("sync_delisted_by_admin") is True,
        "cosign_required": doc.get("cosign_required") is True,
        "cosign_status": doc.get("cosign_status"),
    }


def slugify_profile(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:60].rstrip("-")


def metadata_patch_fields(bpm: Optional[float], key: Optional[str],
                          moods: Optional[list], genre: Optional[str]) -> dict:
    """$set fields for an artist edit. A BPM or key sent from the Vault is the
    artist's confirmed value (PRD-03 4.4): never held again by detection."""
    fields = {}
    if bpm is not None:
        fields.update({
            "metadata.bpm": bpm, "metadata.bpm_source": "artist",
            "metadata.bpm_unsure": False, "metadata.bpm_needs_confirmation": False,
            "metadata.bpm_confirmed": True,
        })
    if key is not None:
        fields.update({
            "metadata.key": key, "metadata.key_source": "artist",
            "metadata.key_unsure": False, "metadata.key_needs_confirmation": False,
            "metadata.key_confirmed": True,
        })
    if moods is not None:
        fields["metadata.moods"] = moods
    if genre is not None:
        fields["genre"] = genre
    return fields
