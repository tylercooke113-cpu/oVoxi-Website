"""
PRD-03 Phase 3: fingerprint_result and duration persisted, callback analysis
fields, clearance evaluator. Mocked db, no network (conftest mocks motor,
modal and acrcloud_check).
"""
import asyncio
import copy
import hashlib
import hmac
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

import server
from clearance import evaluate

SID = "11111111-2222-3333-4444-555555555555"
ORIGINAL = f"catalog/artist/track/original/{SID}.wav"
STEMS = {n: f"catalog/artist/track/stems/{SID}/{n}.wav"
         for n in ("vocals", "instrumental", "drums", "bass", "other")}


def cleared_doc(**overrides):
    doc = {
        "id": SID,
        "genre": "R&B",
        "consent": {"ai_training": False, "sync": True},
        "metadata": {"moods": ["Chill"], "vocals": "vocal", "bpm": 92.0,
                     "key": "A minor", "duration_s": 180.5},
        "intake": {"samples": "original", "samples_attested_at": "t", "distributor": "DistroKid",
                   "content_id": "no", "pro_not_affiliated": False, "pro_name": "BMI",
                   "ipi": "00123456789"},
        "rights": {"owns_everything": True, "attested_at": "t",
                   "writers": [{"share_bp": 10000}], "publishers": [{"share_bp": 10000}],
                   "master_owners": [{"share_bp": 10000}]},
        "fingerprint_result": "CLEARED",
        "stem_paths": dict(STEMS),
    }
    doc.update(overrides)
    return doc


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Clearance evaluator (pure)
# ---------------------------------------------------------------------------

def test_all_checks_pass_is_cleared():
    r = evaluate(cleared_doc())
    assert r["sync_status"] == "cleared"
    assert all(c["result"] == "pass" for c in r["checks"].values())
    assert set(r["checks"]) == {"splits", "fingerprint", "samples", "content_id", "pro", "metadata"}


def test_ai_only_is_not_evaluated():
    assert evaluate(cleared_doc(consent={"ai_training": True, "sync": False})) is None
    assert evaluate({"id": SID}) is None


def test_conflict_wins_over_everything():
    r = evaluate(cleared_doc(fingerprint_result="CONFLICT", intake={}))
    assert r["sync_status"] == "conflict"
    assert r["checks"]["fingerprint"] == {"result": "fail", "reason": "conflict"}


@pytest.mark.parametrize("fp, reason", [
    ("NEEDS_DOCS", "fingerprint_needs_docs"), ("SCAN_ERROR", "fingerprint_scan_error"),
])
def test_fingerprint_failures_are_needs_docs(fp, reason):
    r = evaluate(cleared_doc(fingerprint_result=fp))
    assert r["sync_status"] == "needs_docs"
    assert r["checks"]["fingerprint"]["reason"] == reason


def test_unscanned_is_pending_and_needs_docs():
    doc = cleared_doc()
    del doc["fingerprint_result"]
    r = evaluate(doc)
    assert r["checks"]["fingerprint"]["result"] == "pending"
    assert r["sync_status"] == "needs_docs"


@pytest.mark.parametrize("answer", ["yes", "not_sure"])
def test_content_id_yes_or_not_sure_fails(answer):
    doc = cleared_doc()
    doc["intake"]["content_id"] = answer
    r = evaluate(doc)
    assert r["checks"]["content_id"] == {"result": "fail", "reason": "content_id"}
    assert r["sync_status"] == "needs_docs"


def test_pro_not_affiliated_passes():
    doc = cleared_doc()
    doc["intake"].update(pro_not_affiliated=True, pro_name=None, ipi=None)
    assert evaluate(doc)["checks"]["pro"]["result"] == "pass"


def test_pro_missing_ipi_fails():
    doc = cleared_doc()
    doc["intake"]["ipi"] = None
    assert evaluate(doc)["checks"]["pro"]["reason"] == "pro"


def test_samples_not_attested_fails():
    doc = cleared_doc()
    doc["intake"]["samples_attested_at"] = None
    assert evaluate(doc)["checks"]["samples"]["reason"] == "samples"


