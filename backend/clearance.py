"""Clearance evaluator. See docs/PRD-03 section 5 and Brief 25b Part D1.

Pure: a track document in, check results and a status per use out. No DB access.
A track opted into sync gets sync_status; one opted into AI training gets
ai_status. Content ID and PRO are sync-only checks; everything else applies to
both uses. Tracks with no use (or legacy tracks) return None.
"""
from typing import Optional

from sync_constants import AI_TOOLS_PASS, MAX_MOODS, MAX_PARTIES, SAMPLE_DECLARATIONS, TOTAL_BP

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


def _creator_emails(doc: dict) -> set:
    rights = doc.get("rights") or {}
    return {(p.get("email") or "").strip().lower()
            for side in RIGHTS_SIDES for p in (rights.get(side) or []) if p.get("email")}


def check_samples(doc: dict, use: str = "sync") -> dict:
    """Agreement 3.6. Original: both uses. Samples of other recordings: never. Loops:
    sync only, with every loop creator in the splits, a license on file for each loop,
    and Tyler's approval of the licenses. Creator consent is the cosign check."""
    intake = doc.get("intake") or {}
    answer = intake.get("samples")
    if answer not in SAMPLE_DECLARATIONS or not intake.get("samples_attested_at"):
        return _fail("samples")
    if answer == "original":
        return _ok()
    if answer == "cleared_sample":
        return _fail("samples_not_allowed")
    # royalty_free_loop
    if use == "ai":
        return _fail("samples_loop_ai")
    loops = intake.get("loops") or []
    if not loops:
        return _fail("loops_missing")
    emails = _creator_emails(doc)
    if any((lp.get("creator_email") or "").lower() not in emails for lp in loops):
        return _fail("loop_creator_not_listed")
    if any(not lp.get("license_key") for lp in loops):
        return _fail("loop_license_missing")
    review = (doc.get("loop_licenses_reviewed") or {}).get("result")
    if review == "approved":
        return _ok()
    if review == "rejected":
        return _fail("loop_license_rejected")
    return {"result": "pending", "reason": "loop_license_review"}


def check_content_id(doc: dict) -> dict:
    if (doc.get("intake") or {}).get("content_id") == "no":
        return _ok()
    return _fail("content_id")


def writers_missing_pro(rights: dict) -> list:
    """Names of writers without both a PRO and an IPI (Agreement 3.5: every writer)."""
    return [p.get("legal_name") or "A writer" for p in ((rights or {}).get("writers") or [])
            if not (p.get("society") and p.get("ipi_name_number"))]


def check_pro(doc: dict) -> dict:
    """Agreement 3.5: sync needs every writer affiliated with a PRO, with an IPI.
    "Not affiliated" no longer passes; such a song may be offered for AI training only."""
    intake = doc.get("intake") or {}
    if intake.get("pro_not_affiliated") is True or not (intake.get("pro_name") and intake.get("ipi")):
        return _fail("pro")
    if writers_missing_pro(doc.get("rights")):
        return _fail("pro_writers")
    return _ok()


def check_ai_tools(doc: dict) -> dict:
    """AI-tools disclosure (Agreement 9(e)). "partial" waits for an admin review."""
    intake = doc.get("intake") or {}
    answer = intake.get("ai_tools")
    if not answer or not intake.get("ai_tools_attested_at"):
        return _fail("ai_tools")
    if answer in AI_TOOLS_PASS:
        return _ok()
    if answer == "partial":
        review = (doc.get("ai_tools_reviewed") or {}).get("result")
        if review == "approved":
            return _ok()
        if review == "rejected":
            return _fail("ai_tools_rejected")
        return {"result": "pending", "reason": "ai_tools_review"}
    return _fail("ai_tools_full")


def check_cosign(doc: dict) -> dict:
    # Grandfather rule: tracks uploaded before co-owner sign-off shipped have no
    # cosign_required field, so they pass untouched.
    if doc.get("cosign_required") is not True:
        return _ok()
    status = doc.get("cosign_status")
    if status == "complete":
        return _ok()
    if status == "declined":
        return _fail("cosign_declined")
    return _fail("cosign_pending")


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


# Order matters only for display. COMMON_CHECKS apply to every use.
COMMON_CHECKS = (
    ("splits", check_splits),
    ("fingerprint", check_fingerprint),
    ("ai_tools", check_ai_tools),
    ("cosign", check_cosign),
    ("metadata", check_metadata),
)
SYNC_ONLY_CHECKS = (
    ("samples", lambda d: check_samples(d, "sync")),
    ("content_id", check_content_id),
    ("pro", check_pro),
)
# Samples differ by use (loops are sync-only), so AI training has its own samples check.
AI_ONLY_CHECKS = (
    ("samples_ai", lambda d: check_samples(d, "ai")),
)
SYNC_CHECK_NAMES = tuple(n for n, _ in COMMON_CHECKS + SYNC_ONLY_CHECKS)
AI_CHECK_NAMES = tuple(n for n, _ in COMMON_CHECKS + AI_ONLY_CHECKS)


def _status(checks: dict, names) -> str:
    picked = [checks[n] for n in names]
    if any(c["reason"] == "conflict" for c in picked):
        return "conflict"
    if all(c["result"] == "pass" for c in picked):
        return "cleared"
    return "needs_docs"


def evaluate(doc: dict) -> Optional[dict]:
    """Return {"checks", "sync_status", "ai_status"}, or None when the track has no
    use opted in. A status is None for a use the track is not opted into."""
    consent = doc.get("consent")
    if not isinstance(consent, dict):
        return None
    sync_on = consent.get("sync") is True
    ai_on = consent.get("ai_training") is True
    if not (sync_on or ai_on):
        return None
    checks = {name: fn(doc) for name, fn in COMMON_CHECKS}
    if sync_on:
        checks.update({name: fn(doc) for name, fn in SYNC_ONLY_CHECKS})
    if ai_on:
        checks.update({name: fn(doc) for name, fn in AI_ONLY_CHECKS})
    return {
        "checks": checks,
        "sync_status": _status(checks, SYNC_CHECK_NAMES) if sync_on else None,
        "ai_status": _status(checks, AI_CHECK_NAMES) if ai_on else None,
    }


def clearance_fields(doc: dict, now_iso: str) -> dict:
    """The $set for a track after evaluation. on_sync_profile is the catalog-listing
    flag for every use (the name predates AI listing): on when any opted use clears
    and an admin has not delisted the track. sync_listed_at moves only when the
    track goes from unlisted to listed."""
    result = evaluate(doc)
    if result is None:
        fields = {"checks": None, "sync_status": None, "ai_status": None}
    else:
        fields = dict(result)
    listed = ("cleared" in (fields["sync_status"], fields["ai_status"])
              and doc.get("sync_delisted_by_admin") is not True)
    fields["on_sync_profile"] = listed
    fields["clearance_evaluated_at"] = now_iso
    if listed and not doc.get("on_sync_profile"):
        fields["sync_listed_at"] = now_iso
    return fields
