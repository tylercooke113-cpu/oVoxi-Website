"""Brief 20 B6: GET /api/sync/pricing, the public Pricing-page endpoint (B1).

Proves every number comes from server constants (PLANS and the single-track prices),
the `visible` gate, the subscriptions_enabled rule, that the endpoint is read-only
(never warms the Stripe price cache), and that it leaks nothing outside the allowlist.
"""
import pytest
from fastapi.testclient import TestClient

import server
import subscriptions as subs
import sync_orders as so
from sync_constants import PLANS, SUB_DAY_CAP

ADMIN = {"sub": "user_admin", "metadata": {"role": "admin"}}

PLAN_KEYS = {"id", "label", "month_cents", "year_cents", "month_cap", "day_cap",
             "month_cents_loyalty15", "month_cents_loyalty20"}
SINGLE_KEYS = {"id", "label", "price_cents", "by_quote"}
TOP_KEYS = {"visible", "library_visible", "subscriptions_enabled", "plans", "singles"}


@pytest.fixture
def env(monkeypatch):
    monkeypatch.delenv("SYNC_PUBLIC_PAGES_ENABLED", raising=False)
    monkeypatch.delenv("SUBSCRIPTIONS_ENABLED", raising=False)
    monkeypatch.setattr(server.limiter, "enabled", False)
    # Default: subscriptions resolved so the happy path has prices without touching Stripe.
    monkeypatch.setattr(subs, "prices_ready", lambda: True)
    state = {"viewer": None}
    server.app.dependency_overrides[server.optional_clerk] = lambda: state["viewer"]
    yield TestClient(server.app), state, monkeypatch
    server.app.dependency_overrides.clear()


def pricing(env):
    return env[0].get("/api/sync/pricing").json()


def test_plan_values_equal_constants(env):
    plans = {p["id"]: p for p in pricing(env)["plans"]}
    assert set(plans) == set(PLANS)
    for pid, src in PLANS.items():
        p = plans[pid]
        assert p["label"] == src["label"]
        assert p["month_cents"] == src["month_cents"]
        assert p["year_cents"] == src["year_cents"]
        assert p["month_cap"] == src["month_cap"]
        assert p["day_cap"] == SUB_DAY_CAP
        # Loyalty prices use the one shared formula; the client does no discount math.
        assert p["month_cents_loyalty15"] == subs.loyalty_price_cents(src["month_cents"], 15)
        assert p["month_cents_loyalty20"] == subs.loyalty_price_cents(src["month_cents"], 20)


def test_single_track_prices_equal_checkout_prices(env):
    singles = {s["id"]: s for s in pricing(env)["singles"]}
    assert set(singles) == set(so.TIERS) | {"enterprise"}
    for tid in so.TIERS:
        term = "1y" if tid in so.TERM_OPTIONS else None
        assert singles[tid]["price_cents"] == so.price_cents(tid, term)
        assert singles[tid]["by_quote"] is False
        assert singles[tid]["label"] == so.TIERS[tid][0]
    # Enterprise is quote-only and carries no price.
    assert singles["enterprise"]["by_quote"] is True
    assert singles["enterprise"]["price_cents"] is None


@pytest.mark.parametrize("viewer, gate_on, expect", [
    (None,  False, False),
    (None,  True,  True),
    (ADMIN, False, True),
    (ADMIN, True,  True),
])
def test_visible_matrix(env, viewer, gate_on, expect):
    client, state, mp = env
    state["viewer"] = viewer
    mp.setenv("SYNC_PUBLIC_PAGES_ENABLED", "true" if gate_on else "false")
    assert pricing(env)["visible"] is expect


@pytest.mark.parametrize("flag, ready, expect", [
    (False, True,  False),   # flag off wins even with prices ready
    (True,  False, False),   # flag on but prices not resolved
    (True,  True,  True),
])
def test_subscriptions_enabled_rule(env, flag, ready, expect):
    client, state, mp = env
    if flag:
        mp.setenv("SUBSCRIPTIONS_ENABLED", "true")
    mp.setattr(subs, "prices_ready", lambda: ready)
    assert pricing(env)["subscriptions_enabled"] is expect


def test_read_only_never_warms_price_cache(env):
    """B1 must not call Stripe or warm the cache, even with the flag on and prices empty
    (unlike /sync/checkout/config, which warms). It only reads prices_ready()."""
    client, state, mp = env
    mp.setenv("SUBSCRIPTIONS_ENABLED", "true")
    mp.setattr(subs, "prices_ready", lambda: False)

    def _boom(client):
        raise AssertionError("ensure_prices must not be called from /sync/pricing")

    mp.setattr(subs, "ensure_prices", _boom)
    body = pricing(env)
    assert body["subscriptions_enabled"] is False
    # Plans and singles are still returned from constants with no cache dependency.
    assert {p["id"] for p in body["plans"]} == set(PLANS)


def test_response_has_only_allowlisted_keys(env):
    body = pricing(env)
    assert set(body) == TOP_KEYS
    for p in body["plans"]:
        assert set(p) == PLAN_KEYS
    for s in body["singles"]:
        assert set(s) == SINGLE_KEYS
