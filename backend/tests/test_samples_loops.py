"""Brief 25b (Agreement 3.6): no samples of other recordings; royalty-free loops for sync
only, with each creator in the splits, a license on file and Tyler's approval; and
full-song fingerprint scanning."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import importlib.util
from pathlib import Path

# conftest replaces acrcloud_check with a mock for the pipeline tests; load the real file.
_spec = importlib.util.spec_from_file_location(
    "acrcloud_check_real", Path(__file__).parent.parent / "acrcloud_check.py")
acrcloud_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(acrcloud_check)
import server
from clearance import check_samples, evaluate
from sync_constants import LOOPS_NO_AI_MESSAGE, SAMPLES_NOT_ALLOWED_MESSAGE
from sync_vault import vault_track_view
from test_presign_consent import base, client, fake_db, inserted_doc, intake, post  # noqa: F401
from test_rights import manual
from test_sync_orders import AsyncDB

LOOP = {"creator_name": "Jordan Producer", "creator_email": "jordan@example.com",
        "source": "Splice", "loop_name": "Dusty Keys 92bpm"}
LOOP_DECL = {"samples": "royalty_free_loop", "samples_attested": True, "loops": [LOOP],
             "ai_tools": "none", "ai_tools_attested": True}


def loop_doc(**over):
    doc = {"id": "t1", "clerk_user_id": "u1", "consent": {"sync": True, "ai_training": False},
           "intake": {"samples": "royalty_free_loop", "samples_attested_at": "t",
                      "loops": [{**LOOP, "license_key": "loop-licenses/t1/0-a.pdf"}]},
           "rights": {"writers": [{"legal_name": "Jordan Producer", "email": "jordan@example.com",
                                   "share_bp": 5000}]}}
    doc.update(over)
    return doc


# --------------------------------------------------------------------------- clearance rules

def test_original_passes_both_uses():
    d = {"intake": {"samples": "original", "samples_attested_at": "t"}}
    assert check_samples(d, "sync")["result"] == "pass" and check_samples(d, "ai")["result"] == "pass"


def test_cleared_sample_never_passes():
    d = {"intake": {"samples": "cleared_sample", "samples_attested_at": "t"}}
    assert check_samples(d, "sync")["reason"] == "samples_not_allowed"
    assert check_samples(d, "ai")["reason"] == "samples_not_allowed"


def test_loop_never_passes_for_ai():
    assert check_samples(loop_doc(loop_licenses_reviewed={"result": "approved"}), "ai")["reason"] == "samples_loop_ai"


@pytest.mark.parametrize("change,result,reason", [
    ({"intake": {"samples": "royalty_free_loop", "samples_attested_at": "t", "loops": []}}, "fail", "loops_missing"),
    ({"rights": {"writers": [{"legal_name": "Someone", "email": "x@example.com"}]}}, "fail", "loop_creator_not_listed"),
    ({"intake": {"samples": "royalty_free_loop", "samples_attested_at": "t", "loops": [dict(LOOP)]}},
     "fail", "loop_license_missing"),
    ({}, "pending", "loop_license_review"),
    ({"loop_licenses_reviewed": {"result": "rejected"}}, "fail", "loop_license_rejected"),
    ({"loop_licenses_reviewed": {"result": "approved"}}, "pass", None),
])
def test_loop_sync_rules(change, result, reason):
    assert check_samples(loop_doc(**change), "sync") == {"result": result, "reason": reason}


def test_evaluate_uses_per_use_samples_check():
    r = evaluate(loop_doc(consent={"sync": True, "ai_training": True},
                          loop_licenses_reviewed={"result": "approved"}))
    assert r["checks"]["samples"]["result"] == "pass"
    assert r["checks"]["samples_ai"]["reason"] == "samples_loop_ai"
    assert r["ai_status"] == "needs_docs"


def test_vault_view_shows_loops_without_license_keys():
    v = vault_track_view(loop_doc())
    assert v["loops"] == [{"creator_name": "Jordan Producer", "loop_name": "Dusty Keys 92bpm",
                           "source": "Splice", "has_license": True}]
    assert v["loop_license_status"] == "pending"
    assert "loop-licenses" not in str(v)


# --------------------------------------------------------------------------- upload rules

def test_upload_sample_refused(client, fake_db):
    r = post(client, base(declarations={**LOOP_DECL, "samples": "cleared_sample", "loops": []}))
    assert r.status_code == 422 and SAMPLES_NOT_ALLOWED_MESSAGE in r.text


def test_upload_loop_with_ai_training_refused(client, fake_db):
    r = post(client, base(declarations=LOOP_DECL, rights=manual()))
    assert r.status_code == 422 and "can't be offered for AI training" in r.text


def test_upload_loop_needs_loop_list(client, fake_db):
    r = post(client, base(consent_ai_training=False, consent_sync=True, sync_intake=intake(),
                          declarations={**LOOP_DECL, "loops": []}, rights=manual()))
    assert r.status_code == 422 and "List each loop" in r.text


def test_upload_loop_creator_must_be_in_splits(client, fake_db):
    stranger = {**LOOP, "creator_name": "Stranger", "creator_email": "stranger@example.com"}
    r = post(client, base(consent_ai_training=False, consent_sync=True, sync_intake=intake(),
                          declarations={**LOOP_DECL, "loops": [stranger]}, rights=manual()))
    assert r.status_code == 422 and "Add each loop creator to the splits" in r.text and "Stranger" in r.text
    fake_db.track_submissions.insert_one.assert_not_awaited()


def test_upload_loop_for_sync_stored(client, fake_db):
    r = post(client, base(consent_ai_training=False, consent_sync=True, sync_intake=intake(),
                          declarations=LOOP_DECL, rights=manual()))
    assert r.status_code == 200, r.text
    doc = inserted_doc(fake_db)
    assert doc["intake"]["samples"] == "royalty_free_loop"
    assert doc["intake"]["loops"][0]["creator_email"] == "jordan@example.com"
    assert doc["intake"]["loops"][0]["license_key"] is None
    assert doc["cosign_required"] is True          # the loop creator gets the Co-owner Consent


def test_loops_only_listed_with_loop_answer(client, fake_db):
    r = post(client, base(declarations={**LOOP_DECL, "samples": "original"}))
    assert r.status_code == 422 and "Only list loops" in r.text


# --------------------------------------------------------------------------- Vault, license upload, admin review

@pytest.fixture
def env(monkeypatch):
    db = AsyncDB()
    db._db.track_submissions.insert_one(loop_doc(intake={
        "samples": "royalty_free_loop", "samples_attested_at": "t", "loops": [dict(LOOP)]}))
    r2 = MagicMock()
    r2.generate_presigned_url.return_value = "https://r2.test/signed"
    r2.head_object.return_value = {"ContentLength": 2048}
    monkeypatch.setattr(server, "db", db)
    monkeypatch.setattr(server, "r2_client", r2)
    monkeypatch.setattr(server.limiter, "enabled", False)
    artist = {"sub": "u1", "metadata": {"role": "artist"}}
    server.app.dependency_overrides[server.require_artist] = lambda: artist
    server.app.dependency_overrides[server.verify_clerk_token] = lambda: artist
    server.app.dependency_overrides[server.require_admin] = lambda: {"sub": "admin", "metadata": {"role": "admin"}}
    yield SimpleNamespace(client=TestClient(server.app), db=db, r2=r2)
    server.app.dependency_overrides.clear()


def doc(env):
    return env.db._db.track_submissions.find_one({"id": "t1"}, {"_id": 0})


def upload_license(env, index=0, **body):
    b = {"filename": "license.pdf", "content_type": "application/pdf", "file_size": 2048, **body}
    r = env.client.post(f"/api/vault/tracks/t1/loops/{index}/license/presign", json=b)
    if r.status_code != 200:
        return r
    return env.client.post(f"/api/vault/tracks/t1/loops/{index}/license/complete")


def test_license_upload_stores_key_and_resets_review(env):
    env.db._db.track_submissions.update_one({"id": "t1"}, {"$set": {"loop_licenses_reviewed": {"result": "approved"}}})
    r = upload_license(env)
    assert r.status_code == 200, r.text
    d = doc(env)
    assert d["intake"]["loops"][0]["license_key"].startswith("loop-licenses/t1/0-")
    assert d["loop_licenses_reviewed"] is None
    assert d["checks"]["samples"]["reason"] == "loop_license_review"
    assert r.json()["loops"][0]["has_license"] is True


@pytest.mark.parametrize("body,msg", [({"content_type": "text/plain"}, "PDF, PNG or JPG"),
                                      ({"file_size": 11 * 1024 * 1024}, "10 MB")])
def test_license_upload_refusals(env, body, msg):
    r = upload_license(env, **body)
    assert r.status_code == 422 and msg in r.text


def test_license_upload_unknown_loop_404(env):
    assert upload_license(env, index=3).status_code == 404


def test_complete_without_presign_409(env):
    assert env.client.post("/api/vault/tracks/t1/loops/0/license/complete").status_code == 409


def test_admin_cannot_approve_without_license(env):
    r = env.client.post("/api/admin/sync/tracks/t1/loop-licenses-review", json={"result": "approved"})
    assert r.status_code == 409 and "license file" in r.text


def test_admin_approve_clears_samples_check_and_logs(env):
    upload_license(env)
    r = env.client.post("/api/admin/sync/tracks/t1/loop-licenses-review",
                        json={"result": "approved", "reason": "Splice license checked"})
    assert r.status_code == 200, r.text
    d = doc(env)
    assert d["loop_licenses_reviewed"]["result"] == "approved"
    assert d["checks"]["samples"]["result"] == "pass"
    assert env.db._db.admin_actions.find_one({}, {"_id": 0})["action"] == "loop_licenses_approved"


def test_admin_license_link(env):
    upload_license(env)
    r = env.client.get("/api/admin/sync/tracks/t1/loops/0/license")
    assert r.status_code == 200 and r.json()["url"] == "https://r2.test/signed"
    assert r.json()["creator_email"] == "jordan@example.com"


def test_vault_ai_training_refused_for_loop_song(env):
    r = env.client.post("/api/vault/tracks/t1/consent", json={"scope": "ai_training", "action": "grant"})
    assert r.status_code == 409 and r.json()["detail"] == LOOPS_NO_AI_MESSAGE


# --------------------------------------------------------------------------- full-song scanning

def test_scan_offsets_cover_the_song(monkeypatch):
    for k in ("ACR_SCAN_STEP_SECONDS", "ACR_SCAN_MAX_WINDOWS"):
        monkeypatch.delenv(k, raising=False)
    assert acrcloud_check.scan_offsets(None) == [0]
    assert acrcloud_check.scan_offsets(12) == [0]
    assert acrcloud_check.scan_offsets(180) == [0, 30, 60, 90, 120, 150]
    monkeypatch.setenv("ACR_SCAN_MAX_WINDOWS", "2")
    assert acrcloud_check.scan_offsets(900) == [0, 30]


@pytest.fixture(autouse=True)
def _no_pause(monkeypatch):
    monkeypatch.setenv("ACR_SCAN_PAUSE_SECONDS", "0")


def test_scan_file_pauses_between_windows(monkeypatch):
    monkeypatch.setenv("ACR_SCAN_PAUSE_SECONDS", "0.6")
    sleeps = []
    monkeypatch.setattr(acrcloud_check.time, "sleep", sleeps.append)
    monkeypatch.setattr(acrcloud_check, "scan_window", lambda p, o: acrcloud_check._result("CLEARED"))
    acrcloud_check.scan_file("x.wav", 100)
    assert sleeps == [0.6, 0.6, 0.6]                 # 4 windows, a pause before each after the first


def test_scan_file_returns_most_serious_window(monkeypatch):
    results = {0: "CLEARED", 30: "NEEDS_DOCS", 60: "SCAN_ERROR", 90: "CLEARED"}
    calls = []

    def fake(path, offset):
        calls.append(offset)
        return {**acrcloud_check._result(results[offset]), "confidence": 80 if results[offset] == "NEEDS_DOCS" else None}

    monkeypatch.setattr(acrcloud_check, "scan_window", fake)
    r = acrcloud_check.scan_file("x.wav", 100)
    assert r["status"] == "NEEDS_DOCS" and r["matched_offset_s"] == 30
    assert calls == [0, 30, 60, 90]


def test_scan_file_stops_at_conflict(monkeypatch):
    calls = []

    def fake(path, offset):
        calls.append(offset)
        return acrcloud_check._result("CONFLICT" if offset == 30 else "CLEARED")

    monkeypatch.setattr(acrcloud_check, "scan_window", fake)
    r = acrcloud_check.scan_file("x.wav", 300)
    assert r["status"] == "CONFLICT" and r["matched_offset_s"] == 30 and calls == [0, 30]
