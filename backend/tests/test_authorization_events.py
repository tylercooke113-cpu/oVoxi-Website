"""Brief 28 B4: the authorization_events audit log is insert-only, validates the event
type, and records the co-owner email change with old and new email."""
import asyncio
from unittest.mock import AsyncMock

import pytest

import authorization_events as ae


def run(coro):
    return asyncio.run(coro)


def _db():
    db = AsyncMock()
    db.authorization_events.insert_one = AsyncMock()
    return db


def _doc(db):
    return db.authorization_events.insert_one.await_args.args[0]


def test_event_type_sets_are_disjoint_and_complete():
    assert ae.LIFECYCLE_EVENTS.isdisjoint(ae.ACTION_EVENTS)
    assert ae.EVENT_TYPES == ae.LIFECYCLE_EVENTS | ae.ACTION_EVENTS
    assert "coowner_email_changed" in ae.ACTION_EVENTS


@pytest.mark.parametrize("event", sorted(ae.EVENT_TYPES))
def test_every_known_event_inserts(event):
    db = _db()
    run(ae.record(db, event=event, authorization_id="auth1", artist_user_id="artist",
                  actor_user_id="uploader", track_id="t1"))
    d = _doc(db)
    assert d["event"] == event
    assert d["authorization_id"] == "auth1" and d["artist_user_id"] == "artist"
    assert d["actor_user_id"] == "uploader" and d["track_id"] == "t1"
    assert d["id"] and d["created_at"]


def test_unknown_event_rejected_and_nothing_written():
    db = _db()
    with pytest.raises(ValueError):
        run(ae.record(db, event="hacked", authorization_id="auth1", artist_user_id="artist"))
    db.authorization_events.insert_one.assert_not_awaited()


def test_coowner_email_changed_records_old_and_new():
    db = _db()
    run(ae.record_coowner_email_changed(
        db, authorization_id="auth1", artist_user_id="artist", actor_user_id="uploader",
        track_id="t1", old_email="old@example.com", new_email="new@example.com"))
    d = _doc(db)
    assert d["event"] == "coowner_email_changed"
    assert d["detail"] == {"old_email": "old@example.com", "new_email": "new@example.com"}
    assert d["actor_user_id"] == "uploader" and d["track_id"] == "t1"


def test_acting_admin_recorded_for_ovoxi_upload():
    db = _db()
    run(ae.record(db, event="upload", authorization_id="auth1", artist_user_id="artist",
                  actor_user_id="admin1", acting_admin_user_id="admin1", track_id="t1"))
    assert _doc(db)["acting_admin_user_id"] == "admin1"
