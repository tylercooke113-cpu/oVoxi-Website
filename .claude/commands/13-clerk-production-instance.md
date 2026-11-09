---
description: "Close OQ-8: migrate Clerk from the development instance to a production instance on ovoxi.net. Spans Vercel, Railway, Clerk and Google Cloud — read the ordering section before touching anything."
---

Follow `CLAUDE.md`. Plan before you code — show me the approach and the file list, wait
for approval, then implement. **Do not touch `frontend/src/marketing/`.**

This is the highest-risk change in the repo so far. It is the only one that can break
authentication *and* the backend API at the same time, across three deploy platforms that
do not deploy together. Read all of it before proposing a plan.

---

## Why

`frontend/src/index.js:7` hardcodes `pk_test_Y3J1Y2lhbC1maWxseS00Ny5jbGVyay5hY2NvdW50cy5kZXYk`
— a Clerk **development** instance serving the live site. Logged as **OQ-8**.

Verified limitations, from Clerk's own documentation:

- **Capped at 100 users, and user data cannot be transferred between instances.**
- Social connections use **shared OAuth credentials** — the Google consent screen shows
  Clerk's application, not oVoxi.
- The account portal runs on `accounts.dev`, not our domain. **This is the leading
  suspect for the post-sign-in redirect landing on `/` rather than `/vault`.**
- Sessions are passed via a `__clerk_db_jwt` querystring parameter rather than HttpOnly
  cookies. A session token in a URL is a token in history, referrers and logs.
- Clerk states development instances have "a more relaxed security posture and are not
  suitable for production workloads."

Production instances are included on the free Hobby plan. **There is no plan change and
no payment.** This is configuration, not billing.

## Migration scope — confirmed 2026-09-03

The development instance holds **test accounts only**. There is no user migration, no
`clerk_user_id` remapping in MongoDB, and no artist communication. A brief auth outage
during cutover is acceptable. **Confirm this is still true before starting** — if real
artists have signed up since, stop and re-plan.

---

## The two failures that will not announce themselves

**1. `CLERK_JWKS_URL` on Railway.** `backend/server.py:104` reads it, and
`verify_clerk_token` validates every bearer token against it. It currently points at the
dev instance. If the frontend moves to production and this does not, **every
authenticated route fails** — `/api/vault/tracks`, `/api/upload/presign`,
`/api/upload/complete`, the appeal routes. It will not look like an auth error. It will
look like an empty vault. `CLERK_SECRET_KEY` (server.py:105) needs the production
`sk_live_` value in the same pass.

**2. The CSP in `vercel.json`.** It allowlists `https://*.clerk.accounts.dev`,
`https://clerk.com`, `https://*.clerk.com`, `https://api.clerk.com`. A production
instance serves from **`clerk.ovoxi.net`** — our own subdomain, covered by none of those.
The browser blocks it silently. `CLAUDE.md` §4 already warns: any new external origin
"requires a `vercel.json` edit or it will be blocked in production and work fine locally."

Both must be handled *before* the frontend key flips.

---

## Order of operations — this is the part that matters

Vercel and Railway deploy independently. There is no atomic cutover. Do it in this order:

**Phase 1 — build the production instance (zero impact on the live site)**

1. Clerk Dashboard → the existing application → activate the **Production** environment.
2. Add `ovoxi.net` as the production domain. Clerk emits CNAME records (typically
   `clerk`, `accounts`, `clkmail`, and two DKIM records).
3. Add those records wherever DNS for `ovoxi.net` is managed.

   **DNS facts, verified 2026-09-03:** the apex A record resolves to `76.76.21.21`
   (Vercel) and the nameservers are `ns-cloud-b1`–`b4.googledomains.com`. That
   nameserver pattern is shared by **Google Cloud DNS** and by domains migrated from
   Google Domains to **Squarespace**, which kept the Google hostnames — so it does not
   by itself identify the panel. Check `account.squarespace.com` → Domains → DNS
   Settings first, then `console.cloud.google.com` → Network Services → Cloud DNS.
   Whichever shows an editable record list for `ovoxi.net` is the one. The records are
   identical either way.

   Do not touch the existing apex A record — it points at Vercel and serves the site.
   The Clerk records are new CNAMEs on subdomains and do not collide with it.

   Wait for Clerk to report the domain verified before continuing.
4. Create oVoxi's own Google OAuth credentials in Google Cloud Console and add them to
   the Clerk production instance. The shared dev credentials do not carry over.
5. In the production instance, set the same redirect config as the dev one:
   after-sign-in `/vault`, after-sign-up `/vault`.

**Phase 2 — make the app tolerate both instances (additive, safe to ship alone)**

6. `vercel.json`: **add** `https://clerk.ovoxi.net` and `https://*.ovoxi.net` to
   `script-src`, `script-src-elem` and `connect-src`. Do **not** remove the
   `accounts.dev` entries yet — keeping both means this commit cannot break the running
   site. They come out in a separate cleanup commit once production is proven.
7. `frontend/src/index.js`: replace the hardcoded constant with
   `process.env.REACT_APP_CLERK_PUBLISHABLE_KEY`. **Fail loudly** if it is missing —
   throw at module load rather than rendering a broken `<ClerkProvider>`. A silent
   `undefined` here is a white screen with no console clue.

   Note: CRA bakes `REACT_APP_*` at **build** time. Setting it in Vercel has no effect
   until the next deployment. This is the same trap documented for
   `REACT_APP_NEW_MARKETING`.

**Phase 3 — the cutover (brief auth outage, acceptable with test accounts only)**

8. Railway: set `CLERK_JWKS_URL` and `CLERK_SECRET_KEY` to the production values.
   Auth breaks here for anyone holding a dev-instance token. Expected.
9. Vercel: set `REACT_APP_CLERK_PUBLISHABLE_KEY` to the `pk_live_` value on
   **Production and Preview**. Redeploy — the variable does nothing until you do.
10. Vercel: **delete `VITE_CLERK_PUBLISHABLE_KEY`.** It is inert — this is a CRA/craco
    build and only `REACT_APP_*` reaches the bundle. Documented in OQ-8. Removing it
    stops the next person assuming it does something.

**Never dump the full Railway environment.** Read single variables or use the dashboard.
`STEM_WEBHOOK_SECRET` was burned that way once already.

---

## Rollback

Keep the dev instance alive and untouched throughout. If production misbehaves, revert
by setting the three env vars back to their dev values and redeploying — Vercel for the
frontend, Railway for the backend. Because Phase 2 leaves both origins in the CSP, no
`vercel.json` revert is needed. **Do not delete the development instance** until
production has run clean for a week.

---

## GATE

In a fresh incognito window, on the live site:

1. Sign up with a new email → lands on `/vault`.
2. Sign in with Google → **the consent screen says oVoxi, not Clerk** → lands on `/vault`.
3. The email verification link, opened in a new tab → lands on `/vault`.
4. From the vault, upload a real track → `/api/upload/presign` and `/api/upload/complete`
   both return 200. **This is the JWKS check.** An empty vault or a 401 here means
   Railway is still on the dev instance.
5. Browser console and network tab: no CSP violations, no requests to `accounts.dev`.
6. Confirm the session cookie is `__client` (HttpOnly) and that no `__clerk_db_jwt`
   appears in any URL.

Report the results as a table. If gate 2 still lands on `/` after all of this, the
account-portal theory was wrong and the cause is elsewhere — say so plainly rather than
patching around it.
