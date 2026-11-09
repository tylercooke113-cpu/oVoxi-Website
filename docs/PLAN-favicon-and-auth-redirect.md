# Build plan — Google favicon + post-sign-in vault redirect

**Created:** 2026-09-02 · **Status:** ready to execute · **Scope:** frontend only, no backend changes

Two Claude Code commands live in the repo:

- `.claude/commands/11-brand-favicon-seo.md`
- `.claude/commands/12-auth-vault-redirect.md`

Run them **separately**, in that order. Per `CLAUDE.md` rule 5, they touch different
surfaces and do not belong in one commit.

---

## Problem 1 — no logo beside the oVoxi result in Google

### Root cause (verified, not inferred)

`frontend/public/index.html` has **no favicon reference at all** — no `<link rel="icon">`,
no `apple-touch-icon`, no manifest. `frontend/public/` contains only `index.html`,
`logo.png`, `og-image.svg`. There is no `favicon.ico` at the site root. Googlebot-Image
has nothing to fetch, so Search falls back to the default globe.

Google's requirements: the icon must be square (1:1), at least 8×8 and **recommended
above 48×48**, in a supported raster format, referenced via `rel="icon"` or
`rel="apple-touch-icon"`, and crawlable.

`logo.png` is 1088×687 — a wide, thin-stroke wordmark on transparency. It fails the
square requirement and is illegible below ~64px, so it is not the source.

**The square source icon is in place** at `frontend/public/brand/icon-source.png` —
1254×1254, 8-bit RGB, no alpha: the "o" ring with the arc beneath, purple→blue gradient
on a near-white ground. It was originally dropped at `frontend/build/logo-preview.png`;
`build/` is gitignored and wiped by every `npm run build`, so it was copied out.

One caveat carried into the command: the mark occupies only ~62% of the frame, so the
generator must trim the uniform border and re-pad to ~8% before downscaling, or the
16×16 favicon renders a ~10px mark.

### Three defects found alongside it, fixed in the same pass

1. `og:image` and `twitter:image` point at `/og-image.png`, which **does not exist** —
   only `og-image.svg` is present. Every link preview is currently broken.
2. No `<link rel="canonical">`.
3. No `robots.txt`, no `sitemap.xml`.

### Canonical host — resolved 2026-09-02

**Apex, `https://ovoxi.net`.** Vercel already has it as the primary domain with
`www.ovoxi.net` redirecting to it, so no Vercel or DNS work is required — only the
canonical tag, sitemap and JSON-LD need to say apex.

Chosen because the codebase already declares apex in four places (`og:url`,
`twitter:url`, `og:image`, and `content.js` `domain`), so apex is the choice that costs
zero meta-tag edits. The www counterargument — apex-scoped cookies reaching future
subdomains like `api.` or `app.` — is real but mild: Clerk scopes its own session
cookies, and the API lives on Railway, not a subdomain.

`docs/open-questions.md` says the live site is `www.ovoxi.net`. **That line is stale and
should be corrected.**

### Expectation setting

Google re-crawls on its own schedule. Its documentation says crawling "can take anywhere
from several days to several weeks." A same-day check showing no icon is **not** a failed
fix. Request Indexing in Search Console to prompt it.

---

## Problem 2 — sign-in returns artists to the landing page instead of `/vault`

### What is verified

`LoginPage.jsx:14` uses `afterSignInUrl` and `SignUpPage.jsx:14` uses `afterSignUpUrl`.
Clerk's documentation states these props are **deprecated**, replaced by
`forceRedirectUrl` / `fallbackRedirectUrl` and the `<ClerkProvider>`-level
`signInForceRedirectUrl` / `signUpForceRedirectUrl`. The installed
`@clerk/clerk-react@5.61.8` ships all six — confirmed by grepping `dist`. This is not a
version gap.

`frontend/src/index.js` passes `<ClerkProvider>` **only** `publishableKey` — no
`signInUrl`, no `signUpUrl`, no redirect props. Anything the component props miss falls
through to Clerk Dashboard defaults, which default to `/`.

`VaultPage.jsx:96` correctly guards on `isLoaded` before `isSignedIn`, so a hydration
race is ruled out.

### What is not verified — the open question

The live site runs a Clerk **development** instance
(`pk_test_…crucial-filly-47.clerk.accounts.dev`), already logged as **OQ-8**. Dev
instances route OAuth and email-link verification through the `accounts.dev` account
portal, which returns users to the Dashboard-configured URL. If that is `/`, no component
prop can rescue those flows.

**Two candidate causes, distinguishable by which flow breaks.** Decision taken: land the
code fix first, then run an isolation matrix across seven flows (email/password, OAuth,
verification link, already-signed-in, sign-out). If email/password reaches `/vault` but
OAuth does not, the dev instance is confirmed as the remaining cause — and that escalates
to standing up a production Clerk instance with DNS on the apex domain, which is
explicitly **out of scope** for this command.

### The layer the agent cannot reach

Clerk Dashboard → `crucial-filly-47` → **Paths** must be set to sign-in `/login`,
sign-up `/signup`, after-sign-in `/vault`, after-sign-up `/vault`. This is Tyler's manual
step, and on a development instance it is the setting that actually governs the portal
round-trip. If only one item on this page gets done, it is this one.

### Accepted trade-off

`forceRedirectUrl` overrides `redirect_url`, so a logged-out deep link to `/upload` will
land on `/vault`. That costs nothing today: both `UploadPage.jsx:47` and
`VaultPage.jsx:97` bounce with `<Navigate replace>`, which preserves no return URL, so no
`redirect_url` exists anywhere in the app. Adding deep-link return later means switching
to `fallbackRedirectUrl` **and** teaching the guards to pass `redirect_url` — doing one
without the other silently reintroduces this bug.

---

## Deployment note

`CLAUDE.md` §1 still warns that Vercel deploys from `feat/marketing-revamp`. That is
**stale** — `docs/HANDOFF.md` records the repoint to `main` on 2026-08-27, verified
against deployed commit `6427258`. Work merged to `main` now reaches production. Worth
correcting in `CLAUDE.md` on the next docs pass.
