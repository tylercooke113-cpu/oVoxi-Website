"""Clearance evaluator. See docs/PRD-03 section 5.

Pure: a track document in, check results and sync_status out. No DB access.
Runs only for sync-consented tracks; returns None for everything else.
"""
from typing import Optional

from sync_constants import MAX_MOODS, MAX_PARTIES, SAMPLE_DECLARATIONS, TOTAL_BP

STEM_NAMES = ("vocals", "instrumental", "drums", "bass", "other")
RIGHTS_SIDES = ("writers", "publishers", "master_owners")


def _ok():
    return {"result": "pass", "reason": None}


def _fail(reason):
    return {"result": "fail", "reason": reason}


def check_splits(doc: dict) -> dict:
    rights = doc.get("rights")
    if not rights:
        return _fail("splits_missing")
    for side in RIGHTS_SIDES:
        parties = rights.get(side) or []
        if not 1 <= len(parties) <= MAX_PARTIES:
            return _fail(f"splits_{side}")
        if sum(p.get("share_bp", 0) for p in parties) != TOTAL_BP:
            return _fail(f"splits_{side}")
    if not rights.get("attested_at"):
        return _fail("splits_not_attested")
    return _ok()


def check_fingerprint(doc: dict) -> dict:
    result = doc.get("fingerprint_result")
    if result is None:
        return {"result": "pending", "reason": "not_scanned"}
    if result == "CLEARED":
        return _ok()
    if result == "CONFLICT":
        return _fail("conflict")
    if result == "NEEDS_DOCS":
        return _fail("fingerprint_needs_docs")
    return _fail("fingerprint_scan_error")


def check_samples(doc: dict) -> dict:
    intake = doc.get("intake") or {}
    if intake.get("samples") in SAMPLE_DECLARATIONS and intake.get("samples_attested_at"):
        return _ok()
    return _fail("samples")


def check_content_id(doc: dict) -> dict:
    if (doc.get("intake") or {}).get("content_id") == "no":
        return _ok()
    return _fail("content_id")


def check_pro(doc: dict) -> dict:
    intake = doc.get("intake") or {}
    if intake.get("pro_not_affiliated") is True:
        return _ok()
    if intake.get("pro_name") and intake.get("ipi"):
        return _ok()
    return _fail("pro")


def check_metadata(doc: dict) -> dict:
    meta = doc.get("metadata") or {}
    missing = []
    if not doc.get("genre"):
        missing.append("genre")
    if not 1 <= len(meta.get("moods") or []) <= MAX_MOODS:
        missing.append("moods")
    if not meta.get("vocals"):
        missing.append("vocals")
    for field in ("bpm", "key", "duration_s"):
        if meta.get(field) in (None, ""):
            missing.append(field)
    stems = doc.get("stem_paths") or {}
    if not all(stems.get(name) for name in STEM_NAMES):
        missing.append("stems")
    # PRD-03 4.4: a value held for artist confirmation does not pass.
    confirm = [f for f in ("bpm", "key")
               if meta.get(f) not in (None, "") and meta.get(f"{f}_needs_confirmation") is True]
    parts = []
    if missing:
        parts.append("missing: " + ", ".join(missing))
    if confirm:
        parts.append("confirm: " + ", ".join(confirm))
    return _ok() if not parts else _fail("; ".join(parts))


CHECKS = (
    ("splits", check_splits),
    ("fingerprint", check_fingerprint),
    ("samples", check_samples),
    ("content_id", check_content_id),
    ("pro", check_pro),
    ("metadata", check_metadata),
)


def evaluate(doc: dict) -> Optional[dict]:
    """Return {"checks": {...}, "sync_status": ...}, or None when the track has
    no sync consent (AI-only tracks keep sync_status null)."""
    if (doc.get("consent") or {}).get("sync") is not True:
        return None
    checks = {name: fn(doc) for name, fn in CHECKS}
    if any(c["reason"] == "conflict" for c in checks.values()):
        status = "conflict"
    elif all(c["result"] == "pass" for c in checks.values()):
        status = "cleared"
    else:
        status = "needs_docs"
    return {"checks": checks, "sync_status": status}
