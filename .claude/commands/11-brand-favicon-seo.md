---
description: "Fix the missing Google search favicon. Adds icon assets, head links, manifest, robots.txt, sitemap.xml and Organization JSON-LD. Frontend only."
---

Follow `CLAUDE.md`. Plan before you code — show me the approach and the file list, wait
for approval, then implement. **Do not touch `frontend/src/marketing/`** and do not touch
anything under `backend/`. This command is `frontend/public/` + `frontend/src/index.js`
head content + `vercel.json` only.

---

## Root cause — verified 2026-09-02, do not re-diagnose

`frontend/public/index.html` contains **no favicon reference of any kind**. There is no
`<link rel="icon">`, no `<link rel="apple-touch-icon">`, and no `manifest.json`.
`frontend/public/` holds exactly four files: `index.html`, `logo.png`, `og-image.svg`,
`.DS_Store`. There is no `favicon.ico` at the site root.

Googlebot-Image has nothing to fetch, so Google Search renders the default globe.

Per Google's favicon documentation the icon must be:
- referenced by `rel="icon"`, `rel="apple-touch-icon"`, or `rel="apple-touch-icon-precomposed"`
- square (1:1), at least 8×8px, **recommended larger than 48×48px**
- ICO, PNG, JPEG, GIF, BMP, PPM or TIFF
- crawlable by Googlebot-Image, with the home page crawlable by Googlebot

`logo.png` is **1088×687** — not square, and a thin-stroke wordmark that is illegible
below ~64px. It must not be used as the favicon source — that is what `public/brand/icon-source.png` is for.

### Three defects found in the same file, fix them in this pass

1. `og:image` and `twitter:image` both point at `https://ovoxi.net/og-image.png`, which
   **does not exist** — only `og-image.svg` is present. Every link preview is currently
   broken. (Most social crawlers do not render SVG OG images either.)
2. There is no `<link rel="canonical">`.
3. There is no `robots.txt` and no `sitemap.xml`. Absent a `robots.txt`, crawling is
   permitted by default, so this is not the cause of the missing favicon — but a sitemap
   is the cheapest way to prompt a re-crawl once the icon ships.

---

## Step 0 — the source icon (already in place)

The square source icon is committed at:

```
frontend/public/brand/icon-source.png
```

**1254×1254, 8-bit RGB, no alpha channel** — the "o" ring with the arc beneath it, in the
purple→blue brand gradient on a near-white ground. Verified 2026-09-02.

It was originally dropped at `frontend/build/logo-preview.png`. **`frontend/build/` is
gitignored and is wiped by every `npm run build`** — it was copied to `public/brand/`
for that reason. Use the `public/brand/` copy. Do not read from `build/`.

Two properties of this file drive Step 1:

- **No alpha.** The white ground is baked in, so the favicon renders as a white tile with
  the mark floating on it. That composites correctly on Google's white results page and
  is acceptable in a dark browser tab. Do not try to key out the white — the gradient
  strokes are anti-aliased against it and keying will fringe them.
- **Heavy padding.** The mark occupies roughly 62% of the width and 72% of the height.
  Downscaled straight to 16×16 the mark is only ~10px across. **Trim the uniform border
  and re-pad to about 8% before resizing** — `sharp().trim()` then `.extend()`. Compare
  a trimmed and an untrimmed 16×16 side by side before committing; if trimming makes the
  ring strokes alias into mush, keep more padding and tell me.

## Step 1 — derive the icon set

Write `frontend/scripts/gen-icons.mjs` as a **one-shot generator**, run it once, and
commit the outputs. Do not add an icon step to the build — `craco build` and the
`react-snap` postbuild stay untouched.

Use `sharp` and `png-to-ico` as `devDependencies` only.

Emit into `frontend/public/`:

| File | Size | Purpose |
|---|---|---|
| `favicon.ico` | 16 + 32 + 48 multi-res | root fallback; what most crawlers try first |
| `favicon-32.png` | 32×32 | browser tab |
| `favicon-96.png` | 96×96 | Google's preferred surface (>48px) |
| `apple-touch-icon.png` | 180×180 | iOS home screen, and a `rel` Google accepts |
| `icon-192.png` | 192×192 | manifest |
| `icon-512.png` | 512×512 | manifest / install prompt |
| `og-image.png` | 1200×630 | replaces the missing PNG the meta tags already point at |

