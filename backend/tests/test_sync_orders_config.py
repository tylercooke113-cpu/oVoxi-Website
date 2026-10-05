"""PRD-03 Phase 6a: pricing and configuration (sync_orders.py)."""
import pytest

import sync_orders as so

ENV = ["SYNC_PRICE_CREATOR", "SYNC_PRICE_DIGITAL", "SYNC_PRICE_CAMPAIGN", "SYNC_PRICE_BROADCAST",
       "SYNC_CHECKOUT_ENABLED", "SYNC_DELIVER_STEMS", "STRIPE_SECRET_KEY", "SYNC_TOKEN_SECRET"]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ENV:
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize("tier,price", [("creator", 4900), ("digital", 29900)])
def test_base_prices(tier, price):
    assert so.price_cents(tier) == price   # Campaign/Broadcast need a term (see test_term_prices)


@pytest.mark.parametrize("tier,term,price", [
    ("campaign", "1y", 69900), ("campaign", "2y", 104900), ("campaign", "3y", 132900),
    ("campaign", "5y", 181900), ("campaign", "perpetual", 244900),
    ("broadcast", "1y", 149900), ("broadcast", "2y", 224900), ("broadcast", "3y", 284900),
    ("broadcast", "5y", 389900),
])
def test_term_prices(tier, term, price):
    assert so.price_cents(tier, term) == price


def test_stems_are_free():
    assert so.price_cents("digital") == 29900   # no stems uplift


def test_env_override_one_year_only(monkeypatch):
    monkeypatch.setenv("SYNC_PRICE_CAMPAIGN", "80000")
    assert so.price_cents("campaign", "1y") == 80000
    assert so.price_cents("campaign", "2y") == 104900   # other terms come from the table


def test_price_env_override(monkeypatch):
    monkeypatch.setenv("SYNC_PRICE_CREATOR", "2500")
    assert so.price_cents("creator") == 2500


@pytest.mark.parametrize("bad", ["abc", "0", "-5", "19.00"])
def test_bad_price_env_is_config_error(monkeypatch, bad):
    monkeypatch.setenv("SYNC_PRICE_CREATOR", bad)
    with pytest.raises(so.ConfigError):
        so.price_cents("creator")


def test_unknown_tier():
    with pytest.raises(ValueError):
        so.price_cents("enterprise")


def test_bad_or_missing_term_raises():
    with pytest.raises(ValueError):
        so.price_cents("campaign", "9y")
    with pytest.raises(ValueError):
        so.price_cents("campaign")   # term required for Campaign


def test_checkout_disabled_by_default_admin_test_key_only(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_abc")
    assert so.can_checkout(is_admin=True) is True
    assert so.can_checkout(is_admin=False) is False


def test_live_key_blocks_admin_while_disabled(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_abc")
    assert so.can_checkout(is_admin=True) is False


def test_enabled_opens_to_public(monkeypatch):
    monkeypatch.setenv("SYNC_CHECKOUT_ENABLED", "true")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_abc")
    assert so.can_checkout(is_admin=False) is True


def test_enabled_requires_exact_true(monkeypatch):
    monkeypatch.setenv("SYNC_CHECKOUT_ENABLED", "yes")
    assert so.checkout_enabled() is False


def test_missing_stripe_key(monkeypatch):
    with pytest.raises(so.ConfigError):
        so.can_checkout(is_admin=True)


def test_token_secret_min_length(monkeypatch):
    monkeypatch.setenv("SYNC_TOKEN_SECRET", "short")
    with pytest.raises(so.ConfigError):
        so.token_secret()
    monkeypatch.setenv("SYNC_TOKEN_SECRET", "x" * 64)
    assert so.token_secret() == b"x" * 64


def test_deliver_stems_defaults_true(monkeypatch):
    assert so.deliver_stems() is True
    monkeypatch.setenv("SYNC_DELIVER_STEMS", "false")
    assert so.deliver_stems() is False
