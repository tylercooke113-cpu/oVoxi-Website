"""Brief 25b Part D1: AI-training songs listed in the catalog, the samples and
AI-tools questions on every upload, the Vault answer flow, and the admin review."""
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import server
from clearance import clearance_fields
from sync_constants import AI_TOOLS_FULL_MESSAGE
from sync_public import AI_LISTING_FILTER, LISTING_FILTER, SYNC_LISTING_FILTER, available_for, is_listed, listed_for
from sync_vault import vault_track_view
from test_presign_consent import base, client as presign_client, fake_db, inserted_doc, post  # noqa: F401
from test_sync_orders import AsyncDB
from test_vault import FakeCollection, TID, client, db, track  # noqa: F401

STEMS = {n: "x" for n in ("vocals", "instrumental", "drums", "bass", "other")}
DECL = {"samples": "original", "samples_attested": True, "ai_tools": "none", "ai_tools_attested": True}


def ai_only_doc(**over):
    doc = {
        "id": "t-ai", "clerk_user_id": "user_artist", "track_name": "Ocean", "artist_name": "Kay",
        "genre": "R&B", "consent": {"ai_training": True, "sync": False},
        "metadata": {"moods": ["Chill"], "vocals": "vocal", "bpm": 90.0, "key": "C major", "duration_s": 180.0},
        "intake": {"samples": "original", "samples_attested_at": "t",
                   "ai_tools": "none", "ai_tools_attested_at": "t"},
        "rights": {"attested_at": "t", "writers": [{"share_bp": 10000}],
                   "publishers": [{"share_bp": 10000}], "master_owners": [{"share_bp": 10000}]},
        "fingerprint_result": "CLEARED", "stem_paths": dict(STEMS),
    }
    doc.update(over)
    return doc


def cleared(doc):
    return {**doc, **clearance_fields(doc, "2026-10-24T00:00:00+00:00")}


# --------------------------------------------------------------------------- listing

def test_cleared_ai_only_track_is_listed_for_ai_only():
    d = cleared(ai_only_doc())
    assert d["ai_status"] == "cleared" and d["on_sync_profile"] is True
    assert listed_for(d, "ai") and not listed_for(d, "sync")
    assert available_for(d) == ["ai"] and is_listed(d)


def test_listing_filters_in_mongo():
    db = AsyncDB()
    db._db.track_submissions.insert_one(cleared(ai_only_doc()))
    c = db._db.track_submissions
    assert c.count_documents(LISTING_FILTER) == 1
    assert c.count_documents(AI_LISTING_FILTER) == 1
    assert c.count_documents(SYNC_LISTING_FILTER) == 0


def test_ai_only_without_answers_is_needs_info_and_not_listed():
    d = cleared(ai_only_doc(intake={}))
    assert d["ai_status"] == "needs_docs" and d["on_sync_profile"] is False
    view = vault_track_view(d)
    assert view["needs_declarations"] is True
    assert set(view["ai_reasons"]) == {"samples", "ai_tools"}


def test_ai_sold_exclusively_comes_down():
    d = cleared(ai_only_doc(consent={"ai_training": True, "sync": False, "exclusive": True},
                            exclusive_sold={"ai": "L1"}))
    assert not listed_for(d, "ai") and not is_listed(d)


def test_vault_view_has_ai_status_and_no_sync_reasons_for_ai_only():
    v = vault_track_view(cleared(ai_only_doc()))
    assert v["ai_status"] == "cleared" and v["ai_reasons"] == []
    assert v["sync_status"] is None and v["sync_reasons"] == []
    assert v["on_sync_profile"] is True and v["needs_declarations"] is False


# --------------------------------------------------------------------------- sync sales need a sync listing

def test_checkout_refuses_ai_only_track_404(monkeypatch):
    import sync_orders as so
    db = AsyncDB()
    db._db.track_submissions.insert_one(cleared(ai_only_doc(id="t1")))
    monkeypatch.setattr(server, "db", db)
    monkeypatch.setattr(server.limiter, "enabled", False)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_abc")
    monkeypatch.setenv("SYNC_TOKEN_SECRET", "s" * 64)
    monkeypatch.setenv("SYNC_CHECKOUT_ENABLED", "true")
    server.app.dependency_overrides[server.optional_clerk] = lambda: {"sub": "a", "metadata": {"role": "admin"}}
    try:
        r = TestClient(server.app).post("/api/sync/checkout", json={
            "track_id": "t1", "tier": "digital", "include_stems": False, "buyer_name": "Dana",
            "buyer_company": "", "buyer_email": "dana@example.com", "project_name": "Teaser",
            "accept_terms": True, "terms_version": so.terms_version()})
        assert r.status_code == 404
    finally:
        server.app.dependency_overrides.clear()


# --------------------------------------------------------------------------- upload questions

def test_upload_requires_declarations(presign_client, fake_db):
    body = base()
    body.pop("declarations")
    r = post(presign_client, body)
    assert r.status_code == 422 and "Answer the samples and AI tools questions." in r.text


