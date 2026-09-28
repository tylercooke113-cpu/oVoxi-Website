"""Append-only consent ledger. See docs/PRD-03 section 8.2.

This module only inserts. There is no update or delete function and none
should be added: every change of consent is a new event.
"""
import os
from datetime import datetime, timezone

GRANT_VERSION = os.environ.get("SYNC_GRANT_VERSION", "draft-0")


async def record_grants(db, *, user_id, track_id, scopes, source, ip):
    await _record(db, "grant", user_id=user_id, track_id=track_id,
                  scopes=scopes, source=source, ip=ip)


async def record_withdrawals(db, *, user_id, track_id, scopes, source, ip):
    await _record(db, "withdraw", user_id=user_id, track_id=track_id,
                  scopes=scopes, source=source, ip=ip)


async def _record(db, action, *, user_id, track_id, scopes, source, ip):
    if not scopes:
        raise ValueError(f"consent {action} called with no scopes")
    now = datetime.now(timezone.utc).isoformat()
    await db.consent_events.insert_many([
        {
            "user_id": user_id,
            "track_id": track_id,
            "scope": scope,
            "action": action,
            "source": source,
            "grant_version": GRANT_VERSION,
            "ip": ip,
            "created_at": now,
        }
        for scope in scopes
    ])
