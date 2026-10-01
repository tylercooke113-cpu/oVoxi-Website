# PRD-03: Sync Marketplace

**Status:** Draft for approval, 2026-09-26. All product decisions made. Phase 0 findings applied. Not committed.
**Depends on:** Phase 0 discovery report, D8 file exception, final grant and license text (Phase 6 go-live only).
**Code location:** new UI in `frontend/src/sync/`. Changes to `/upload`, `/vault`, `/admin` limited to the D8 file list.

---

## 1. Goal

Artists opt each upload into AI training, sync placements, or both. Every artist gets a public sync profile. Creators and sync buyers get a library modeled on Epidemic Sound's interaction patterns (filter rail, waveform rows, one-click preview, license button on every row) in oVoxi's own visual identity, where they can filter, preview and license a track in about 60 seconds.

## 2. Out of scope for v1

- Subscriptions ($12/month, $39/month) and genre packs
- Clean versions and 15/30/60 second cutdowns
- Buyer accounts (guest checkout only)
- Artist revenue share and automated payouts (manual payouts from the order record)
- Co-writer confirmation by email (splits are uploader-attested, Option A)
- CWR export
- Text search in the library
- Sitemap entries for artist and track pages
- Final grant and license text (placeholders until counsel)
- Cover art, artist ISRC entry, artist-set pricing
- Admin approve or reject actions for tracks (clearance is automatic)
- Backfill or migration of existing submissions (they lack consent and are excluded everywhere)
- Resolving fingerprint NEEDS_DOCS and SCAN_ERROR tracks (OQ-12, separate PRD)

## 3. Core rules

**3.1 Two independent axes.** Clearance status is a legal fact (Cleared, Needs docs, Conflict). Usage consent is the artist's choice (AI training, sync). They are stored separately and never merged into one field.

**3.2 Listing rule.** A track appears in the library, on the artist page and at its share link only when all of these hold:
- `sync_status == cleared`
- `consent.sync == true`
- Content ID answer is "No"
- `on_sync_profile == true`
- the track is not delisted by an admin

**3.3 AI export rule.** Any AI dataset export filters on `consent.ai_training == true`. A sync-only track must never appear in an AI delivery.

**3.4 Consent can change after upload.** Either consent can be added or removed from the Vault. Every change is a new consent event; nothing is overwritten.
- Removing sync delists the track for future sales. Licenses already sold stay valid.
- Removing AI training excludes the track from future AI exports. Deliveries already made are not recalled.
- A track with both consents removed stays in the Vault and is used for nothing.

**3.5 Consent is enforced server-side at upload.** Presign rejects with 422 if neither consent is true, so no audio reaches R2 without consent. The disabled button in the UI is convenience only.

**3.6 Fingerprint match detail is database-only.** No API returns ACRCloud match detail (matched title, artist, label, ISRC, acrid, confidence, raw code): not the Vault, not the admin panel, not any public endpoint. It is visible only in MongoDB. Artists with a CONFLICT track see "this recording appears to match existing copyrighted material" and the File Appeal link. The fingerprint status itself may appear in the admin panel.

## 4. Artist flows

### 4.1 Upload form

Always shown:
- Checkbox: "Use this upload for AI training"
- Checkbox: "Use this upload for sync placements"
- At least one required. Upload button disabled until one is checked.
- Genre: the existing top-level `genre` field, already a fixed select validated server-side against `VALID_GENRES` (Hip-Hop, R&B, Afrobeats, Trap, Soul, Pop, Electronic, Latin, Reggaeton, Afropop, Other). No change.
- Mood (one to three, fixed list, Appendix A)
- Vocals or instrumental
- BPM (a number) or "I'm unsure", and key (one of the 24 major and minor keys) or "I'm unsure". The artist's answer is the source of truth; detection cross-checks it (4.4).
- **Splits (check 1, Option A).** Uses the PRD-02 rights model: three lists (writers, publishers, master owners), 1 to 4 parties each, each list summing to exactly 100% (stored as basis points). Every party has a legal name. Role, PRO and IPI are optional. Two shortcuts: "I own 100% of the writing, publishing and master" is expanded server-side into one self row per list using the artist's legal name, and "I self-publish" fills the publishers list. Plus an attestation checkbox.

