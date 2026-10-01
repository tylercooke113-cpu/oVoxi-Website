# Sync marketplace launch checklist (PRD-03)

Created 2026-09-30, when Phase 6 (checkout, delivery, email, admin orders) was complete and verified in production on Stripe test mode. Work through this before setting `SYNC_CHECKOUT_ENABLED=true` on Railway. Check items off in this file as they are done.

## Legal (counsel)

- [ ] Final license text. Replace `draft-0` in `backend/license_pdf.py` `TERMS` with a new version key and set `SYNC_TERMS_VERSION` to it.
- [ ] Artist grant text and split attestation wording (PRD-03 §14).
- [ ] Re-consent plan for artists who opted in under grant `draft-0`.
- [ ] Confirm the library copy "Discover our royalty-free music for videos".
- [ ] Real tier descriptions. Replace "Test" in `backend/sync_orders.py` `TIER_DESCRIPTIONS`.
- [ ] OQ-3 (model-weight licensing) answered. Decides `SYNC_DELIVER_STEMS` for live sales.
- [ ] Confirm the grant covers public profiles (gate for `SYNC_PUBLIC_PAGES_ENABLED`).

## Tax and money (Jose / accountant)

- [ ] Stripe product tax code for sync licenses. Set `SYNC_STRIPE_TAX_CODE`.
- [ ] Stripe Tax registrations for the states or countries where tax must be collected.
- [ ] Head office address in Stripe **live** mode (Settings, Tax). Checkout fails without it.
- [ ] Artist revenue split for sync sales. Optionally add an artist share column to the orders CSV.

## Stripe live

- [ ] Live secret key on Railway (`STRIPE_SECRET_KEY`, `sk_live_`).
- [ ] Live webhook destination at `https://ovoxi-website-production.up.railway.app/api/stripe/webhook` with `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `checkout.session.expired`, `charge.refunded`.
- [ ] Live signing secret on Railway (`STRIPE_WEBHOOK_SECRET`).
- [ ] One real low-value purchase, check delivery and email, then refund it in Stripe and check the download link stops working.

## Site and operations

- [ ] Confirm the canonical domain (`ovoxi.net` or `www.ovoxi.net`). Set `SYNC_SITE_URL` if it is `www`.
- [ ] Remove or flag the TEST sync tracks (TEST sync1, sync2, sync3, sync3b) before launch and before any AI export.
- [ ] Move Resend off the free plan before real volume.
- [ ] Turn on, in order: `SYNC_PUBLIC_PAGES_ENABLED=true`, `SYNC_LIBRARY_ENABLED=true`, `SYNC_CHECKOUT_ENABLED=true`.
- [ ] After launch, check the admin Orders list and the Resend dashboard daily for the first week.

## Never change after launch

- `SYNC_TOKEN_SECRET`: changing it breaks every issued download link.

## Optional housekeeping

- [ ] Remove `backend/test_acrcloud.py` from the repo.
- [ ] Tighten `vercel.json` CSP (default-src, img-src, media-src).
- [ ] Move temporary profile-photo uploads to `profile-uploads/` with an R2 lifecycle rule.
- [ ] Switch UploadPage to `SyncIntakeFields`.
- [ ] `npx vercel login` on the Mac so `npx vercel --prod` works.