`og-image.png` is a **new composition**, not a scaled icon: ink background, the wordmark
`logo.png` centred, generous margin. Do not delete `og-image.svg`.

## Step 2 — head links

Add to `frontend/public/index.html`, inside `<head>`:

```html
<link rel="icon" href="/favicon.ico" sizes="any" />
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png" />
<link rel="icon" type="image/png" sizes="96x96" href="/favicon-96.png" />
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png" />
<link rel="manifest" href="/site.webmanifest" />
<link rel="canonical" href="https://ovoxi.net/" />
```

Use **root-relative paths**, not `%PUBLIC_URL%`. The app is served from the domain root
and react-snap rewrites the file; root-relative is the form that survives both.

**The canonical host is the apex, `https://ovoxi.net` — decided 2026-09-02, do not
re-ask.** Vercel already has `ovoxi.net` as the primary domain with `www.ovoxi.net`
redirecting to it, so no Vercel or DNS change is needed. Use the apex, with no `www` and
no trailing path, in the canonical tag, the sitemap, `og:url`, `twitter:url`, both image
URLs, and the JSON-LD.

Note that `docs/open-questions.md` states the live site is `www.ovoxi.net`. That line is
**stale**. Correct it in the same commit.

## Step 3 — manifest and crawl files

`frontend/public/site.webmanifest`:

```json
{
  "name": "oVoxi",
  "short_name": "oVoxi",
  "icons": [
    { "src": "/icon-192.png", "type": "image/png", "sizes": "192x192" },
    { "src": "/icon-512.png", "type": "image/png", "sizes": "512x512" }
  ],
  "theme_color": "#0B0B0F",
  "background_color": "#FFFFFF",
  "display": "standalone",
  "start_url": "/"
}
```

`theme_color` is the site's dark chrome; `background_color` is white to match the icon's
own ground, so the install splash does not flash a dark field behind a white tile.

`frontend/public/robots.txt` — allow everything, point at the sitemap. Do **not** add
any `Disallow` that could touch `/favicon*`, `/*.png`, or `/`.

`frontend/public/sitemap.xml` — static list of the public routes only:
`/`, `/contact`, `/apply`, `/privacy`, `/terms`.
**Exclude `/vault`, `/upload`, `/admin`, `/login`, `/signup`, `/appeal/*`.**

## Step 4 — Organization structured data

The favicon and the knowledge-panel logo are two different mechanisms. The favicon is
the small icon beside the result; the knowledge-panel logo comes from `Organization`
structured data. Add a JSON-LD block to `index.html`:

```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "oVoxi",
  "url": "https://ovoxi.net/",
  "logo": "https://ovoxi.net/icon-512.png"
}
```

**CSP check:** `vercel.json` sets `script-src` and `script-src-elem` with `'unsafe-inline'`
present, so an inline `<script type="application/ld+json">` is permitted. Verify this in
the deployed response headers rather than assuming it — a blocked JSON-LD block fails
silently.

`vercel.json` has no `img-src` and no `default-src`, so image loading is unrestricted and
needs no edit for this work. Do not add a `default-src` in this command — doing so would
retroactively constrain Clerk and the Railway API.

---

## GATE — do not report this done until all five pass

1. `cd frontend && npm run build`, then confirm the built `build/index.html` **still
   carries every icon link**. react-snap runs at postbuild only when
   `REACT_APP_NEW_MARKETING=true`; run the build both ways and diff the `<head>`.
   A link that survives the plain build but is stripped by react-snap is the failure
   mode to catch here.
2. Every emitted file loads at its own URL on the deploy preview and returns
   `200 image/png` (or `image/x-icon`) — not the SPA HTML fallback. A 200 that returns
   HTML is the classic SPA-rewrite trap and will silently fail Google's fetch.
3. `curl -sI https://<host>/favicon.ico` returns 200. Same for `/robots.txt`,
   `/sitemap.xml`, `/site.webmanifest`.
4. Paste the URL into Slack or a draft email — the preview card renders with the new
   `og-image.png`.
5. Google Rich Results Test on the home page parses the `Organization` block with no
   errors.

## Post-deploy, manual — Tyler, not the agent

- Google Search Console → verify the property → **URL Inspection on the home page →
  Request Indexing**.
- Submit `sitemap.xml` in Search Console.
- **Expect days to weeks, not hours.** Google's own documentation says crawling "can take
  anywhere from several days to several weeks", and the favicon is refreshed on Google's
  schedule, not on deploy. Do not treat a same-day check as a failed fix.