Shown only when sync is checked:
- **Samples (check 3).** Fully original / cleared sample / royalty-free loop whose license allows sync, plus attestation.
- **Distributor and Content ID (check 4).** Distributor name. "Is this song registered in YouTube Content ID?" Yes / No / Not sure.
- **PRO (check 5).** PRO name and IPI number, or "Not affiliated".

### 4.2 Changing consent from the Vault

- **Add sync:** an AI-only track shows "Add to sync library". It opens the sync-only questions from 4.1, writes a `grant` event with `source: vault`, and sends the track through the clearance evaluator. When it reaches Cleared it is added to the profile automatically.
- **Remove sync:** confirmation dialog stating that sold licenses stay valid. Writes a `withdraw` event and delists the track.
- **Add or remove AI training:** a toggle with a confirmation dialog. Writes a `grant` or `withdraw` event.
- Tracks uploaded before Phase 1 have no usage choices, splits, moods, BPM or key. The Vault shows them with downloads only and the note "Uploaded before usage options. Re-upload to add it to AI training or sync." No backfill.

### 4.3 Vault: Sync Profile tab

Available to every artist.
- **Empty state:** blank profile with "Submit your music to your sync library."
- **Profile editor:** display name, photo *(Phase 4b)*, bio (500 characters), location (80 characters), Spotify artist URL, Instagram URL. Published immediately on save.
- **Slug:** generated from display name on first save, unique, lowercase. Artist cannot change it in v1 (shared links would break); admin can.
- **Sync tracks list:** every sync-consented track with its state: Live, Needs docs (with the missing item named), Conflict, Processing. Each live track has a copy-link button for its share page.
- "Live" is shown for cleared sync tracks from Phase 4a, before the public library launches.

The tab's components live in `frontend/src/sync/`. `VaultPage.jsx` only mounts the tab, which keeps the D8 exception small.

### 4.4 BPM and key

The artist supplies BPM and key at upload, or ticks "I'm unsure". After processing, the pipeline detects both and reconciles:

| Artist | Detector | Result |
|---|---|---|
| BPM value | within ±1.5% | Artist value, confirmed |
| BPM value | half or double (within ±1.5%) | Artist value, confirmed |
| BPM value | any other value | Held: artist confirms |
| Key | same key | Artist value, confirmed |
| Key | same root, opposite mode, or the relative key | Artist value, confirmed |
| Key | any other key | Held: artist confirms |
| I'm unsure | a value | Detected value, held: artist confirms |
| a value | detection failed | Artist value, confirmed |
| I'm unsure | detection failed | Held: artist enters it |

A held value fails check 6 until the artist confirms or edits it in the Vault (Phase 4). Confirming or editing sets the source to `artist`. Detected values are stored separately and never overwrite the artist's answer.

Detection runs in the Modal stem worker after separation, on the mastered file. BPM uses librosa's onset and beat analysis (ISC license). Key uses Krumhansl-Schmuckler profile matching, written in-house. Essentia (AGPL), madmom (non-commercial model weights) and aubio (GPL) were rejected on license grounds. Tempo is measured from beat-to-beat spacing and snapped to the nearest whole BPM when within 0.2. If detection fails the job still completes and reconciliation follows the table above.

## 5. Clearance evaluator

Runs automatically when a track finishes processing and again whenever any input changes (intake answers, splits, metadata edits, admin action).

| # | Check | Pass when |
|---|---|---|
| 1 | Splits | Writers, publishers and master owners each sum to exactly 10000 basis points, 1 to 4 parties per list, attestation recorded (`rights.attested_at`) |
| 2 | Fingerprint | Persisted `fingerprint_result` is CLEARED. CONFLICT sets Conflict. NEEDS_DOCS and SCAN_ERROR fail. |
| 3 | Samples | An option is selected and the attestation is recorded |
| 4 | Content ID | Answer is "No". "Yes" and "Not sure" fail with reason `content_id` |
| 5 | PRO | PRO and IPI present, or "Not affiliated" |
| 6 | Metadata | Genre, 1 to 3 moods, vocals/instrumental, BPM, key, duration present, and stems produced, and neither BPM nor key is awaiting artist confirmation |