@pytest.mark.parametrize("rights, reason", [
    (None, "splits_missing"),
    ({"attested_at": "t", "writers": [{"share_bp": 9999}], "publishers": [{"share_bp": 10000}],
      "master_owners": [{"share_bp": 10000}]}, "splits_writers"),
    ({"attested_at": "t", "writers": [{"share_bp": 10000}], "publishers": [],
      "master_owners": [{"share_bp": 10000}]}, "splits_publishers"),
    ({"writers": [{"share_bp": 10000}], "publishers": [{"share_bp": 10000}],
      "master_owners": [{"share_bp": 10000}]}, "splits_not_attested"),
])
def test_splits_failures(rights, reason):
    assert evaluate(cleared_doc(rights=rights))["checks"]["splits"]["reason"] == reason


def test_metadata_lists_every_missing_item():
    doc = cleared_doc(stem_paths={"vocals": "x"})
    doc["metadata"] = {"moods": ["Chill"], "vocals": "vocal", "duration_s": 100}
    r = evaluate(doc)
    assert r["checks"]["metadata"]["reason"] == "missing: bpm, key, stems"
    assert r["sync_status"] == "needs_docs"


def test_metadata_too_many_moods_fails():
    doc = cleared_doc()
    doc["metadata"]["moods"] = ["A", "B", "C", "D"]
    assert "moods" in evaluate(doc)["checks"]["metadata"]["reason"]


def test_evaluate_does_not_mutate_input():
    doc = cleared_doc()
    before = copy.deepcopy(doc)
    evaluate(doc)
    assert doc == before


# ---------------------------------------------------------------------------
# _run_clearance (stores the result)
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_db(monkeypatch):
    db = MagicMock()
    db.track_submissions.find_one = AsyncMock()
    db.track_submissions.update_one = AsyncMock(return_value=SimpleNamespace(matched_count=1))
    monkeypatch.setattr(server, "db", db)
    return db


def stored_fields(fake_db):
    return fake_db.track_submissions.update_one.await_args.args[1]["$set"]


def test_run_clearance_cleared_lists_once(fake_db):
    fake_db.track_submissions.find_one.return_value = cleared_doc()
    run(server._run_clearance(SID))
    f = stored_fields(fake_db)
    assert f["sync_status"] == "cleared"
    assert f["on_sync_profile"] is True and f["sync_listed_at"]
    assert f["clearance_evaluated_at"]


def test_run_clearance_already_listed_keeps_listed_at(fake_db):
    fake_db.track_submissions.find_one.return_value = cleared_doc(on_sync_profile=True, sync_listed_at="old")
    run(server._run_clearance(SID))
    f = stored_fields(fake_db)
    assert "sync_listed_at" not in f and "on_sync_profile" not in f


def test_run_clearance_respects_admin_delist(fake_db):
    fake_db.track_submissions.find_one.return_value = cleared_doc(sync_delisted_by_admin=True)
    run(server._run_clearance(SID))
    assert "on_sync_profile" not in stored_fields(fake_db)


def test_run_clearance_needs_docs_does_not_list(fake_db):
    fake_db.track_submissions.find_one.return_value = cleared_doc(fingerprint_result="NEEDS_DOCS")
    run(server._run_clearance(SID))
    f = stored_fields(fake_db)
    assert f["sync_status"] == "needs_docs" and "on_sync_profile" not in f


def test_run_clearance_ai_only_writes_nothing(fake_db):
    fake_db.track_submissions.find_one.return_value = cleared_doc(consent={"ai_training": True, "sync": False})
    run(server._run_clearance(SID))
    fake_db.track_submissions.update_one.assert_not_awaited()


def test_run_clearance_never_raises(fake_db):
    fake_db.track_submissions.find_one.side_effect = RuntimeError("mongo down")
    run(server._run_clearance(SID))  # no exception


# ---------------------------------------------------------------------------
# Stems callback: phase 3 fields
# ---------------------------------------------------------------------------

SECRET = "test-webhook-secret"


