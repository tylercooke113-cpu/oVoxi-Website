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
    assert c["terms_version"] == "v1" and c["terms_url"] == "/license-terms"
    assert c["subscriptions_enabled"] is False
    assert [(t["id"], t["price_cents"]) for t in c["tiers"]] == [
        ("creator", 4900), ("digital", 29900), ("campaign", 69900), ("broadcast", 149900)]
    campaign = next(t for t in c["tiers"] if t["id"] == "campaign")
    assert campaign["terms"][0] == {"id": "1y", "label": "1 year", "price_cents": 69900}
    assert campaign["needs_territory"] is False
    broadcast = next(t for t in c["tiers"] if t["id"] == "broadcast")
    assert broadcast["needs_territory"] is True and len(broadcast["terms"]) == 4
    assert next(t for t in c["tiers"] if t["id"] == "creator")["terms"] is None
    assert any(x["code"] == "CA" and x["name"] == "Canada" for x in c["countries"])


def test_public_gets_nothing_while_disabled(env):
    env[1]["viewer"] = None
    assert cfg(env) == {"can_checkout": False}


def test_public_gets_config_when_enabled(env, monkeypatch):
    monkeypatch.setenv("SYNC_CHECKOUT_ENABLED", "true")
    env[1]["viewer"] = None
    assert cfg(env)["can_checkout"] is True


def test_stems_off(env, monkeypatch):
    monkeypatch.setenv("SYNC_DELIVER_STEMS", "false")
    assert cfg(env)["stems_available"] is False


def test_subscriptions_flag(env, monkeypatch):
    monkeypatch.setenv("SUBSCRIPTIONS_ENABLED", "true")
    assert cfg(env)["subscriptions_enabled"] is True


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
        term = "1y" if t["terms"] else None
        assert t["price_cents"] == so.price_cents(t["id"], term)
