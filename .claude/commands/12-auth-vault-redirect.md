---
description: "Send artists to /vault after sign-in and sign-up. Replaces deprecated Clerk props with force redirects, then isolates whether the dev instance (OQ-8) is still intercepting."
---

Follow `CLAUDE.md`. Plan before you code — show me the approach and the file list, wait
for approval, then implement. **Do not touch `frontend/src/marketing/`** and do not touch
anything under `backend/`. Auth is the product's front door; a broken Clerk is a broken
product.

---

## Symptom

An artist signs in or creates an account and lands back on the landing page instead of
their vault.

## What is verified, and what is not

**Verified from source:**

- `frontend/src/pages/LoginPage.jsx:14` uses `afterSignInUrl="/vault"`
- `frontend/src/pages/SignUpPage.jsx:14` uses `afterSignUpUrl="/vault"`
- Clerk's docs state plainly: *"The `afterSignIn`, `afterSignUp`, and `redirectUrl` props
  are deprecated."* They were replaced by `fallbackRedirectUrl` / `forceRedirectUrl` and
  the `<ClerkProvider>`-level `signInForceRedirectUrl` / `signUpForceRedirectUrl` /
  `signInFallbackRedirectUrl` / `signUpFallbackRedirectUrl`.
- The installed `@clerk/clerk-react@5.61.8` **does** ship all six of those props —
  confirmed by grepping `node_modules/@clerk/clerk-react/dist`. This is not a version-gap
  problem; the new API is available.
- `frontend/src/index.js` passes `<ClerkProvider>` **only** `publishableKey`. No
  `signInUrl`, no `signUpUrl`, no redirect props at all. Everything the component props
  do not cover falls through to Clerk Dashboard defaults, which default to `/`.
- `VaultPage.jsx:96` correctly guards on `isLoaded` before checking `isSignedIn`, so a
  hydration race is **not** the cause. Do not "fix" that guard.

**Not verified — this is the open question:**

The instance is `pk_test_…crucial-filly-47.clerk.accounts.dev`, a Clerk **development**
instance serving the live site (already logged as **OQ-8** in `docs/open-questions.md`).
Development instances route OAuth and email-link verification through the
`accounts.dev` account portal, and the portal returns the user to the instance's
Dashboard-configured URL. If that Dashboard setting is `/`, no component prop can save
that flow.

**So there are two candidate causes and they are distinguishable by which flow breaks.**
Land the code fix first, then run the isolation matrix. Do not assume, and do not
attempt the production-instance migration in this command.

## Clerk's precedence order — the reason force is the right tool

1. `forceRedirectUrl` — always wins, ignores where the user came from
2. `redirect_url` query parameter
3. `fallbackRedirectUrl` — used only when there is no `redirect_url`
4. default `/`

---

## Step 1 — `<ClerkProvider>` (`frontend/src/index.js`)

Add, alongside the existing `publishableKey`:

```jsx
signInUrl="/login"
signUpUrl="/signup"
signInForceRedirectUrl="/vault"
signUpForceRedirectUrl="/vault"
afterSignOutUrl="/"
```

This is the layer that catches flows which never re-mount `<SignIn>` — OAuth returns and
email-verification links land here, not on the component.

While you are in this file: **leave the hardcoded key alone.** Moving it to
`REACT_APP_CLERK_PUBLISHABLE_KEY` belongs with the OQ-8 migration, not here — changing
the key source and the redirect behaviour in the same commit makes a failure
undiagnosable.

## Step 2 — the two page components

`LoginPage.jsx` — replace `afterSignInUrl="/vault"` with:

```jsx
forceRedirectUrl="/vault"
signUpUrl="/signup"
```

`SignUpPage.jsx` — replace `afterSignUpUrl="/vault"` with:

```jsx
forceRedirectUrl="/vault"
signInUrl="/login"
```

Adding the cross-links means the "already have an account?" / "sign up" switch inside the
Clerk card stays inside our own routes instead of bouncing to the account portal.

**Trade-off, accepted deliberately:** `forceRedirectUrl` overrides `redirect_url`, so a
logged-out user who deep-links to `/upload` will land on `/vault` rather than back on
`/upload`. That costs nothing today — `UploadPage.jsx:47` and `VaultPage.jsx:97` both
bounce with `<Navigate replace>`, which preserves no return URL, so there is no
`redirect_url` in play anywhere in the app. If deep-link return is added later, switch
these two to `fallbackRedirectUrl` **and** make the guards pass a `redirect_url`. Doing
one without the other silently reintroduces this bug.

## Step 3 — Dashboard settings (Tyler, manual — the agent cannot do this)

Clerk Dashboard → the `crucial-filly-47` instance → **Paths**:

- Sign-in URL: `/login`
- Sign-up URL: `/signup`
- After sign-in URL: `/vault`
- After sign-up URL: `/vault`

This is the setting the account portal actually reads on a development instance. **If
only one thing in this document gets done, it is this one** — it is the layer the code
cannot reach.

---

## GATE — isolation matrix, run on the deploy preview in a fresh incognito window

Test each flow with a brand-new account, and record where each one lands:

| Flow | Expected |
|---|---|
| Email + password sign-up | `/vault` |
| Email + password sign-in | `/vault` |
| Google (or any OAuth) sign-up | `/vault` |
| Google (or any OAuth) sign-in | `/vault` |
| Email verification link, opened in a new tab | `/vault` |
| Already signed in, visit `/login` directly | `/vault` |
| Sign out | `/` |

**Read the result:**

- All seven pass → the deprecated props were the whole cause. Close it out.
- Email/password passes but OAuth or the verification link still lands on `/` → the
  development instance's account portal is intercepting. That is **OQ-8**, it is not
  fixable in this repo, and it escalates to standing up a production Clerk instance with
  DNS on the apex domain. Report that finding, update `docs/open-questions.md`, and stop.
  Do not start the migration inside this command.

Also confirm, in the browser console on the deploy preview, that **no Clerk deprecation
warning** for `afterSignInUrl` / `afterSignUpUrl` remains.

## Regression check

Sign in, then confirm the Vault still loads real tracks — `GET /api/vault/tracks` with
the Clerk bearer token must still return 200. A redirect change that breaks token
issuance would look like an empty vault, not like an auth error.
