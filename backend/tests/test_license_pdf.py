"""PRD-03 Phase 6a: license PDF (license_pdf.py). Requires reportlab; pypdf only for text checks."""
import pytest

from license_pdf import TERMS, render_license_pdf

pypdf = pytest.importorskip("pypdf")

ORDER = {
    "license_id": "OVX-7K2M9Q4XRT", "created_at": "2026-09-29T12:00:00+00:00",
    "paid_at": "2026-09-29T12:01:00+00:00", "buyer_name": "Dana Buyer", "buyer_company": "",
    "buyer_email": "dana@example.com", "tier": "creator_pro", "include_stems": True,
    "price_cents": 6000, "tax_cents": 420, "amount_total_cents": 6420, "currency": "usd",
    "terms_version": "draft-0", "test_mode": True,
}


def text_of(pdf: bytes) -> str:
    from io import BytesIO
    return "\n".join(p.extract_text() for p in pypdf.PdfReader(BytesIO(pdf)).pages)


def test_renders_all_prd_fields():
    pdf = render_license_pdf(ORDER, track_title="Night Drive", artist_name="Kay Lune")
    assert pdf.startswith(b"%PDF")
    text = text_of(pdf)
    for expected in ("OVX-7K2M9Q4XRT", "September 29, 2026", "Dana Buyer", "dana@example.com",
                     "Night Drive", "Kay Lune", "Creator Pro", "$60.00 USD", "$4.20 USD", "$64.20 USD",
                     "draft-0", "PLACEHOLDER TERMS"):
        assert expected in text, expected


def test_test_mode_watermark_only_in_test():
    assert "TEST ORDER" in text_of(render_license_pdf(ORDER, track_title="T", artist_name="A"))
    live = dict(ORDER, test_mode=False)
    assert "TEST ORDER" not in text_of(render_license_pdf(live, track_title="T", artist_name="A"))


def test_markup_in_user_text_is_escaped():
    evil = dict(ORDER, buyer_name="<b>Bob</b> & <font size=90>Co", buyer_company="A<B")
    text = text_of(render_license_pdf(evil, track_title="<i>x</i>", artist_name="&amp;"))
    assert "<b>Bob</b> & <font size=90>Co" in text and "<i>x</i>" in text and "&amp;" in text


def test_long_names_wrap_without_error():
    long = dict(ORDER, buyer_company="Very Long Company Name " * 20)
    assert render_license_pdf(long, track_title="T" * 300, artist_name="A").startswith(b"%PDF")


def test_unknown_terms_version_fails_loudly():
    with pytest.raises(KeyError):
        render_license_pdf(dict(ORDER, terms_version="v9"), track_title="T", artist_name="A")


def test_draft_terms_exist():
    assert "draft-0" in TERMS