@pytest.fixture
def cb(fake_db, monkeypatch):
    monkeypatch.setenv("STEM_WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(server.limiter, "enabled", False)
    fake_db.track_submissions.find_one.return_value = {"status": "processing", "original_r2_path": ORIGINAL}
    client = TestClient(server.app)

    def send(**fields):
        payload = {"submission_id": SID, "status": "completed", "stem_paths": dict(STEMS),
                   "stem_schema_version": 3, "stem_format": "wav24", "ts": int(time.time()), **fields}
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        sig = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
        return client.post("/api/internal/stems/callback", content=body,
                           headers={"Content-Type": "application/json", "X-Ovoxi-Signature": sig})
    return send


def completed_fields(fake_db):
    for call in fake_db.track_submissions.update_one.await_args_list:
        fields = call.args[1]["$set"]
        if fields.get("status") == "completed":
            return fields
    raise AssertionError("no completed write")


def test_callback_stores_analysis_fields(cb, fake_db):
    resp = cb(preview_key=f"catalog/artist/track/previews/{SID}.mp3",
              waveform_key=f"catalog/artist/track/previews/{SID}.waveform.json",
              bpm=92.04, key="A minor")
    assert resp.status_code == 200, resp.text
    f = completed_fields(fake_db)
    assert f["preview_key"].endswith(f"previews/{SID}.mp3")
    assert f["waveform_key"].endswith(f"previews/{SID}.waveform.json")
    assert f["metadata.bpm"] == 92.0 and f["metadata.bpm_source"] == "detected"
    assert f["metadata.key"] == "A minor" and f["metadata.key_source"] == "detected"


def test_callback_without_analysis_still_completes(cb, fake_db):
    assert cb().status_code == 200
    f = completed_fields(fake_db)
    assert not any(k in f for k in ("preview_key", "waveform_key", "metadata.bpm", "metadata.key"))


@pytest.mark.parametrize("fields, dropped", [
    ({"preview_key": "catalog/other/track/previews/x.mp3"}, "preview_key"),
    ({"waveform_key": f"catalog/artist/track/previews/{SID}.json"}, "waveform_key"),
    ({"bpm": 900}, "metadata.bpm"),
    ({"bpm": True}, "metadata.bpm"),
    ({"bpm": "120"}, "metadata.bpm"),
    ({"key": "H major"}, "metadata.key"),
])
def test_callback_drops_bad_optional_fields_but_completes(cb, fake_db, fields, dropped):
    resp = cb(**fields)
    assert resp.status_code == 200, resp.text
    f = completed_fields(fake_db)
    assert f["status"] == "completed"
    assert dropped not in f


def test_callback_runs_clearance(cb, fake_db, monkeypatch):
    spy = AsyncMock()
    monkeypatch.setattr(server, "_run_clearance", spy)
    cb()
    spy.assert_awaited_once_with(SID)


# ---------------------------------------------------------------------------
# _process_stems: fingerprint_result and duration persisted
# ---------------------------------------------------------------------------

@pytest.fixture
def pipeline(monkeypatch):
    calls = []

    async def fake_set_status(sid, status, extra=None, match=None):
        calls.append((status, dict(extra or {})))
        return 1

    monkeypatch.setattr(server, "_set_status", fake_set_status)
    monkeypatch.setattr(server, "_r2_download_to", AsyncMock())
    monkeypatch.setattr(server, "_run_clearance", AsyncMock())
    monkeypatch.setattr(server.subprocess, "run", lambda *a, **k: SimpleNamespace(
        returncode=0, stdout=json.dumps({"format": {"duration": "183.456"}})))
    monkeypatch.setattr(server, "_master_track", AsyncMock(side_effect=RuntimeError("stop here")))

    def go(acr_status):
        server.acrcloud_check.scan_file = MagicMock(return_value={"status": acr_status})
        run(server._process_stems(SID, ORIGINAL, "Artist", "Track"))
        return calls
    return go


@pytest.mark.parametrize("acr", ["NEEDS_DOCS", "CONFLICT", "SCAN_ERROR"])
def test_stopped_track_keeps_fingerprint_and_duration(pipeline, acr):
    calls = pipeline(acr)
    status, extra = calls[0]
    assert status == acr
    assert extra["fingerprint_result"] == acr
    assert extra["metadata.duration_s"] == 183.46
    server._run_clearance.assert_awaited_once_with(SID)


def test_cleared_track_keeps_fingerprint_and_duration(pipeline):
    calls = pipeline("CLEARED")
    status, extra = calls[0]
    assert status == "mastering"
    assert extra == {"fingerprint_result": "CLEARED", "metadata.duration_s": 183.46}
    server._run_clearance.assert_not_awaited()
