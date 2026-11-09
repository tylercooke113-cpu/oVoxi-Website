"""Append-only authorization audit log (Brief 28 B4).

Insert-only, like consent_ledger: every Upload Authorization lifecycle change and every
delegated action is a new event. There is no update or delete function and none should be
added. `artist_user_id` is always the artist; `actor_user_id` is whoever performed the
action; `acting_admin_user_id` is set only for OVOXI uploads (which admin acted).
"""
import uuid
from datetime import datetime, timezone

# The authorization itself moving through its lifecycle.
LIFECYCLE_EVENTS = frozenset({
    "created",         # artist created it (person: awaiting_uploader; ovoxi: active)
    "artist_signed",
    "uploader_signed",
    "declined",
    "revoked",         # artist revoked
    "ended",           # uploader ended
    "expired",
})

# Delegated actions taken under an active authorization. Each logs actor, authorization
# and track.
ACTION_EVENTS = frozenset({
    "upload",
    "metadata",
    "splits",
    "declarations",
    "use_added",
    "coowner_email_changed",
})

EVENT_TYPES = LIFECYCLE_EVENTS | ACTION_EVENTS


async def record(db, *, event, authorization_id, artist_user_id, actor_user_id=None,
                 acting_admin_user_id=None, track_id=None, detail=None):
    if event not in EVENT_TYPES:
        raise ValueError(f"unknown authorization event {event!r}")
    doc = {
        "id": str(uuid.uuid4()),
        "event": event,
        "authorization_id": authorization_id,
        "artist_user_id": artist_user_id,
        "actor_user_id": actor_user_id,
        "acting_admin_user_id": acting_admin_user_id,
        "track_id": track_id,
        "detail": detail or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.authorization_events.insert_one(doc)
    return doc


async def record_coowner_email_changed(db, *, authorization_id, artist_user_id, actor_user_id,
                                       track_id, old_email, new_email, acting_admin_user_id=None):
    """A co-owner email change made by an uploader (Part 0 rows 9 and 10). Records the old
    and new email so the change is auditable."""
    return await record(db, event="coowner_email_changed", authorization_id=authorization_id,
                        artist_user_id=artist_user_id, actor_user_id=actor_user_id,
                        acting_admin_user_id=acting_admin_user_id, track_id=track_id,
                        detail={"old_email": old_email, "new_email": new_email})
