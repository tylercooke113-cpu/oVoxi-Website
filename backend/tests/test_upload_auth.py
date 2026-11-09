"""Brief 28 Part A: Artist Agreement v6, Co-owner Consent v4, Upload Authorization v1.

Pure-function tests against the real backend/agreements/*.txt (no Mongo, no HTTP):
template rendering, hashing, the supports_authorized_uploaders flag, the cosign v4
on-behalf clause, and the three-party Upload Authorization signature block.
"""
from datetime import datetime, timezone
from io import BytesIO

import pytest

import artist_agreement as aa
import cosign
import upload_auth


NOW = datetime(2026, 10, 28, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# A1: Artist Agreement v6
# ---------------------------------------------------------------------------

def test_supports_authorized_uploaders_v6_only():
    assert aa.supports_authorized_uploaders("v6") is True
    for old in ("v1", "v2", "v3", "v4", "v5"):
        assert aa.supports_authorized_uploaders(old) is False


def test_v6_renders_without_version_or_placeholders():
    vals = {"agreement_date": "28th day of October, 2026",
            "licensor_party": "Jane Q Smith, of 1 Main St, Austin, TX 78701, USA",
            "licensor_email": "jane@example.com", "platform_account_id": "user_test"}
    text = aa.render_text("v6", vals)
    assert "{{" not in text.replace(aa.SIGNATURE_MARKER, "")
    assert "—" not in text                                   # no em dashes


def test_v6_carries_the_part_a_changes():
    text = aa.load_template("v6")
    assert "2.3 Authorized Uploaders." in text
    assert '1.20 "Authorized Uploader" means' in text
    assert '1.21 "Upload Authorization" means' in text
    assert "or by an Authorized Uploader on the Licensor's behalf" in text        # 1.4
    assert "The Licensor, and not an Authorized Uploader, may elect" in text       # 3.4(a)
    assert "whether uploaded by the Licensor or by an Authorized Uploader" in text  # 9.1
    assert "did not intend it to be licensed" in text                              # 12.4
    assert "does not count toward the limit in Section 12.4" in text               # 2.3(f)/12.4
    assert "Nothing in this Agreement makes an Authorized Uploader" in text         # 17.4


def test_v6_is_v5_elsewhere():
    # A sample of untouched v5 text must survive verbatim in v6.
    v5, v6 = aa.load_template("v5"), aa.load_template("v6")
    for line in ("3.4 Exclusive Election and Exclusive Licenses.",
                 "forty percent (40%)",
                 "16.2 This Agreement will be governed by and construed"):
        assert line in v5 and line in v6


# ---------------------------------------------------------------------------
# A2 / A6: Co-owner Consent v4 and the on-behalf clause
# ---------------------------------------------------------------------------

def test_on_behalf_clause_empty_and_filled():
    assert cosign.on_behalf_clause("") == ""
    assert cosign.on_behalf_clause("   ") == ""
    assert cosign.on_behalf_clause("Studio X") == (
        ", through Studio X, acting as the Uploader's Authorized Uploader under the Artist Agreement,")


def _cosign_vals(**over):
    base = dict(now=NOW, entity_type="individual", legal_name="Jane Co",
                coowner_email="jane@example.com", uploader_name="Upload Artist",
                work_title="Night Drive", work_artist="Artist", work_id="w1",
                interests=[{"side": "writers", "legal_name": "Jane Co", "role": "C", "share_bp": 10000}])
    base.update(over)
    return cosign.build_values(**base)


def test_cosign_v4_artist_upload_reads_cleanly():
    text = cosign.render_text(_cosign_vals(), "cosign_v4")
    assert "{{" not in text.replace(aa.SIGNATURE_MARKER, "")
    assert 'at ovoxi.net (the "Platform") and listed the Co-owner' in text
    assert "any Authorized Uploader acting for the Uploader" in text               # 2.2 change
    assert "—" not in text


def test_cosign_v4_delegated_upload_names_the_uploader():
    text = cosign.render_text(_cosign_vals(authorized_uploader_name="Studio X"), "cosign_v4")
    assert ('(the "Platform"), through Studio X, acting as the Uploader\'s Authorized Uploader '
            "under the Artist Agreement, and listed the Co-owner") in text


def test_cosign_v3_unaffected_by_new_value():
    # The extra on_behalf_clause value is harmless for a template without the placeholder.
    text = cosign.render_text(_cosign_vals(authorized_uploader_name="Studio X"), "cosign_v3")
    assert "{{" not in text.replace(aa.SIGNATURE_MARKER, "")
    assert "through Studio X" not in text


# ---------------------------------------------------------------------------
# A5: Upload Authorization v1
# ---------------------------------------------------------------------------

def test_authorized_uses_text():
    assert upload_auth.authorized_uses_text(["ai_training", "sync"]) == (
        "the AI Training Field of Use and the Sync Field of Use")
    assert upload_auth.authorized_uses_text(["sync"]) == "the Sync Field of Use only"
    assert upload_auth.authorized_uses_text(["ai_training"]) == "the AI Training Field of Use only"
    with pytest.raises(ValueError):
        upload_auth.authorized_uses_text([])


def test_uploader_party():
    assert upload_auth.uploader_party("ovoxi") == "OVOXI, Inc., acting through its employees"
    assert upload_auth.uploader_party("person", "  Sam Engineer ") == "Sam Engineer"


def _ua_vals(**over):
    base = dict(now=NOW, licensor_party="Jane Q Smith, of 1 Main St, Austin, TX 78701, USA",
                licensor_email="jane@example.com", platform_account_id="user_artist",
                kind="person", uploader_name="Sam Engineer", uploader_email="sam@example.com",
                uploader_role="Engineer", uses=["sync"])
    base.update(over)
    return upload_auth.build_values(**base)


def test_upload_auth_renders_without_placeholders():
    text = upload_auth.render_text(_ua_vals(), "upload_auth_v1")
    assert "{{" not in text.replace(aa.SIGNATURE_MARKER, "")
    assert "Sam Engineer" in text and "the Sync Field of Use only" in text
    assert "—" not in text


def test_upload_auth_ovoxi_party_in_text():
    text = upload_auth.render_text(
        _ua_vals(kind="ovoxi", uploader_name="", uploader_role="OVOXI",
                 uses=["ai_training", "sync"]), "upload_auth_v1")
    assert "OVOXI, Inc., acting through its employees" in text
    assert "the AI Training Field of Use and the Sync Field of Use" in text


def _ua_sig(**over):
    sig = {"authorization_id": "ua-1", "version": "upload_auth_v1", "text_sha256": "c" * 64,
           "kind": "person", "artist_typed_signature": "Jane Q Smith",
           "artist_legal_name": "Jane Q Smith", "artist_email": "jane@example.com",
           "artist_signed_at": "2026-10-28T00:00:00+00:00", "artist_ip": "203.0.113.1",
           "uploader_typed_signature": "Sam Engineer", "uploader_name": "Sam Engineer",
           "uploader_email": "sam@example.com", "uploader_signed_at": "2026-10-28T01:00:00+00:00",
           "uploader_ip": "203.0.113.2"}
    sig.update(over)
    return sig


def test_upload_auth_pdf_three_party():
    pypdf = pytest.importorskip("pypdf")
    text = upload_auth.render_text(_ua_vals(), "upload_auth_v1")
    pdf = upload_auth.render_pdf(text, _ua_sig())
    assert pdf[:4] == b"%PDF"
    body = "\n".join(p.extract_text() for p in pypdf.PdfReader(BytesIO(pdf)).pages)
    assert "ARTIST" in body and "AUTHORIZED UPLOADER" in body and "LICENSEE" in body
    assert "Document fingerprint" in body and "cccccccccccccccc" in body
    assert "Uploader signed at (UTC)" in body


def test_upload_auth_pdf_ovoxi_two_party():
    pypdf = pytest.importorskip("pypdf")
    text = upload_auth.render_text(
        _ua_vals(kind="ovoxi", uploader_name="", uploader_role="OVOXI",
                 uses=["ai_training", "sync"]), "upload_auth_v1")
    pdf = upload_auth.render_pdf(text, _ua_sig(kind="ovoxi"))
    body = "\n".join(p.extract_text() for p in pypdf.PdfReader(BytesIO(pdf)).pages)
    assert "ARTIST" in body and "LICENSEE" in body
    assert "AUTHORIZED UPLOADER" not in body
    assert "Uploader signed at (UTC)" not in body
