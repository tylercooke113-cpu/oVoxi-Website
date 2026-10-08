#!/usr/bin/env python3
"""Idempotent Stripe setup for oVoxi subscriptions (Brief 19).

    STRIPE_SECRET_KEY=sk_test_... python backend/scripts/stripe_subscriptions_setup.py

Creates missing products, prices (by lookup key), coupons and a Customer Portal config,
and changes nothing that already exists. Prints STRIPE_PORTAL_CONFIG_ID. Uses the same
StripeClient style as backend/sync_orders.py.
"""
import os
import sys

import stripe

PRODUCTS = {"creator": "oVoxi Creator", "pro": "oVoxi Pro", "business": "oVoxi Business"}
PRICES = [
    ("sub_creator_month", "creator", 1900, "month"), ("sub_creator_year", "creator", 19000, "year"),
    ("sub_pro_month", "pro", 4900, "month"), ("sub_pro_year", "pro", 49000, "year"),
    ("sub_business_month", "business", 14900, "month"), ("sub_business_year", "business", 149000, "year"),
]
COUPONS = [("LOYALTY15", 15), ("LOYALTY20", 20)]
PORTAL_MARKER = "v1"


def _meta(obj) -> dict:
    """metadata as a plain dict. StripeObject has no .get in the v1 services client."""
    return (obj.to_dict().get("metadata") or {}) if hasattr(obj, "to_dict") else (obj.get("metadata") or {})


def main():
    key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not key.startswith(("sk_test_", "rk_test_")):
        sys.exit("Refusing to run without a Stripe TEST key in STRIPE_SECRET_KEY.")
    print("Stripe Python library:", stripe.VERSION)
    print("Pinned API version:", getattr(stripe, "api_version", "account default"))
    c = stripe.StripeClient(key)

    # Products matched by metadata.ovoxi_plan, not by name.
    by_plan = {}
    for p in c.v1.products.list({"limit": 100}).auto_paging_iter():
        plan = _meta(p).get("ovoxi_plan")
        if plan:
            by_plan[plan] = p
    product_ids = {}
    for plan, name in PRODUCTS.items():
        p = by_plan.get(plan)
        if p:
            print(f"exists  product {plan} {p.id}")
        else:
            p = c.v1.products.create({"name": name, "metadata": {"ovoxi_plan": plan}})
            print(f"created product {plan} {p.id}")
        product_ids[plan] = p.id

    price_ids = {}
    for lk, plan, amount, interval in PRICES:
        found = c.v1.prices.list({"lookup_keys": [lk], "limit": 1}).data
        if found:
            price_ids[lk] = found[0].id
            print(f"exists  price {lk} {found[0].id}")
        else:
            pr = c.v1.prices.create({"product": product_ids[plan], "currency": "usd",
                                     "unit_amount": amount, "recurring": {"interval": interval},
                                     "lookup_key": lk, "tax_behavior": "exclusive"})
            price_ids[lk] = pr.id
            print(f"created price {lk} {pr.id}")

    for cid, pct in COUPONS:
        try:
            c.v1.coupons.retrieve(cid)
            print(f"exists  coupon {cid}")
        except stripe.InvalidRequestError:
            c.v1.coupons.create({"id": cid, "percent_off": pct, "duration": "forever"})
            print(f"created coupon {cid}")

    existing = [cfg for cfg in c.v1.billing_portal.configurations.list({"limit": 100}).auto_paging_iter()
                if _meta(cfg).get("ovoxi_subscriptions") == PORTAL_MARKER]
    if existing:
        print("exists  portal config")
        print("STRIPE_PORTAL_CONFIG_ID=", existing[0].id)
        return

    products_block = [{"product": product_ids[plan],
                       "prices": [price_ids[lk] for lk, p, *_ in PRICES if p == plan]}
                      for plan in PRODUCTS]
    features = {
        "payment_method_update": {"enabled": True},
        "invoice_history": {"enabled": True},
        "subscription_cancel": {"enabled": True, "mode": "at_period_end"},
        "subscription_update": {"enabled": True, "default_allowed_updates": ["price"],
                                "proration_behavior": "create_prorations", "products": products_block},
    }
    params = {"metadata": {"ovoxi_subscriptions": PORTAL_MARKER}, "features": features}
    try:
        cfg = c.v1.billing_portal.configurations.create(params)
    except stripe.InvalidRequestError as exc:
        if "business_profile" in str(exc):
            print("portal config needed a business_profile; adding privacy and terms URLs")
            params["business_profile"] = {"privacy_policy_url": "https://ovoxi.net/privacy",
                                          "terms_of_service_url": "https://ovoxi.net/license-terms"}
            cfg = c.v1.billing_portal.configurations.create(params)
        else:
            raise
    print("created portal config")
    print("STRIPE_PORTAL_CONFIG_ID=", cfg.id)


if __name__ == "__main__":
    main()
