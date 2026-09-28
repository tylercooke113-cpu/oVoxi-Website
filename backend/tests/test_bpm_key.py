"""
PRD-03 4.4, decisions 11 and 12: artist-supplied BPM and key at upload,
reconciled with detection after processing.
"""
import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

import server
from clearance import evaluate
from metadata_reconcile import bpm_agrees, key_agrees, reconcile
from test_presign_consent import (  # noqa: F401  (pytest fixtures)
    assert_rejected, base, client, fake_db, inserted_doc, post,
)
from test_phase3 import ORIGINAL, SID, STEMS, SECRET, cleared_doc, completed_fields


# ---------------------------------------------------------------------------
# Upload request
# ---------------------------------------------------------------------------

def test_artist_values_stored(client, fake_db):
    resp = post(client, base(bpm=130, key="D minor"))
    assert resp.status_code == 200, resp.text
    m = inserted_doc(fake_db)["metadata"]
    assert m["bpm"] == 130.0 and m["bpm_source"] == "artist" and m["bpm_unsure"] is False
    assert m["key"] == "D minor" and m["key_source"] == "artist" and m["key_unsure"] is False


def test_unsure_stored(client, fake_db):
    body = base(bpm_unsure=True, key_unsure=True)
    del body["bpm"], body["key"]
    resp = post(client, body)
    assert resp.status_code == 200, resp.text
    m = inserted_doc(fake_db)["metadata"]
    assert m["bpm"] is None and m["bpm_source"] is None and m["bpm_unsure"] is True
    assert m["key"] is None and m["key_source"] is None and m["key_unsure"] is True


def test_bpm_rounded_to_tenth(client, fake_db):
    post(client, base(bpm=93.47))
    assert inserted_doc(fake_db)["metadata"]["bpm"] == 93.5


@pytest.mark.parametrize("field", ["bpm", "key"])
def test_missing_answer_rejected(client, fake_db, field):
    body = base()
    del body[field]
    resp = post(client, body)
    assert_rejected(resp, fake_db)
    assert f"Enter the {field.upper() if field == 'bpm' else field}" in resp.text


@pytest.mark.parametrize("field", ["bpm", "key"])
def test_value_and_unsure_rejected(client, fake_db, field):
    resp = post(client, base(**{f"{field}_unsure": True}))
    assert_rejected(resp, fake_db)
    assert "not both" in resp.text


@pytest.mark.parametrize("bpm", [10, 400, 0])
def test_bpm_out_of_range_rejected(client, fake_db, bpm):
    assert_rejected(post(client, base(bpm=bpm)), fake_db)


@pytest.mark.parametrize("key", ["H major", "D Minor", "Dm", ""])
def test_bad_key_rejected(client, fake_db, key):
    assert_rejected(post(client, base(key=key)), fake_db)


# ---------------------------------------------------------------------------
# Agreement rules
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("artist, detected, ok", [
    (130, 130, True), (130, 129.0, True), (130, 131.9, True),
    (130, 65, True), (65, 130, True), (130, 260, True),
    (130, 127, False), (103, 130, False), (90, 120, False),
])
def test_bpm_agreement(artist, detected, ok):
    assert bpm_agrees(artist, detected) is ok


@pytest.mark.parametrize("artist, detected, ok", [
    ("D minor", "D minor", True),
    ("D minor", "D major", True),     # same root, opposite mode
    ("D minor", "F major", True),     # relative
    ("F major", "D minor", True),
    ("C major", "A minor", True),
    ("A minor", "C major", True),
    ("F# minor", "A major", True),
    ("C major", "E minor", False),
    ("C major", "F# minor", False),
    ("C major", "G major", False),
    ("D minor", "A minor", False),
])
def test_key_agreement(artist, detected, ok):
    assert key_agrees(artist, detected) is ok


# ---------------------------------------------------------------------------
# reconcile(): the table in PRD-03 4.4
# ---------------------------------------------------------------------------

def artist(bpm=None, key=None):
    return {"bpm": bpm, "bpm_source": "artist" if bpm is not None else None, "bpm_unsure": bpm is None,
            "key": key, "key_source": "artist" if key is not None else None, "key_unsure": key is None}


def test_half_tempo_and_parallel_key_artist_wins():
    out = reconcile(artist(130.0, "D minor"), 65.0, "D major")
    assert out["metadata.bpm"] == 130.0 and out["metadata.bpm_needs_confirmation"] is False
    assert out["metadata.key"] == "D minor" and out["metadata.key_needs_confirmation"] is False
    assert out["metadata.bpm_detected"] == 65.0 and out["metadata.key_detected"] == "D major"


def test_other_disagreement_held_with_artist_value():
    out = reconcile(artist(103.0, "C major"), 130.0, "F# minor")
    assert out["metadata.bpm"] == 103.0 and out["metadata.bpm_source"] == "artist"
    assert out["metadata.bpm_needs_confirmation"] is True
    assert out["metadata.key"] == "C major" and out["metadata.key_needs_confirmation"] is True


