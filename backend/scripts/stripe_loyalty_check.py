#!/usr/bin/env python3
"""Verify loyalty pricing with a Stripe test clock (Brief 19 item 7).

    STRIPE_SECRET_KEY=sk_test_... python backend/scripts/stripe_loyalty_check.py

Subscribes a clock customer to Pro monthly, prints the first invoice, then for each
upcoming invoice applies the loyalty coupon computed by subscriptions.loyalty_target
(from subscribed_since and the next period start) BEFORE advancing the clock. Switches to
Business for the 4th invoice. Expected Pro: 49.00, 49.00, 41.65, 41.65, then Business.
Uses the same StripeClient style as sync_orders.py. Always deletes the test clock.
"""
import os
import sys
import time
from datetime import datetime, timezone

import stripe

# Make the sibling backend modules importable when run as a script.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import subscriptions as subs  # noqa: E402


def _iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def main():
    key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not key.startswith(("sk_test_", "rk_test_")):
        sys.exit("Refusing to run without a Stripe TEST key.")
    c = stripe.StripeClient(key)
    print("Stripe Python library:", stripe.VERSION)

    def price(lk):
        return c.v1.prices.list({"lookup_keys": [lk], "limit": 1}).data[0].id

    clock = c.v1.test_helpers.test_clocks.create({"frozen_time": int(time.time())})
    try:
        cust = c.v1.customers.create({"test_clock": clock.id})
        pm = c.v1.payment_methods.attach("pm_card_visa", {"customer": cust.id})
        c.v1.customers.update(cust.id, {"invoice_settings": {"default_payment_method": pm.id}})
        sub = c.v1.subscriptions.create({"customer": cust.id, "items": [{"price": price("sub_pro_month")}]})
        start, end = subs.period_bounds(sub.to_dict())
        subscribed_since = _iso(start)

        inv = c.v1.invoices.list({"subscription": sub.id, "limit": 1}).data[0]
        print(f"invoice 1: ${inv.total / 100:.2f}")

        for n in range(2, 9):
            # Apply the coupon for the UPCOMING invoice (period starts at the current period end).
            target = subs.loyalty_target(subscribed_since, _iso(end))
            coupon = subs.LOYALTY_COUPONS.get(target)
            if coupon:
                c.v1.subscriptions.update(sub.id, {"discounts": [{"coupon": coupon}]})
            if n == 4:
                item = c.v1.subscriptions.retrieve(sub.id)["items"]["data"][0]["id"]
                c.v1.subscriptions.update(sub.id, {"items": [{"id": item, "price": price("sub_business_month")}],
                                                   "proration_behavior": "none"})

            clock = c.v1.test_helpers.test_clocks.advance(clock.id, {"frozen_time": end + 3600})
            while clock.status == "advancing":
                time.sleep(2)
                clock = c.v1.test_helpers.test_clocks.retrieve(clock.id)

            sub = c.v1.subscriptions.retrieve(sub.id)
            start, end = subs.period_bounds(sub.to_dict())
            inv = c.v1.invoices.list({"subscription": sub.id, "limit": 1}).data[0]
            print(f"invoice {n}: ${inv.total / 100:.2f} (target {target}%{' , switched to Business' if n == 4 else ''})")
        print("Expected Pro: 49.00, 49.00, 41.65, 41.65 (switch to Business), then Business with the discount.")
    finally:
        c.v1.test_helpers.test_clocks.delete(clock.id)
        print("test clock deleted")


if __name__ == "__main__":
    main()
