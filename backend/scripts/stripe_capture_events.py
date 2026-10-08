#!/usr/bin/env python3
"""Capture REAL Stripe subscription event payloads as test fixtures (Brief 19).

    STRIPE_SECRET_KEY=sk_test_... python backend/scripts/stripe_capture_events.py

Drives, on a single test clock, every flow the webhook handles: subscribe, renew,
payment failure (card 4000000000000341), refund, and dispute (card 4000000000000259).
Then it reads the resulting events with events.list and writes each handled event type
to backend/tests/fixtures/stripe/<event.type>.json, with emails, names and addresses
scrubbed. Those fixtures let the handler tests run against real basil-shaped payloads,
so the two-format field accessors in subscriptions.py are reconciled against reality.

Refuses any key that is not a Stripe TEST key. Always deletes the test clock.
"""
import json
import os
import re
import sys
import time
from decimal import Decimal

import stripe

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import subscriptions as subs  # noqa: E402

# checkout.session.completed is intentionally excluded: completing a hosted Checkout Session
# cannot be driven headlessly, so the handler test for it uses a synthetic subscription session.
HANDLED = {"customer.subscription.created", "customer.subscription.updated",
           "customer.subscription.deleted", "invoice.paid", "invoice.payment_failed",
           "charge.refunded", "charge.dispute.created", "charge.dispute.closed"}

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures", "stripe")

# Field names whose values are scrubbed anywhere they appear in a payload.
_SCRUB_KEYS = {"email", "name", "receipt_email", "customer_email", "customer_name",
               "phone", "line1", "line2", "postal_code", "payer_email"}
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _scrub(obj):
    if isinstance(obj, dict):
        return {k: ("redacted@example.com" if k in ("email", "receipt_email", "customer_email", "payer_email")
                    else "Redacted" if k in _SCRUB_KEYS else _scrub(v))
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [_scrub(v) for v in obj]
    if isinstance(obj, str):
        return _EMAIL_RE.sub("redacted@example.com", obj)
    return obj


def _json_default(o):
    if isinstance(o, Decimal):
        return int(o) if o == o.to_integral_value() else float(o)
    return str(o)


def _advance(c, clock, to_ts):
    clock = c.v1.test_helpers.test_clocks.advance(clock.id, {"frozen_time": to_ts})
    while clock.status == "advancing":
        time.sleep(2)
        clock = c.v1.test_helpers.test_clocks.retrieve(clock.id)
    return clock


def main():
    key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not key.startswith(("sk_test_", "rk_test_")):
        sys.exit("Refusing to run without a Stripe TEST key.")
    c = stripe.StripeClient(key)
    print("Stripe Python library:", stripe.VERSION)

    def price(lk):
        return c.v1.prices.list({"lookup_keys": [lk], "limit": 1}).data[0].id

    def customer(clock, card):
        cust = c.v1.customers.create({"test_clock": clock.id, "email": "buyer@example.com", "name": "Test Buyer"})
        pm = c.v1.payment_methods.attach(card, {"customer": cust.id})
        c.v1.customers.update(cust.id, {"invoice_settings": {"default_payment_method": pm.id}})
        return cust

    clock = c.v1.test_helpers.test_clocks.create({"frozen_time": int(time.time())})
    api_versions = set()

    def scan():
        """Newest event per handled type, as dicts."""
        out = {}
        for ev in c.v1.events.list({"limit": 100}).auto_paging_iter():
            api_versions.add(ev.api_version)
            if ev.type in HANDLED and ev.type not in out:
                out[ev.type] = ev.to_dict()
        return out

    try:
        # A. subscribe + renew (pro monthly) ---------------------------------
        good = customer(clock, "pm_card_visa")
        subA = c.v1.subscriptions.create(
            {"customer": good.id, "items": [{"price": price("sub_pro_month")}],
             "metadata": {"user_id": "user_capture_a"}})

        # B. renewal payment failure: start healthy, then swap to a card that declines on charge.
        failc = customer(clock, "pm_card_visa")
        subB = c.v1.subscriptions.create(
            {"customer": failc.id, "items": [{"price": price("sub_creator_month")}],
             "metadata": {"user_id": "user_capture_b"}})
        badpm = c.v1.payment_methods.attach("pm_card_chargeCustomerFail", {"customer": failc.id})
        c.v1.customers.update(failc.id, {"invoice_settings": {"default_payment_method": badpm.id}})

        _, endA = subs.period_bounds(subA.to_dict())
        _, endB = subs.period_bounds(subB.to_dict())
        clock = _advance(c, clock, max(endA, endB) + 3600)         # A renews (paid), B renews (fails)
        print("A renewed, B renewal declined")

        # C. refund A's renewed (paid) invoice charge ------------------------
        paid = c.v1.invoices.list({"subscription": subA.id, "status": "paid", "limit": 1}).data[0]
        paid = c.v1.invoices.retrieve(paid.id, {"expand": ["payments"]})
        charge_id = subs.invoice_charge_id(paid.to_dict())
        if not charge_id:
            chs = c.v1.charges.list({"customer": good.id, "limit": 1}).data
            charge_id = chs[0].id if chs else None
        if charge_id:
            c.v1.refunds.create({"charge": charge_id})
            print("C refunded charge", charge_id)
        else:
            print("C skipped: no charge id on the paid invoice")

        # D. dispute, then close it (closing a test dispute resolves it as lost) ---
        dsp = customer(clock, "pm_card_createDispute")
        c.v1.subscriptions.create(
            {"customer": dsp.id, "items": [{"price": price("sub_creator_month")}],
             "metadata": {"user_id": "user_capture_d"}})
        print("D dispute subscription created", dsp.id)
        time.sleep(10)                                             # dispute is raised asynchronously

        opened = scan().get("charge.dispute.created")
        if opened:
            try:
                c.v1.disputes.close(opened["data"]["object"]["id"])
                print("D dispute closed (lost)")
                time.sleep(8)
            except stripe.StripeError as exc:
                print("D dispute close failed (capture created only):", exc.code)

        # Collect the newest event per handled type. ---------------------------
        os.makedirs(FIXTURE_DIR, exist_ok=True)
        seen = scan()
        for etype, ev in seen.items():
            path = os.path.join(FIXTURE_DIR, etype + ".json")
            with open(path, "w") as fh:
                json.dump(_scrub(ev), fh, indent=2, sort_keys=True, default=_json_default)
            print("wrote", os.path.relpath(path))
        missing = sorted(HANDLED - set(seen))
        if missing:
            print("NOT captured (drive manually or ignore if not applicable):", ", ".join(missing))
        print("account default API version(s) seen on events:", ", ".join(sorted(v for v in api_versions if v)))
    finally:
        c.v1.test_helpers.test_clocks.delete(clock.id)
        print("test clock deleted")


if __name__ == "__main__":
    main()