def test_upload_mostly_ai_refused(presign_client, fake_db):
    r = post(presign_client, base(declarations={**DECL, "ai_tools": "full"}))
    assert r.status_code == 422 and AI_TOOLS_FULL_MESSAGE in r.text
    fake_db.track_submissions.insert_one.assert_not_awaited()


def test_upload_partial_needs_detail(presign_client, fake_db):
    r = post(presign_client, base(declarations={**DECL, "ai_tools": "partial"}))
    assert r.status_code == 422 and "which parts used AI" in r.text


def test_upload_partial_stored_with_detail(presign_client, fake_db):
    r = post(presign_client, base(declarations={**DECL, "ai_tools": "partial",
                                                "ai_tools_detail": "  Backing vocals, Suno  "}))
    assert r.status_code == 200, r.text
    i = inserted_doc(fake_db)["intake"]
    assert i["ai_tools"] == "partial" and i["ai_tools_detail"] == "Backing vocals, Suno"
    assert i["samples"] == "original" and i["ai_tools_attested_at"]


def test_upload_detail_dropped_unless_partial(presign_client, fake_db):
    r = post(presign_client, base(declarations={**DECL, "ai_tools_detail": "ignored"}))
    assert r.status_code == 200, r.text
    assert inserted_doc(fake_db)["intake"]["ai_tools_detail"] is None


# --------------------------------------------------------------------------- Vault answer flow

def _declare(client, **over):
    return client.post(f"/api/vault/tracks/{TID}/declarations", json={**DECL, **over})


def test_vault_declarations_store_and_reclear(client, db):
    db.track_submissions.docs[0]["intake"] = {}
    r = _declare(client)
    assert r.status_code == 200, r.text
    d = db.track_submissions.docs[0]
    assert d["intake"]["samples"] == "original" and d["intake"]["ai_tools"] == "none"
    assert d["checks"]["ai_tools"]["result"] == "pass"            # clearance re-ran
    assert r.json()["needs_declarations"] is False


def test_vault_declarations_changed_partial_resets_review(client, db):
    d = db.track_submissions.docs[0]
    d["intake"] = {"samples": "original", "ai_tools": "partial", "ai_tools_detail": "Drums"}
    d["ai_tools_reviewed"] = {"result": "approved"}
    _declare(client, ai_tools="partial", ai_tools_detail="Drums and bass")
    assert db.track_submissions.docs[0]["ai_tools_reviewed"] is None


def test_vault_declarations_unchanged_keeps_review(client, db):
    d = db.track_submissions.docs[0]
    d["intake"] = {"samples": "original", "ai_tools": "partial", "ai_tools_detail": "Drums"}
    d["ai_tools_reviewed"] = {"result": "approved"}
    _declare(client, ai_tools="partial", ai_tools_detail="Drums")
    assert db.track_submissions.docs[0]["ai_tools_reviewed"] == {"result": "approved"}


def test_vault_declarations_full_refused(client, db):
    assert _declare(client, ai_tools="full").status_code == 422


def test_vault_declarations_legacy_409(client, db):
    db.track_submissions.docs[0].pop("consent")
    assert _declare(client).status_code == 409


def test_vault_add_sync_keeps_declarations(client, db, monkeypatch):
    db.track_submissions.docs[0]["intake"] = {"samples": "original", "samples_attested_at": "t",
                                              "ai_tools": "none", "ai_tools_attested_at": "t"}
    r = client.post(f"/api/vault/tracks/{TID}/consent", json={
        "scope": "sync", "action": "grant",
        "sync_intake": {"distributor": "DistroKid", "content_id": "no", "pro_name": "BMI", "ipi": "00123456789",
                        "sync_sole_attested": True}})
    assert r.status_code == 200, r.text
    i = db.track_submissions.docs[0]["intake"]
    assert i["ai_tools"] == "none" and i["samples"] == "original" and i["content_id"] == "no"


# --------------------------------------------------------------------------- admin review

def _review(client, result, **extra):
    return client.post(f"/api/admin/sync/tracks/{TID}/ai-tools-review", json={"result": result, **extra})


def test_admin_review_requires_partial(client, db):
    db.admin_actions = FakeCollection()
    db.track_submissions.docs[0]["intake"] = {"ai_tools": "none"}
    assert _review(client, "approved").status_code == 409


@pytest.mark.parametrize("result,check", [("approved", "pass"), ("rejected", "fail")])
def test_admin_review_sets_result_logs_and_reclears(client, db, result, check):
    db.admin_actions = FakeCollection()
    db.track_submissions.docs[0]["intake"] = {"samples": "original", "samples_attested_at": "t",
                                              "ai_tools": "partial", "ai_tools_detail": "Drums",
                                              "ai_tools_attested_at": "t"}
    r = _review(client, result, reason="checked stems")
    assert r.status_code == 200, r.text
    d = db.track_submissions.docs[0]
    assert d["ai_tools_reviewed"]["result"] == result and d["ai_tools_reviewed"]["by"] == "admin"
    assert d["checks"]["ai_tools"]["result"] == check
    assert db.admin_actions.inserted[0]["action"] == f"ai_tools_{result}"
