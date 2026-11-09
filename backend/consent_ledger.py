"""Append-only consent ledger. See docs/PRD-03 section 8.2.

This module only inserts. There is no update or delete function and none
should be added: every change of consent is a new event.
"""
import os
from datetime import datetime, timezone

GRANT_VERSION = os.environ.get("SYNC_GRANT_VERSION", "draft-0")

# Brief 28 B3: the only reasons a grant or withdrawal may carry. A value outside this set
# is rejected, so a typo never reaches the ledger. "artist_withdrawal" is the ordinary
# artist removal; "not_intended" is the 12.4 last-sentence removal on a delegated track;
# the three "admin_takedown_*" reasons are the 2.3(f) admin takedown.
REASON_CODES = frozenset({
    "artist_withdrawal",
    "not_intended",
    "admin_takedown_artist_request",
    "admin_takedown_upload_error",
    "admin_takedown_rights",
})


async def record_grants(db, *, user_id, track_id, scopes, source, ip, agreement=None,
                        actor_user_id=None, authorization_id=None,
                        acting_admin_user_id=None, reason=None):
    await _record(db, "grant", user_id=user_id, track_id=track_id,
                  scopes=scopes, source=source, ip=ip, agreement=agreement,
                  actor_user_id=actor_user_id, authorization_id=authorization_id,
                  acting_admin_user_id=acting_admin_user_id, reason=reason)


async def record_withdrawals(db, *, user_id, track_id, scopes, source, ip,
                             actor_user_id=None, authorization_id=None,
                             acting_admin_user_id=None, reason=None):
    await _record(db, "withdraw", user_id=user_id, track_id=track_id,
                  scopes=scopes, source=source, ip=ip,
                  actor_user_id=actor_user_id, authorization_id=authorization_id,
                  acting_admin_user_id=acting_admin_user_id, reason=reason)


async def _record(db, action, *, user_id, track_id, scopes, source, ip, agreement=None,
                  actor_user_id=None, authorization_id=None, acting_admin_user_id=None,
                  reason=None):
    if not scopes:
        raise ValueError(f"consent {action} called with no scopes")
    if reason is not None and reason not in REASON_CODES:
        raise ValueError(f"unknown consent reason {reason!r}")
    now = datetime.now(timezone.utc).isoformat()
    extra = {}
    if agreement:
        extra["agreement_id"] = agreement["id"]
    # Delegated-action provenance. user_id stays the artist; these record who actually
    # performed the action and under what authorization. Written only when supplied, so
    # existing event shapes are unchanged and absence keeps its "artist, directly" meaning.
    for key, value in (("actor_user_id", actor_user_id),
                       ("authorization_id", authorization_id),
                       ("acting_admin_user_id", acting_admin_user_id),
                       ("reason", reason)):
        if value is not None:
            extra[key] = value
    await db.consent_events.insert_many([
        {
            "user_id": user_id,
            "track_id": track_id,
            "scope": scope,
            "action": action,
            "source": source,
            "grant_version": agreement["version"] if agreement else GRANT_VERSION,
            "ip": ip,
            "created_at": now,
            **extra,
        }
        for scope in scopes
    ])
