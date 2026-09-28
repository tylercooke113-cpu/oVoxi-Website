"""
PRD-03 Phase 2: rights (splits) on every upload, PRD-02 model.

Model rules are tested directly on TrackRightsIn / build_rights. The presign
wiring reuses the mocked-db TestClient fixtures from test_presign_consent.
"""
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from rights import TrackRightsIn, build_rights
from test_presign_consent import (  # noqa: F401  (pytest fixtures)
    assert_rejected, base, client, fake_db, inserted_doc, intake, post,
)

AFFILIATED = SimpleNamespace(pro_not_affiliated=False, pro_name="BMI", ipi="00123456789")
NOT_AFFILIATED = SimpleNamespace(pro_not_affiliated=True, pro_name=None, ipi=None)


def party(name, bp, **kw):
    return {"legal_name": name, "share_bp": bp, **kw}


def manual(**overrides):
    body = {
        "owns_everything": False,
        "self_legal_name": "Tyler Example",
        "writers": [party("Tyler Example", 3334, role="CA"), party("Jordan Producer", 3333),
                    party("Sam Writer", 3333)],
        "publishers": [party("Tyler Example", 5000), party("Beat Co Publishing LLC", 5000)],
        "master_owners": [party("Tyler Example", 10000)],
        "attested": True,
    }
    body.update(overrides)
    return body


def rejects(body, match):
    with pytest.raises(ValidationError, match=match):
        TrackRightsIn(**body)


# ---------------------------------------------------------------------------
# Model rules (PRD-02 section 4, section 9 acceptance criteria)
# ---------------------------------------------------------------------------

def test_thirds_and_halves_round_trip_exactly():
    doc = build_rights(TrackRightsIn(**manual()), intake=AFFILIATED,
                       clerk_user_id="u1", now_iso="2026-09-28T00:00:00+00:00")
    assert [p["share_bp"] for p in doc["writers"]] == [3334, 3333, 3333]
    assert [p["share_bp"] for p in doc["publishers"]] == [5000, 5000]
    assert all(isinstance(p["share_bp"], int) for side in ("writers", "publishers", "master_owners")
               for p in doc[side])


@pytest.mark.parametrize("shares, message", [
    ([4999, 5000], r"Writers add up to 99\.99%, 0\.01% short\."),
    ([5001, 5000], r"Writers add up to 100\.01%, 0\.01% over\."),
])
def test_side_off_by_one_basis_point_names_side_and_delta(shares, message):
    rejects(manual(writers=[party("Tyler Example", shares[0]), party("Jordan", shares[1])]), message)


def test_publishers_short_named():
    rejects(manual(publishers=[party("Tyler Example", 7500)]), r"Publishers add up to 75%, 25% short\.")


def test_fifth_party_rejected():
    rejects(manual(master_owners=[party(f"P{i}", 2000) for i in range(5)]),
            r"Master owners need 1 to 4 parties\.")


def test_empty_side_rejected_when_not_owning_everything():
    rejects(manual(publishers=[]), r"Publishers need 1 to 4 parties\.")


def test_zero_share_rejected():
    rejects(manual(master_owners=[party("A", 10000), party("B", 0)]), "greater than or equal to 1")


def test_blank_name_rejected():
    rejects(manual(master_owners=[party("   ", 10000)]), "Every party needs a legal name")


def test_duplicate_name_rejected_case_insensitive():
    rejects(manual(master_owners=[party("Tyler", 5000), party("tyler", 5000)]),
            r"Master owners list the same name twice\.")


@pytest.mark.parametrize("side, role", [
    ("writers", "E"), ("publishers", "CA"), ("master_owners", "CA"),
])
def test_role_must_fit_side(side, role):
    body = manual()
    body[side] = [party("Tyler Example", 10000, role=role)]
    rejects(body, "Invalid role")


@pytest.mark.parametrize("ipi", ["12345678", "1234567890", "12345abc901"])
def test_party_ipi_must_be_9_or_11_digits(ipi):
    rejects(manual(master_owners=[party("Tyler Example", 10000, ipi_name_number=ipi)]),
            r"IPI must be 9 or 11 digits\.")


def test_unknown_society_rejected():
    rejects(manual(master_owners=[party("Tyler Example", 10000, society="Spotify")]), "Invalid PRO")


def test_not_attested_rejected():
    rejects(manual(attested=False), "Confirm the splits")


def test_missing_legal_name_rejected():
    rejects(manual(self_legal_name="  "), "Enter your legal name")


def test_unknown_field_rejected():
    rejects(manual(iswc="T-123.456.789-0"), "Extra inputs are not permitted")


def test_shortcut_with_rows_rejected():
    rejects(manual(owns_everything=True), r"Leave the splits empty when you own 100%\.")