def test_unsure_uses_detected_and_holds():
    out = reconcile(artist(), 129.0, "A minor")
    assert out["metadata.bpm"] == 129.0 and out["metadata.bpm_source"] == "detected"
    assert out["metadata.bpm_needs_confirmation"] is True
    assert out["metadata.key"] == "A minor" and out["metadata.key_needs_confirmation"] is True


def test_detection_failed_artist_value_confirmed():
    out = reconcile(artist(130.0, "D minor"), None, None)
    assert out["metadata.bpm"] == 130.0 and out["metadata.bpm_needs_confirmation"] is False
    assert out["metadata.key"] == "D minor" and out["metadata.key_needs_confirmation"] is False


def test_unsure_and_detection_failed_stays_empty():
    out = reconcile(artist(), None, None)
    assert out["metadata.bpm"] is None and out["metadata.key"] is None


def test_mixed_one_unsure_one_value():
    out = reconcile(artist(bpm=90.0), 90.0, "E minor")
    assert out["metadata.bpm_needs_confirmation"] is False
    assert out["metadata.key"] == "E minor" and out["metadata.key_needs_confirmation"] is True


def test_legacy_track_without_artist_answer_uses_detection():
    out = reconcile({"moods": ["Chill"], "vocals": "vocal"}, 92.0, "A minor")
    assert out["metadata.bpm"] == 92.0 and out["metadata.bpm_source"] == "detected"
    assert "metadata.bpm_needs_confirmation" not in out


# ---------------------------------------------------------------------------
# Callback applies reconciliation in the completed write
# ---------------------------------------------------------------------------

@pytest.fixture
def cb_artist(fake_db, monkeypatch):
    from unittest.mock import AsyncMock
    from types import SimpleNamespace
    monkeypatch.setenv("STEM_WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(server.limiter, "enabled", False)
    monkeypatch.setattr(server, "_run_clearance", AsyncMock())
    fake_db.track_submissions.update_one = AsyncMock(return_value=SimpleNamespace(matched_count=1))
    tc = TestClient(server.app)

    def send(stored_metadata, **fields):
        fake_db.track_submissions.find_one = AsyncMock(return_value={
            "status": "processing", "original_r2_path": ORIGINAL, "metadata": stored_metadata})
        payload = {"submission_id": SID, "status": "completed", "stem_paths": dict(STEMS),
                   "ts": int(time.time()), **fields}
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        sig = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
        r = tc.post("/api/internal/stems/callback", content=body,
                    headers={"Content-Type": "application/json", "X-Ovoxi-Signature": sig})
        assert r.status_code == 200, r.text
        return completed_fields(fake_db)
    return send


def test_callback_artist_wins_on_known_confusions(cb_artist):
    f = cb_artist(artist(130.0, "D minor"), bpm=65.0, key="D major", key_confidence=0.08)
    assert f["metadata.bpm"] == 130.0 and f["metadata.key"] == "D minor"
    assert f["metadata.bpm_needs_confirmation"] is False and f["metadata.key_needs_confirmation"] is False
    assert f["metadata.bpm_detected"] == 65.0 and f["metadata.key_detected"] == "D major"
    assert f["metadata.key_detected_confidence"] == 0.08


def test_callback_holds_real_disagreement(cb_artist):
    f = cb_artist(artist(103.0, "C major"), bpm=130.0, key="F# minor")
    assert f["metadata.bpm"] == 103.0 and f["metadata.bpm_needs_confirmation"] is True
    assert f["metadata.key_needs_confirmation"] is True


@pytest.mark.parametrize("conf", [1.5, -0.1, "high", True])
def test_callback_drops_bad_confidence(cb_artist, conf):
    f = cb_artist(artist(130.0, "D minor"), key="D minor", key_confidence=conf)
    assert "metadata.key_detected_confidence" not in f


# ---------------------------------------------------------------------------
# Clearance check 6
# ---------------------------------------------------------------------------

def test_held_value_fails_check_6():
    doc = cleared_doc()
    doc["metadata"]["key_needs_confirmation"] = True
    r = evaluate(doc)
    assert r["checks"]["metadata"]["reason"] == "confirm: key"
    assert r["sync_status"] == "needs_docs"


def test_missing_and_held_reported_together():
    doc = cleared_doc(stem_paths={})
    doc["metadata"]["bpm_needs_confirmation"] = True
    assert evaluate(doc)["checks"]["metadata"]["reason"] == "missing: stems; confirm: bpm"


def test_confirmed_values_pass():
    doc = cleared_doc()
    doc["metadata"].update(bpm_needs_confirmation=False, key_needs_confirmation=False)
    assert evaluate(doc)["sync_status"] == "cleared"
