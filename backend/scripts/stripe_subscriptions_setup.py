#!/usr/bin/env python3
"""Idempotent Stripe setup for oVoxi subscriptions (Brief 19).

    STRIPE_SECRET_KEY=sk_test_... python backend/scripts/stripe_subscriptions_setup.py

Creates missing products, prices (by lookup key), coupons and a Customer Portal config,
and changes nothing that already exists. Prints STRIPE_PORTAL_CONFIG_ID. Uses the same
StripeClient style as backend/sync_orders.py.
"""
import json
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
    dry = os.environ.get("DRY_RUN", "").strip() == "1"   # preview mutations without calling Stripe
    if dry:
        print("DRY_RUN=1: no Stripe writes will be made; mutations are printed instead.")
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
            product_ids[plan] = p.id
        elif dry:
            print(f"DRY_RUN would create product {plan}")
            product_ids[plan] = f"(dry:product:{plan})"
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
        elif dry:
            print(f"DRY_RUN would create price {lk} ({amount} {interval})")
            price_ids[lk] = f"(dry:price:{lk})"
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
            if dry:
                print(f"DRY_RUN would create coupon {cid} ({pct}%)")
            else:
                c.v1.coupons.create({"id": cid, "percent_off": pct, "duration": "forever"})
                print(f"created coupon {cid}")

    products_block = [{"product": product_ids[plan],
                       "prices": [price_ids[lk] for lk, p, *_ in PRICES if p == plan]}
                      for plan in PRODUCTS]
    # always_invoice bills plan upgrades immediately (prorated) instead of deferring the proration
    # to the next renewal, which is what create_prorations does. See docs/LAUNCH-CHECKLIST-sync.md.
    subscription_update = {"enabled": True, "default_allowed_updates": ["price"],
                           "proration_behavior": "always_invoice", "products": products_block}
    features = {
        "payment_method_update": {"enabled": True},
        "invoice_history": {"enabled": True},
        "subscription_cancel": {"enabled": True, "mode": "at_period_end"},
        "subscription_update": subscription_update,
    }

    # An existing config is updated in place so its id (STRIPE_PORTAL_CONFIG_ID) never changes; only
    # creating a brand-new config would mint a new id. Re-running is therefore idempotent.
    existing = [cfg for cfg in c.v1.billing_portal.configurations.list({"limit": 100}).auto_paging_iter()
                if _meta(cfg).get("ovoxi_subscriptions") == PORTAL_MARKER]
    if existing:
        cfg_id = existing[0].id
        update = {"features": {"subscription_update": subscription_update}}
        if dry:
            print(f"DRY_RUN would update portal config {cfg_id} in place with:")
            print(json.dumps(update, indent=2, sort_keys=True))
        else:
            c.v1.billing_portal.configurations.update(cfg_id, update)
            print("updated portal config in place (subscription_update.proration_behavior=always_invoice)")
        print("STRIPE_PORTAL_CONFIG_ID=", cfg_id)
        return

    params = {"metadata": {"ovoxi_subscriptions": PORTAL_MARKER}, "features": features}
    if dry:
        print("DRY_RUN would create a new portal config with features:")
        print(json.dumps(features, indent=2, sort_keys=True))
        return
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