Check 2 needs a new `fingerprint_result` field written at scan time, because the scan result in `status` is overwritten as processing continues.

**Status derivation:** any Conflict gives `conflict`; otherwise any failed or missing check gives `needs_docs`; all six passing gives `cleared`. On `cleared` with sync consent, set `on_sync_profile = true` and `sync_listed_at`.

The evaluator runs only for tracks with `consent.sync == true`. AI-only tracks keep `sync_status: null`. In Phase 3 it runs when processing completes and when the fingerprint scan stops a track. Later phases add the runs triggered by artist edits and admin actions.

## 6. Public surfaces

| Route | Purpose |
|---|---|
| `/sync` | The library |
| `/sync/track/:id` | Single track page, the artist's share link to buy |
| `/artist/:slug` | Public artist profile |
| `/sync/success` | Post-payment page |
| `/license/:token` | Buyer download page |

### 6.1 Library

- **Filters:** genre (multi-select), mood (multi-select), BPM range, vocals or instrumental, duration range.
- **Sort:** Popular (artist-level count of paid sync purchases, ties broken by newest), Newest.
- **Row:** play button, title, artist display name from the sync profile (falling back to the track's `artist_name`) linking to the profile, waveform, genre and mood tags, BPM, duration, License button.
- **Player:** one persistent player bar at the bottom of the page.
- **Search backend:** plain Mongo queries on compound indexes behind a small search-service module, so a move to Atlas Search or Typesense later changes one file.
- **Who can see it:** admins always. Everyone else only when `SYNC_LIBRARY_ENABLED=true`; otherwise "Page not found". This switch is separate from `SYNC_PUBLIC_PAGES_ENABLED`.
- **Filter logic:** options within genre, or within mood, match **any**. Different filters (genre, mood, BPM, vocals, length) must **all** match.
- **Default sort:** Newest until the first paid sync sale is recorded, then Popular. Popular = the artist's paid sync sales, then newest.
- **Filters live in the address bar** (e.g. `/sync?genre=R%26B&mood=Chill&bpm=80-100&sort=newest`), so a filtered view can be shared. Results load 25 at a time with Load more.

### 6.2 Artist page

Photo, display name, location, bio, Spotify and Instagram links, and the artist's listed tracks using the same row component as the library.

- **Who can see it:** the artist themselves and admins always. Everyone else only when public pages are switched on (`SYNC_PUBLIC_PAGES_ENABLED=true`) **and** the artist has at least one listed track; otherwise "Page not found".
- The artist viewing their own page sees an **Edit profile** button linking to the Vault's Sync Profile tab. With no listed tracks it reads: "No tracks listed yet. Add tracks to your sync profile in your Vault."
- While public pages are off, the owner and admins see a banner saying who can see the page.

### 6.3 Audio previews

- The pipeline produces a 320 kbps MP3 of the master at `catalog/{artist}/{track}/previews/{submission_id}.mp3`, plus precomputed waveform peaks (JSON) at `catalog/{artist}/{track}/previews/{submission_id}.waveform.json`. The MP3 is a playback derivative only, never licensed or delivered, so the WAV24 catalog rule in `stem_worker.py` still holds.
- No CSP change is needed: `vercel.json` restricts only scripts, styles and `connect-src`, so `<audio>` and `<img>` load from R2 signed links. The waveform JSON is fetched through the backend (`GET /api/sync/tracks/{id}/waveform`), not from R2. Photos and previews are served as short-lived signed links, because the R2 bucket has no public address.
- The waveform JSON is public.
- The MP3 is private. Each play calls the backend, which returns a presigned URL valid for 5 minutes. There is no download button, and the endpoint is rate limited.
- This stops link sharing and bulk scraping. It does not stop someone recording the audio. Accepted.
- How the waveform JSON is served publicly is decided in Phase 4 or 5. Phase 3 only produces it.

## 7. Purchase flow

### 7.1 Tiers (one-time, per track)

| Tier | Price | With stems (+22%, rounded to the nearest dollar) |
|---|---|---|
| Creator | $19 | $23 |
| Creator Pro | $49 | $60 |
| Business Social | $149 | $182 |

What each tier permits is defined by the license text, pending counsel. Prices are computed server-side only. The client never sends a price.

### 7.2 Steps

1. Buyer clicks License on a row or track page.
2. A modal asks for tier, stems add-on, name, company (optional), email, and acceptance of the license terms.
3. `POST /api/sync/checkout`: the server confirms the track is listable, computes the price, creates an order (`pending`) and a Stripe Checkout Session with the email prefilled and the order ID in metadata, then returns the Checkout URL.
4. Buyer pays on Stripe's hosted page (guest).
5. Stripe webhook `checkout.session.completed`: verify the signature, skip if the event ID was already processed, mark the order `paid`, generate the license PDF, store it privately in R2, create the download token, send the email, and mark the order `fulfilled`.
6. Stripe redirects to `/sync/success?session_id=...`. The page polls for order status and shows the download link as soon as the order is fulfilled, so the buyer never waits on email.

If the email fails, the order stays fulfilled, the success page still delivers, and an admin can resend.

Phase 6 details (decisions 24 to 30):
- Stripe Tax: every Checkout Session sets `automatic_tax` and requires a billing address. Tax is added on top of the list price. The order stores `price_cents` (license price, the artist earnings basis), `tax_cents` and `amount_total_cents` separately. Product tax code comes from `SYNC_STRIPE_TAX_CODE` (unset uses the account default).
- Webhook events handled: `checkout.session.completed` and `checkout.session.async_payment_succeeded` (fulfil only when `payment_status == "paid"`), `checkout.session.expired` (order `failed`), `charge.refunded`.
- The webhook responds immediately and fulfils in a background task. Each order transition is conditional on the prior status, so a repeated event is a no-op. An event ID is written to `stripe_events` only after it was handled successfully.
- Success page fallback: if the order is still `pending`, `GET /api/sync/orders/by-session/{session_id}` retrieves the session from Stripe and fulfils when it is paid.

### 7.3 Download page

`/license/:token` lists the license PDF, the 24-bit master WAV and, if purchased, the five stems (vocals, instrumental, drums, bass, other). Each click mints a short-lived presigned URL. The token is valid for 30 days with a maximum of 10 downloads per file, and an admin can reissue it.

The token is derived, not stored: `HMAC-SHA256(SYNC_TOKEN_SECRET, order_id + ":" + token_version)`, URL-safe encoded. Only its SHA-256 hash is stored, for lookup. The success page can rebuild the link on refresh, and a reissue increments `token_version`, which invalidates the old link (decision 26). Files are served individually; there is no zip in v1.

### 7.4 License PDF (ReportLab)

License ID, date, buyer name, company and email, track title, artist name, tier, price paid, stems included (yes or no), terms version, and the terms text (placeholder until counsel).

### 7.5 Refunds

Issued manually in the Stripe dashboard. Webhook `charge.refunded` sets the order to `refunded`, disables its download token, and decrements the artist's popularity count. Only a full refund does this; a partial refund is logged on the order and changes nothing else (decision 28).

## 8. Data model

### 8.1 Track document (new fields on `db.track_submissions`)

```
consent:   { ai_training: bool, sync: bool }
metadata:  { moods: [str], vocals: "vocal" | "instrumental",
             bpm, bpm_source: "artist" | "detected", bpm_detected, bpm_needs_confirmation: bool,
             key, key_source: "artist" | "detected", key_detected, key_needs_confirmation: bool,
             duration_s }
intake:    { samples: "original" | "cleared_sample" | "royalty_free_loop",
             samples_attested_at, distributor,
             content_id: "yes" | "no" | "not_sure",
             pro_not_affiliated: bool, pro_name, ipi }
consent_grant_version
fingerprint_result: "CLEARED" | "NEEDS_DOCS" | "CONFLICT" | "SCAN_ERROR"
rights:    { owns_everything: bool,
             writers: [party], publishers: [party], master_owners: [party],
             attested_at, attested_by_clerk_user_id }
           party = { legal_name, ipi_name_number, society, role, share_bp, is_self }
checks:    { splits, fingerprint, samples, content_id, pro, metadata }
           each { result: "pass" | "fail" | "pending", reason }
sync_status:      "cleared" | "needs_docs" | "conflict" | null
on_sync_profile:  bool
sync_listed_at, sync_delisted_by_admin: bool
preview_key, waveform_key
```

Unchanged: top-level `genre`, `track_name`, `artist_name`. The legacy fields `pro_registered`, `pro_org` and `pro_register_us` are left untouched and never read by sync: they default to false and empty because the frontend never sent them, so they do not represent an artist's answer.

### 8.2 `consent_events` (append-only; no update or delete path in application code)

```
{ user_id, track_id, scope: "ai_training" | "sync", action: "grant" | "withdraw",
  source: "upload" | "vault", grant_version, ip, created_at }
```

### 8.3 `sync_profiles`

```
{ user_id, slug, display_name, bio, location, spotify_url, instagram_url,
  photo_key, sales_count, hidden_by_admin, created_at, updated_at }
```

### 8.4 `orders`

```
{ order_id, license_id, track_id, artist_user_id, tier, include_stems,
  price_cents, tax_cents, amount_total_cents, currency,
  buyer_name, buyer_company, buyer_email,
  terms_version, stripe_session_id, stripe_payment_intent,
  status: "pending" | "paid" | "fulfilled" | "failed" | "refunded",
  download_token_hash, token_version, token_expires_at, download_counts,
  license_pdf_key, email_status: "sent" | "failed" | "skipped",
  refunds: [{ amount_cents, at }], test_mode: bool,
  created_at, paid_at, fulfilled_at, refunded_at }
```

The orders collection is the earnings record for manual payouts.

### 8.5 `stripe_events`

```
{ event_id, type, processed_at }
```

Used for webhook idempotency.

## 9. API (proposed; final names after Phase 0)

**Artist (Clerk auth)**
- Existing presign and complete: add consent, metadata, intake and rights
- `POST /api/vault/tracks/{id}/consent`: add or remove a consent (`scope`, `action`, and the sync intake when adding sync)
- `PATCH /api/vault/tracks/{id}/metadata`: correct BPM or key, edit genre or moods
- `GET` and `PUT /api/sync/profile`
- `POST /api/sync/profile/photo/presign` and `/complete`

**Public (rate limited)**
- `GET /api/sync/tracks`: filters, sort, cursor pagination
- `GET /api/sync/tracks/{id}`
- `POST /api/sync/tracks/{id}/preview`: returns a 5-minute preview URL
- `GET /api/sync/artists/{slug}`
- `POST /api/sync/checkout`: returns the Stripe Checkout URL; 403 while checkout is disabled (admins with a test key excepted)
- `GET /api/sync/orders/by-session/{session_id}`: status (`processing`, `ready`, `failed`, `refunded`) and download token only, no buyer details. While pending it asks Stripe directly, at most every 5 seconds per order
- `GET /api/sync/downloads/{token}`: file list with downloads remaining
- `POST /api/sync/downloads/{token}/{file}`: counts one download and returns a 5-minute signed attachment link (`file`: license, master, vocals, instrumental, drums, bass, other)

**Stripe**
- `POST /api/stripe/webhook`

**Admin (Clerk admin role)**
- `GET /api/admin/sync/orders`: filters `status`, `artist`, `date_from`, `date_to` (YYYY-MM-DD, UTC, end inclusive), `include_test` (default false); newest 500; never returns the token hash
- `GET /api/admin/sync/orders.csv`: same filters, payout export, formula-escaped cells
- `POST /api/admin/sync/orders/{id}/resend-email`, `POST /api/admin/sync/orders/{id}/reissue-link` (`send_email`): fulfilled orders only; logged in `admin_actions`
- Hide a profile's photo and bio
- Delist a track

## 10. Email

- A single `send_email()` module, so the provider is swappable in one file.
- v1 provider: Resend free plan (3,000 emails per month, 100 per day, one domain) for testing. Move to a paid plan or another provider before real volume.
- Sending domain must be verified with SPF and DKIM records on the DNS host for ovoxi.net.
- v1 emails: license delivery to the buyer, and a "your track is live in the sync library" notice to the artist (optional).
- As built (6c): sender `oVoxi Licenses <licenses@mail.ovoxi.net>` on the `mail.ovoxi.net` subdomain (verified in Resend; DNS at Squarespace), so the root domain's mailbox records are untouched. Send-only; Reply-To `tyler@ovoxi.net`. The license email attaches the certificate PDF and links to the download page; test orders are prefixed "[TEST]". Email failure never undoes delivery; the order records `email_status`, `email_id`, `email_error`. The artist notice is deferred.

## 11. Security requirements

- Public endpoints return an explicit field allowlist: no emails, Clerk IDs, intake answers, splits, IPI numbers or ACRCloud data.
- Profile photos: JPEG, PNG or WebP, 10 MB max. Re-encoded server-side (strips EXIF, including GPS location), resized to 800 and 200 pixel squares, written to a public path. The original is deleted.
- Profile links validated: Spotify must be an `open.spotify.com/artist/` URL, Instagram an `instagram.com/` URL.
- Stripe webhook signature verified. Event IDs deduplicated.
- Download tokens: 32 random bytes, only the hash stored.
- Masters and stems are never in a public path.
- Rate limits on preview, checkout, and download endpoints.
- Existing open item applies: slowapi limits are per process, so confirm the Railway replica count is 1.
- Profile photos are processed on Railway with Pillow in a background thread, with a size and pixel-count guard against oversized-image attacks (a recorded exception to CLAUDE.md rule 3).

## 12. Configuration

| Variable | Default |
|---|---|
| `SYNC_CHECKOUT_ENABLED` | `false` until license text exists. While false, only admins can check out, and only with an `sk_test_` key |
| `SYNC_DELIVER_STEMS` | `true` |
| `SYNC_STEMS_UPLIFT` | `0.22`, applied server-side and rounded to the nearest dollar |
| `SYNC_PRICE_CREATOR` | `1900` (cents) |
| `SYNC_PRICE_CREATOR_PRO` | `4900` |
| `SYNC_PRICE_BUSINESS_SOCIAL` | `14900` |
| `SYNC_PREVIEW_URL_TTL_SECONDS` | `300` |
| `SYNC_DOWNLOAD_TTL_DAYS` | `30` |
| `SYNC_DOWNLOAD_MAX_PER_FILE` | `10` |
| `SYNC_GRANT_VERSION` | `draft-0` |
| `SYNC_TERMS_VERSION` | `draft-0` |
| `SYNC_PUBLIC_PAGES_ENABLED` | `false` until counsel confirms the grant text covers public profiles |
| `SYNC_LIBRARY_ENABLED` | `false` until Tyler approves the library |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | test mode keys first |
| `SYNC_TOKEN_SECRET` | required for checkout; never change once orders exist (breaks issued links) |
| `SYNC_STRIPE_TAX_CODE` | unset (account default) until chosen with an accountant |
| `SYNC_SITE_URL` | `https://ovoxi.net`; base for Stripe success and cancel URLs, must be https |
| `RESEND_API_KEY`, `EMAIL_FROM`, `EMAIL_REPLY_TO` | unset means emails are skipped (delivery still works on the success page). Set: `oVoxi Licenses <licenses@mail.ovoxi.net>`, `tyler@ovoxi.net` |

## 13. Phases and gates

| Phase | Scope | Gate to start |
|---|---|---|
| 0 | Read-only discovery. D8 file list. BPM and key library license check. | Approval of this PRD |
| 1 | Upload: consent boxes, 422 enforcement, consent ledger, genre, mood, vocals, sync-only intake (checks 3 to 5) | Phase 0 report reviewed |
| 2 | Splits entry (Option A) | Phase 1 live |
| 3 | Pipeline: `fingerprint_result` and `duration_s` persisted, 320 kbps preview, waveform peaks, BPM and key detection, clearance evaluator | Phase 2 live |
| 4a | Vault: usage toggles with consent events, BPM/key confirm and edit, moods and genre edit, sync status; Sync Profile tab (text fields, sync tracks list); match detail removed from all APIs | Phase 3 live |
| 4b | Profile photo, public artist page, track share page, admin hide and delist | Phase 4a live |
| 5 | Library page with filters and sort | Cleared sync tracks exist |
| 6 | Checkout, webhook, license PDF, email, download page, order CSV | Stripe account and email domain ready. Live sales only after license text is final. |

Each phase ships and is verified in production before the next starts.

## 14. Risks

- **Fingerprint dead end (pre-existing, OQ-12).** Tracks scored NEEDS_DOCS or SCAN_ERROR stop before mastering, and no admin action can resolve an appeal. Those tracks can never reach Cleared.
- **Placeholder consent text.** Consents recorded under `grant_version: draft-0` may need to be re-collected once counsel writes the real grant. Real artist sync opt-ins should wait for the final text, or a re-consent step must be planned.
- **Stems (OQ-3).** Paid stem delivery is the commercial use that the unresolved model-weight licensing question affects. Checkout stays off until the license text is final, so OQ-3 should be answered by then.
- **Attested splits (Option A).** A false attestation passes check 1. The attestation wording and the artist's indemnity to oVoxi need counsel.
- **Preview capture.** A 320 kbps preview can be recorded. Accepted.
- **Free email tier.** The 100 per day cap and a newly verified domain may cause delays or spam placement. Mitigated by delivering downloads on the success page.
- **Immediate profile publishing.** Abuse is possible. Mitigated by admin hide.
- **BPM and key accuracy.** Detection will be wrong on some tracks. Mitigated by artist correction.

## 15. Decisions log

| # | Decision |
|---|---|
| 1 | Mood list approved (Appendix A) |
| 2 | Genres reuse the existing upload genre list |
| 3 | Consent can be added or removed in either direction after upload; removal affects future licensing only |
| 4 | "Not affiliated with a PRO" passes check 5 |
| 5 | Stems add-on is +22%, rounded to the nearest dollar |
| 6 | The public library at `/sync` stays hidden behind a flag until Tyler approves it. Upload form changes, the track share page and the public artist page ship live as their phases land. |
| 7 | Splits use the PRD-02 rights model (writers, publishers, master owners), required on every upload |
| 8 | IPI numbers are exactly 9 or 11 digits everywhere, including the sync intake |
| 9 | BPM detected with librosa, key with in-house profile matching; detection is non-fatal |
| 10 | Phase 3 file exception: `infra/modal/stem_worker.py`, new `infra/modal/audio_analysis.py`, new `backend/clearance.py`, plus pipeline and callback code in `server.py` |
| 11 | Artists supply BPM and key at upload on every upload, with "I'm unsure"; detection is a cross-check |
| 12 | Reconciliation per 4.4: artist wins on half/double tempo, same-root and relative keys; other disagreements and "unsure" are held for one artist confirmation |
| 13 | ACRCloud match detail is database-only: removed from the admin panel and every API (supersedes the old 3.6) |
| 14 | CONFLICT wording for artists stays "this recording appears to match existing copyrighted material" with the appeal link |
| 15 | Pre-Phase-1 tracks stay in the Vault without usage controls; no backfill |
| 16 | Phase 4a file exception: `VaultPage.jsx`, `AdminPage.jsx` (match detail removal only), new files in `frontend/src/sync/`, new `backend/sync_vault.py`, `consent_ledger.py`, and the vault and admin endpoints in `server.py` |
| 17 | Public artist and track pages are built now but gated by `SYNC_PUBLIC_PAGES_ENABLED`; admins and the owning artist can always see them |
| 18 | An artist page with no listed tracks is visible only to its owner and admins |
| 19 | Profile photos processed with Pillow on Railway (rule 3 exception) |
| 20 | Phase 4b file exception: `App.js` (two routes), `AdminPage.jsx` (sync controls), `backend/requirements.txt` (Pillow), plus new files in `frontend/src/sync/` and `backend/` |
| 21 | Library gated by its own switch, `SYNC_LIBRARY_ENABLED`; admins always see it |
| 22 | Default sort is Newest until the first sale, then Popular |
| 23 | Phase 5 file exception: `App.js` (one route), new `backend/sync_search.py`, the library endpoint in `server.py`, new files in `frontend/src/sync/` |
| 24 | Phase 6 split: 6a backend, 6b frontend (license modal, success page, download page), 6c email and admin orders. Email (6c) waits for Resend; buyers get files from the success page |
| 25 | While checkout is disabled, the License button stays "coming soon" for the public; admins can run test purchases with an `sk_test_` key only |
| 26 | Download token derived from `SYNC_TOKEN_SECRET` (7.3), replacing "store only the hash of a random token" so the success page survives a refresh |
| 27 | Prices sent inline to Stripe per session (no dashboard Products); the server config is the only price source |
| 28 | Only a full refund revokes a license |
| 29 | Stripe Tax on, tax exclusive, billing address required; tax code set with an accountant before launch |
| 30 | Stems delivered in test (`SYNC_DELIVER_STEMS=true`). The live value is a launch decision tied to OQ-3. Phase 6a file exception: `server.py` (endpoints), `backend/requirements.txt` (`stripe`, `reportlab`), new `backend/sync_orders.py`, `backend/license_pdf.py` and tests |
| 31 | Test-mode orders never change `sales_count`, so sandbox purchases do not affect Popular sort or the switch from Newest to Popular |
| 32 | License email sent from the `mail.ovoxi.net` subdomain, send-only, Reply-To tyler@ovoxi.net |
| 33 | The license email attaches the certificate PDF so the buyer keeps it after the download link expires |
| 34 | Admin order list and CSV hide test orders by default. CSV cells starting with = + - @ are prefixed with an apostrophe (formula injection). No artist share column until the sync revenue split is defined |
| 35 | Delivery emails use idempotency key `license-{order}-v{version}`; an admin resend uses a unique key per click (a reused key made Resend silently skip resends, fixed in 1a264ac) |
| 36 | Phase 6c file exception: new `backend/email_sender.py`, `backend/sync_emails.py`, admin order endpoints in `server.py`, new `frontend/src/sync/AdminOrdersSection.jsx`; `AdminPage.jsx` unchanged |

Open items depend on the Phase 0 report only.

---

## Appendix A: Mood list (approved)

Artists pick 1 to 3 per track.

| Mood | Typical buyer use |
|---|---|
| Uplifting | Brand ads, product launches |
| Happy | Lifestyle, food, travel |
| Hopeful | Nonprofit, personal stories |
| Confident | Fashion, sports, swagger edits |
| Energetic | Fitness, fast-cut action |
| Aggressive | Gaming, combat sports, trailers |
| Epic | Trailers, big reveals |
| Luxurious | Premium brands, cars, real estate |
| Gritty | Street, documentary, urban scenes |
| Chill | Vlogs, study, background |
| Dreamy | Fashion, travel, slow motion |
| Romantic | Weddings, couples |
| Sensual | Late night, beauty, R&B edits |
| Nostalgic | Throwbacks, memories |
| Sentimental | Family, tributes |
| Sad | Loss, reflection |
| Dark | Crime, thriller |
| Tense | Suspense, countdowns |
| Mysterious | Teasers, reveals |
| Playful | Kids, comedy, pets |
