"""Brief 28 B3: the consent ledger stays insert-only and gains optional delegated-action
provenance (actor_user_id, authorization_id, acting_admin_user_id, reason), with reason
restricted to a fixed list."""
import asyncio
from unittest.mock import AsyncMock

import pytest

import consent_ledger


def run(coro):
    return asyncio.run(coro)


def _db():
    db = AsyncMock()
    db.consent_events.insert_many = AsyncMock()
    return db


def _events(db):
    return db.consent_events.insert_many.await_args.args[0]


def test_plain_withdrawal_unchanged():
    db = _db()
    run(consent_ledger.record_withdrawals(db, user_id="artist", track_id="t1",
                                          scopes=["sync"], source="vault", ip="1.2.3.4"))
    ev = _events(db)
    assert len(ev) == 1 and ev[0]["user_id"] == "artist" and ev[0]["action"] == "withdraw"
    # No delegated keys written when none supplied.
    for k in ("actor_user_id", "authorization_id", "acting_admin_user_id", "reason"):
        assert k not in ev[0]


def test_delegated_fields_written_when_supplied():
    db = _db()
    run(consent_ledger.record_grants(
        db, user_id="artist", track_id="t1", scopes=["sync", "ai_training"], source="vault",
        ip="1.2.3.4", actor_user_id="uploader", authorization_id="auth1",
        acting_admin_user_id="admin1", reason="artist_withdrawal"))
    ev = _events(db)
    assert len(ev) == 2
    for e in ev:
        assert e["user_id"] == "artist"              # user_id stays the artist
        assert e["actor_user_id"] == "uploader"
        assert e["authorization_id"] == "auth1"
        assert e["acting_admin_user_id"] == "admin1"
        assert e["reason"] == "artist_withdrawal"


@pytest.mark.parametrize("reason", sorted(consent_ledger.REASON_CODES))
def test_every_valid_reason_accepted(reason):
    db = _db()
    run(consent_ledger.record_withdrawals(db, user_id="a", track_id="t", scopes=["sync"],
                                          source="admin", ip="1.1.1.1", reason=reason))
    assert _events(db)[0]["reason"] == reason


def test_unknown_reason_rejected_and_nothing_written():
    db = _db()
    with pytest.raises(ValueError):
        run(consent_ledger.record_withdrawals(db, user_id="a", track_id="t", scopes=["sync"],
                                              source="admin", ip="1.1.1.1", reason="because"))
    db.consent_events.insert_many.assert_not_awaited()


def test_reason_codes_are_the_fixed_list():
    assert consent_ledger.REASON_CODES == frozenset({
        "artist_withdrawal", "not_intended", "admin_takedown_artist_request",
        "admin_takedown_upload_error", "admin_takedown_rights"})
