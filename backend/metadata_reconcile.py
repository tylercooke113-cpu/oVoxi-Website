"""Reconcile the artist's BPM and key with the detected values.
See docs/PRD-03 section 4.4 and decisions 11 and 12. Pure: no DB access.

The artist's answer is the source of truth. Detection is a cross-check:
agreement (including the known detector confusions) confirms the artist's
value; any other disagreement, or "I'm unsure", holds the value for one
artist confirmation in the Vault.
"""
from typing import Optional

from sync_constants import PITCHES

BPM_TOLERANCE = 0.015  # ±1.5%


def bpm_agrees(artist: float, detected: float) -> bool:
    """Same tempo, or the detector read half or double of it."""
    return any(abs(artist - detected * f) <= artist * BPM_TOLERANCE for f in (1.0, 2.0, 0.5))


def _parse_key(key: str) -> tuple:
    root, mode = key.split(" ")
    return PITCHES.index(root), mode


def key_agrees(artist: str, detected: str) -> bool:
    """Same key, same root with the opposite mode, or the relative key."""
    a_root, a_mode = _parse_key(artist)
    d_root, d_mode = _parse_key(detected)
    if a_root == d_root:
        return True  # same key, or parallel major/minor
    if a_mode == d_mode:
        return False
    major_root, minor_root = (a_root, d_root) if a_mode == "major" else (d_root, a_root)
    return (major_root + 9) % 12 == minor_root  # C major <-> A minor


def _resolve(artist: Optional[object], unsure: bool, detected: Optional[object], agrees) -> dict:
    if artist is not None:
        held = detected is not None and not agrees(artist, detected)
        return {"value": artist, "source": "artist", "needs_confirmation": held}
    if unsure and detected is not None:
        return {"value": detected, "source": "detected", "needs_confirmation": True}
    return {"value": None, "source": None, "needs_confirmation": False}


def reconcile(metadata: dict, bpm_detected: Optional[float], key_detected: Optional[str]) -> dict:
    """Return the `metadata.*` fields to $set after detection.

    Only tracks whose upload recorded an artist answer (a value, or unsure)
    are reconciled. Older tracks without one keep the Phase 3 behaviour:
    the detected value is used as-is.
    """
    out = {"metadata.bpm_detected": bpm_detected, "metadata.key_detected": key_detected}
    for field, detected, agrees in (("bpm", bpm_detected, bpm_agrees), ("key", key_detected, key_agrees)):
        answered = metadata.get(f"{field}_source") == "artist" or metadata.get(f"{field}_unsure") is True
        if not answered:
            if detected is not None:
                out[f"metadata.{field}"] = detected
                out[f"metadata.{field}_source"] = "detected"
            continue
        artist = metadata.get(field) if metadata.get(f"{field}_source") == "artist" else None
        r = _resolve(artist, metadata.get(f"{field}_unsure") is True, detected, agrees)
        out[f"metadata.{field}"] = r["value"]
        out[f"metadata.{field}_source"] = r["source"]
        out[f"metadata.{field}_needs_confirmation"] = r["needs_confirmation"]
    return out
