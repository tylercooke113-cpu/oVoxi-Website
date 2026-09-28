"""Vault helpers for PRD-03 Phase 4a. Pure: no DB access.

vault_track_view() is the ONLY place that decides what the Vault returns for
a track. It is an allowlist: anything not listed here never reaches the
artist (no intake answers, no splits, no ACRCloud match detail).
"""
import re
import unicodedata
from typing import Optional

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


def failed_reasons(doc: dict) -> list:
    checks = doc.get("checks") or {}
    return [c.get("reason") for c in checks.values()
            if isinstance(c, dict) and c.get("result") != "pass" and c.get("reason")]


def vault_track_view(doc: dict) -> dict:
    """Extra Vault fields for one track (added to the existing base fields)."""
    if is_legacy(doc):
        return {"legacy": True}
    meta = doc.get("metadata") or {}
    consent = doc.get("consent") or {}
    sync_on = consent.get("sync") is True
    return {
        "legacy": False,
        "consent": {"ai_training": consent.get("ai_training") is True, "sync": sync_on},
        "metadata": {k: meta.get(k) for k in VAULT_METADATA_FIELDS},
        "sync_status": doc.get("sync_status") if sync_on else None,
        "sync_reasons": failed_reasons(doc) if sync_on else [],
        "on_sync_profile": bool(doc.get("on_sync_profile")) if sync_on else False,
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
