"""PRD-03 Phase 6a: pricing and configuration (sync_orders.py)."""
import pytest

import sync_orders as so

ENV = ["SYNC_PRICE_CREATOR", "SYNC_PRICE_CREATOR_PRO", "SYNC_PRICE_BUSINESS_SOCIAL", "SYNC_STEMS_UPLIFT",
       "SYNC_CHECKOUT_ENABLED", "SYNC_DELIVER_STEMS", "STRIPE_SECRET_KEY", "SYNC_TOKEN_SECRET"]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ENV:
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize("tier,plain,stems", [
    ("creator", 1900, 2300), ("creator_pro", 4900, 6000), ("business_social", 14900, 18200),
])
def test_prd_price_table(tier, plain, stems):
    assert so.price_cents(tier, False) == plain
    assert so.price_cents(tier, True) == stems


def test_uplift_rounds_half_up_to_whole_dollar(monkeypatch):
    monkeypatch.setenv("SYNC_PRICE_CREATOR", "1000")
    monkeypatch.setenv("SYNC_STEMS_UPLIFT", "0.25")  # 12.50 -> 13
    assert so.price_cents("creator", True) == 1300


def test_price_env_override(monkeypatch):
    monkeypatch.setenv("SYNC_PRICE_CREATOR", "2500")
    assert so.price_cents("creator", False) == 2500


@pytest.mark.parametrize("bad", ["abc", "0", "-5", "19.00"])
def test_bad_price_env_is_config_error(monkeypatch, bad):
    monkeypatch.setenv("SYNC_PRICE_CREATOR", bad)
    with pytest.raises(so.ConfigError):
        so.price_cents("creator", False)


def test_unknown_tier():
    with pytest.raises(ValueError):
        so.price_cents("enterprise", False)


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
