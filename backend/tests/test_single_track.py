"""Brief 18: single-track tiers, terms, scopes, Stripe params, and the terms endpoint."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from pypdf import PdfReader

import licenses as lic
import server
import sync_orders as so

NOW = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- scopes

def test_add_months_clamps_and_rolls_over():
    jan31 = datetime(2026, 1, 31, 12, 0, tzinfo=timezone.utc)
    assert lic._add_months(jan31, 1).date().isoformat() == "2026-02-28"      # clamp to end of Feb
    assert lic._add_months(jan31, 12).date().isoformat() == "2027-01-31"     # year rollover, no clamp


def test_scope_creator():
    s = lic.license_scope("creator", NOW.isoformat())
    assert s["territory"] == "Worldwide" and s["term_label"] == "Perpetual for the project"
    assert s["term_end"] is None and s["paid_term_end"] is None and s["media_spend_cap_cents"] is None


def test_scope_digital():
    s = lic.license_scope("digital", NOW.isoformat())
    assert s["media_spend_cap_cents"] == 2500000 and s["term_end"] is None
    assert s["paid_term_end"] == lic._add_months(NOW, 12).isoformat()
    assert "Paid ads 12 months" in s["term_label"]


@pytest.mark.parametrize("term,label,end", [
    ("1y", "1 year from the license date", True), ("2y", "2 years from the license date", True),
    ("perpetual", "Perpetual", False),
])
def test_scope_campaign(term, label, end):
    s = lic.license_scope("campaign", NOW.isoformat(), term=term)
    assert s["term_label"] == label and s["media_spend_cap_cents"] == 10000000
    assert (s["term_end"] is not None) is end and s["paid_term_end"] == s["term_end"]


def test_scope_broadcast():
    s = lic.license_scope("broadcast", NOW.isoformat(), term="1y", territory="CA")
    assert s["territory"] == "Canada" and s["term_end"] is None   # programs/films perpetual
    assert s["paid_term_end"] == lic._add_months(NOW, 12).isoformat()
    assert s["media_spend_cap_cents"] == 25000000 and "Ads: 1 year" in s["term_label"]


def test_scope_legacy():
    s = lic.license_scope("creator_pro", NOW.isoformat())
    assert s["territory"] == "Worldwide" and s["term_label"] == "Perpetual for the project"


def test_legacy_tier_label():
    assert so.tier_label("creator_pro") == "Creator Pro"
    assert so.tier_label("business_social") == "Business Social"


# --------------------------------------------------------------------------- checkout validation (model)

def base(**over):
    b = {"track_id": "t1", "tier": "digital", "buyer_name": "B", "buyer_email": "b@example.com",
         "project_name": "P", "accept_terms": True, "terms_version": "v1"}
    b.update(over)
    return b


@pytest.mark.parametrize("over", [
    {"tier": "campaign"},                               # campaign needs a term
    {"tier": "digital", "term": "1y"},                  # digital must not have a term
    {"tier": "broadcast", "term": "1y"},                # broadcast needs a territory
    {"tier": "broadcast", "term": "1y", "territory": "ZZ"},   # unknown country
    {"tier": "broadcast", "term": "perpetual", "territory": "US"},  # broadcast has no perpetual
    {"tier": "creator_pro"},                            # old id not buyable
    {"tier": "campaign", "term": "1y", "territory": "US"},     # territory only for broadcast
])
def test_checkout_validation_rejects(over):
    with pytest.raises(ValidationError):
        server.CheckoutRequest(**base(**over))


def test_checkout_validation_accepts():
    server.CheckoutRequest(**base(tier="campaign", term="2y"))
    server.CheckoutRequest(**base(tier="broadcast", term="1y", territory="CA"))
    server.CheckoutRequest(**base(tier="creator"))


# --------------------------------------------------------------------------- Stripe params + stems price

def _order(**over):
    return so.build_order(track={"id": "t1", "clerk_user_id": "u"}, test_mode=True, now=NOW,
                          buyer_name="B", buyer_company="", buyer_email="b@example.com",
                          track_title="Night Drive", artist_display_name="Kay Lune", **over)


def test_stripe_params_amount_and_description():
    camp = _order(tier="campaign", term="2y", include_stems=False)
    p = so.checkout_session_params(camp, now=NOW)
    assert p["line_items"][0]["price_data"]["unit_amount"] == 104900
    assert "Campaign license, 2 years." in p["line_items"][0]["price_data"]["product_data"]["description"]

    bc = _order(tier="broadcast", term="1y", territory="CA", include_stems=False)
    desc = so.checkout_session_params(bc, now=NOW)["line_items"][0]["price_data"]["product_data"]["description"]
    assert "Broadcast license, 1 year, Canada." in desc


def test_stems_do_not_change_order_price():
    assert _order(tier="creator", include_stems=True)["price_cents"] == _order(tier="creator", include_stems=False)["price_cents"]


# --------------------------------------------------------------------------- terms endpoint + PDF

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(server.limiter, "enabled", False)
    return TestClient(server.app)


def test_terms_endpoint(client):
    r = client.get("/api/sync/terms/v1")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "v1" and isinstance(body["blocks"], list) and body["blocks"]
    assert body["blocks"][0] == {"type": "title", "text": "oVoxi Music License Terms"}
    assert client.get("/api/sync/terms/v9").status_code == 404


def test_certificate_has_terms_title():
    from license_pdf import render_license_pdf
    order = {"license_id": "OVX-AAAAAAAAAA", "created_at": NOW.isoformat(), "paid_at": NOW.isoformat(),
             "buyer_name": "B", "buyer_company": "", "buyer_email": "b@example.com", "tier": "digital",
             "include_stems": False, "price_cents": 29900, "tax_cents": 0, "amount_total_cents": 29900,
             "currency": "usd", "terms_version": "v1", "test_mode": True}
    pdf = render_license_pdf(order, track_title="Night Drive", artist_name="Kay Lune",
                             license={"scope": lic.license_scope("digital", NOW.isoformat()),
                                      "project": {}, "cue_sheet": []})
    text = "".join(page.extract_text() for page in PdfReader_bytes(pdf))
    assert "oVoxi Music License Terms" in text


def PdfReader_bytes(data):
    from io import BytesIO
    return PdfReader(BytesIO(data)).pages