def test_shortcut_expands_to_three_full_lists():
    body = {"owns_everything": True, "self_legal_name": "Tyler Example", "attested": True}
    doc = build_rights(TrackRightsIn(**body), intake=AFFILIATED, clerk_user_id="u1", now_iso="t")
    for side in ("writers", "publishers", "master_owners"):
        assert len(doc[side]) == 1
        row = doc[side][0]
        assert row["legal_name"] == "Tyler Example"
        assert row["share_bp"] == 10000
        assert row["is_self"] is True
    assert doc["writers"][0]["role"] == "CA"
    assert doc["publishers"][0]["role"] == "E"
    assert doc["master_owners"][0]["role"] is None


def test_shortcut_puts_pro_and_ipi_on_writer_row_only():
    body = {"owns_everything": True, "self_legal_name": "Tyler Example", "attested": True}
    doc = build_rights(TrackRightsIn(**body), intake=AFFILIATED, clerk_user_id="u1", now_iso="t")
    assert doc["writers"][0]["ipi_name_number"] == "00123456789"
    assert doc["writers"][0]["society"] == "BMI"
    assert doc["publishers"][0]["ipi_name_number"] is None
    assert doc["master_owners"][0]["society"] is None


def test_shortcut_not_affiliated_leaves_pro_empty():
    body = {"owns_everything": True, "self_legal_name": "Tyler Example", "attested": True}
    doc = build_rights(TrackRightsIn(**body), intake=NOT_AFFILIATED, clerk_user_id="u1", now_iso="t")
    assert doc["writers"][0]["ipi_name_number"] is None
    assert doc["writers"][0]["society"] is None


def test_is_self_derived_by_server():
    doc = build_rights(TrackRightsIn(**manual()), intake=AFFILIATED, clerk_user_id="u1", now_iso="t")
    assert [p["is_self"] for p in doc["writers"]] == [True, False, False]
    assert [p["is_self"] for p in doc["publishers"]] == [True, False]


def test_is_self_cannot_be_sent_by_client():
    rejects(manual(master_owners=[party("Tyler Example", 10000, is_self=True)]),
            "Extra inputs are not permitted")


def test_attestation_stamped_by_server():
    doc = build_rights(TrackRightsIn(**manual()), intake=AFFILIATED,
                       clerk_user_id="user_abc", now_iso="2026-09-28T12:00:00+00:00")
    assert doc["attested_at"] == "2026-09-28T12:00:00+00:00"
    assert doc["attested_by_clerk_user_id"] == "user_abc"
    assert "attested" not in doc
    assert "self_legal_name" not in doc


# ---------------------------------------------------------------------------
# Presign wiring
# ---------------------------------------------------------------------------

def sync_upload(**overrides):
    body = base(consent_ai_training=False, consent_sync=True, sync_intake=intake(), rights=manual())
    body.update(overrides)
    return body


def test_presign_stores_manual_rights(client, fake_db):
    resp = post(client, sync_upload())
    assert resp.status_code == 200, resp.text
    doc = inserted_doc(fake_db)
    assert [p["share_bp"] for p in doc["rights"]["writers"]] == [3334, 3333, 3333]
    assert doc["rights"]["attested_by_clerk_user_id"] == "user_test"
    assert doc["rights"]["attested_at"]


def test_presign_stores_expanded_shortcut(client, fake_db):
    body = sync_upload(rights={"owns_everything": True, "self_legal_name": "Test Person", "attested": True})
    resp = post(client, body)
    assert resp.status_code == 200, resp.text
    r = inserted_doc(fake_db)["rights"]
    assert all(len(r[s]) == 1 and r[s][0]["share_bp"] == 10000
               for s in ("writers", "publishers", "master_owners"))


@pytest.mark.parametrize("make", [sync_upload, base], ids=["sync", "ai_only"])
def test_upload_without_rights_rejected(client, fake_db, make):
    body = make()
    del body["rights"]
    resp = post(client, body)
    assert_rejected(resp, fake_db)
    assert "Add the splits for this upload." in resp.text


def test_bad_split_rejected_before_presign_url(client, fake_db):
    resp = post(client, sync_upload(rights=manual(writers=[party("Tyler Example", 9999)])))
    assert_rejected(resp, fake_db)
    assert "presigned_url" not in resp.text
    assert "Writers add up to 99.99%" in resp.text


def test_ai_only_stores_manual_rights(client, fake_db):
    resp = post(client, base(rights=manual()))
    assert resp.status_code == 200, resp.text
    doc = inserted_doc(fake_db)
    assert "intake" not in doc
    assert [p["share_bp"] for p in doc["rights"]["publishers"]] == [5000, 5000]


def test_ai_only_shortcut_has_no_pro_on_writer_row(client, fake_db):
    resp = post(client, base())
    assert resp.status_code == 200, resp.text
    w = inserted_doc(fake_db)["rights"]["writers"][0]
    assert w["share_bp"] == 10000 and w["is_self"] is True
    assert w["society"] is None and w["ipi_name_number"] is None


def test_build_rights_shortcut_without_intake():
    body = {"owns_everything": True, "self_legal_name": "Tyler Example", "attested": True}
    doc = build_rights(TrackRightsIn(**body), intake=None, clerk_user_id="u1", now_iso="t")
    assert doc["writers"][0]["society"] is None
    assert len(doc["master_owners"]) == 1
