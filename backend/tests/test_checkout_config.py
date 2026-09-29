"""PRD-03 Phase 6b: GET /api/sync/checkout/config for the license modal."""
import pytest
from fastapi.testclient import TestClient

import server
import sync_orders as so

ADMIN = {"sub": "user_admin", "metadata": {"role": "admin"}}


@pytest.fixture
def env(monkeypatch):
    for name in ("SYNC_CHECKOUT_ENABLED", "SYNC_DELIVER_STEMS", "SYNC_TERMS_VERSION", "SYNC_PRICE_CREATOR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_abc")
    monkeypatch.setenv("SYNC_TOKEN_SECRET", "s" * 64)
    monkeypatch.setattr(server.limiter, "enabled", False)
    state = {"viewer": ADMIN}
    server.app.dependency_overrides[server.optional_clerk] = lambda: state["viewer"]
    yield TestClient(server.app), state
    server.app.dependency_overrides.clear()


def cfg(env):
    return env[0].get("/api/sync/checkout/config").json()


def test_admin_test_mode_gets_full_config(env):
    c = cfg(env)
    assert c["can_checkout"] is True and c["test_mode"] is True and c["stems_available"] is True
    assert c["terms_version"] == "draft-0" and c["terms"][0].startswith("PLACEHOLDER TERMS")
    assert [(t["id"], t["price_cents"], t["price_with_stems_cents"]) for t in c["tiers"]] == [
        ("creator", 1900, 2300), ("creator_pro", 4900, 6000), ("business_social", 14900, 18200)]
    assert all(t["description"] == "Test" for t in c["tiers"])


def test_public_gets_nothing_while_disabled(env):
    env[1]["viewer"] = None
    assert cfg(env) == {"can_checkout": False}


def test_public_gets_config_when_enabled(env, monkeypatch):
    monkeypatch.setenv("SYNC_CHECKOUT_ENABLED", "true")
    env[1]["viewer"] = None
    assert cfg(env)["can_checkout"] is True


def test_stems_off_hides_stem_prices(env, monkeypatch):
    monkeypatch.setenv("SYNC_DELIVER_STEMS", "false")
    c = cfg(env)
    assert c["stems_available"] is False and all(t["price_with_stems_cents"] is None for t in c["tiers"])


def test_price_override_is_reflected(env, monkeypatch):
    monkeypatch.setenv("SYNC_PRICE_CREATOR", "2500")
    assert cfg(env)["tiers"][0]["price_cents"] == 2500


@pytest.mark.parametrize("env_name,value", [("SYNC_TOKEN_SECRET", "short"), ("SYNC_PRICE_CREATOR", "abc"),
                                            ("SYNC_TERMS_VERSION", "v9")])
def test_misconfiguration_means_no_checkout(env, monkeypatch, env_name, value):
    monkeypatch.setenv(env_name, value)
    assert cfg(env) == {"can_checkout": False}


def test_missing_stripe_key_means_no_checkout(env, monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY")
    assert cfg(env) == {"can_checkout": False}


def test_config_prices_match_checkout_prices(env):
    for t in cfg(env)["tiers"]:
        assert t["price_cents"] == so.price_cents(t["id"], False)
        assert t["price_with_stems_cents"] == so.price_cents(t["id"], True)
