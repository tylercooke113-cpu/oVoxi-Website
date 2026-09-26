# CLAUDE.md — oVoxi Website / Platform

Read this before touching anything. It describes what exists, what is load-bearing,
and the rules for changing it.

---

## 1. What this repo is

`oVoxi-Website` is the artist-facing web app for oVoxi.ai. Artists sign in, upload a
track, the backend fingerprint-checks it, masters it, splits it into stems, and stores
the results in Cloudflare R2 for the training-rights catalog.

**It is a monorepo with two independently deployed halves:**

| Half | Path | Stack | Deployed to |
|---|---|---|---|
| Frontend | `frontend/` | React (CRA) + Tailwind + Radix/shadcn + Clerk + react-three-fiber, prerendered with react-snap | Vercel |
| Backend | `backend/` | FastAPI (Python 3.12) + Motor/MongoDB + boto3→R2 | Railway (`ovoxi-website-production.up.railway.app`) |

There is **no root `package.json`** — build each half from its own directory.

### Deployment topology — verified 2026-08-27

Both halves auto-deploy on push. Neither is manual, and a belief that "auto-deploy is
broken" has been wrong twice.

| Platform | Deploys from | Notes |
|---|---|---|
| Vercel (frontend) | ⚠️ **`feat/marketing-revamp`**, not `main` | Fires on every push; four unnoticed production deploys landed in one day. **Nothing built on `main` reaches the live site until this is repointed.** |
| Railway (backend) | assumed `main` — **verify against the deployed commit before trusting it** | |

`REACT_APP_NEW_MARKETING` (`frontend/src/App.js:20`) switches the `/` route between
`HomePage` and `MarketingPage` and hides the header. Nothing else reads it. Currently
`false` (Config type). The marketing revamp is **not** an unmerged side branch — it is
the base of the entire commit history at `75a1d94`, with every stem commit on top of it.
Do not attempt to remove it; the flag achieves the outcome without history surgery.

**Never dump the full Railway environment** (`railway variables` with no filter) into a
terminal or an agent transcript. `STEM_WEBHOOK_SECRET` was already burned once that way
and had to be rotated. Read single variables, or read them in the dashboard.

---

## 2. Backend map (`backend/`)

`server.py` is a ~940-line monolith. Everything lives in it. Key regions:

| Lines (approx.) | Region |
|---|---|
| 1–100 | imports, env loading, Mongo client, R2 client, Clerk JWT verify |
| 123–236 | helpers: `_slugify`, `_lalal_upload`, `_lalal_split`, `_download`, `_r2_get`, `_r2_put`, `_master_track` |
| 238–329 | `_process_stems` — **the entire audio pipeline** |
| 332–480 | Pydantic models |
| 482–935 | API routes under the `/api` prefix |

Supporting files:

- `acrcloud_check.py` — synchronous ACRCloud fingerprint scan, called via `asyncio.to_thread`. Returns `{"status": "CLEARED" | ...}`.
- `requirements.txt` — note `matchering` (mastering) and `pyacrcloud` are heavyweight.
- `Dockerfile` — `python:3.12-slim` + `ffmpeg`. **CPU only. There is no GPU on Railway.**
- `Procfile` — `uvicorn server:app`.

### The audio pipeline (`_process_stems`)

Triggered by `POST /api/upload/complete` via FastAPI `BackgroundTasks` — i.e. it runs
**in-process inside the web dyno**. Sequence:

1. status → `scanning` (L243); pull original from R2; ACRCloud scan.
2. If not `CLEARED`, write the ACR status and match metadata and **stop**.
3. status → `processing` (L271). **This write is spurious** — it is immediately superseded by `mastering` four lines later. It is undocumented, it makes `processing` mean two different things, and it should be deleted. Do not build logic on it.
4. status → `mastering` (L277); `_master_track` runs Matchering against `backend/reference/default.wav`, writes to the `/mastered/` R2 key.
5. status → `processing` (L282) with `mastered_r2_key`; separation begins.
6. status → `completed` (L316), with `stem_paths`.
7. Any exception → status `failed` (L324) with `error`.

### R2 key conventions — DO NOT CHANGE

```
catalog/{slug_artist}/{slug_track}/original/{submission_id}{ext}
catalog/{slug_artist}/{slug_track}/mastered/{submission_id}.wav
catalog/{slug_artist}/{slug_track}/stems/{vocals|instrumental|drums|bass|other}.wav
```

**The mastered key is always `.wav`** (fixed 2026-08-27). Matchering writes 24-bit
PCM WAV, so deriving the suffix from the source container produced `mastered/{id}.mp3`
files holding WAV bytes. Legacy documents keep their old keys — see OQ-7. Never rebuild
this key by string manipulation; read `mastered_r2_key` off the document.

**Stems are 24-bit PCM WAV since 2026-08-27, under `stem_schema_version: 3`.**
The `/03` A/B accepted MP3 320, but LALAL's legacy stems were already `pcm_s24le` WAV,
so MP3 left the catalog half lossless and half lossy — the wrong direction for a
training-data product. Schema versions are now: **v1** = four LALAL stems (WAV),
**v2** = five stems (MP3 320), **v3** = five stems (24-bit WAV). Documents from v3
onward also carry `stem_format`. Legacy documents are **not** rewritten.

**Five stems since `/04`, under `stem_schema_version: 2`.** `instrumental` is the full
mix minus vocals (what LALAL called `other`); `other` is now a true htdemucs residual.
Same key name, different content — see PRD-01 §10.1. Legacy documents stay at
version 1 and are **not** rewritten.

⚠️ Stem keys omit the submission id, so two uploads of the same artist + track title
overwrite each other. This is OQ-2, known, deliberately unfixed during PRD-01.

`_master_track` derives the mastered key by string-replacing `/original/` → `/mastered/`.
`AdminPage.jsx` maps the five keys via `STEM_LABELS`; `VaultPage.jsx` iterates
`stem_urls` dynamically and needs no change when the set grows.

### Status values — DO NOT CHANGE without updating all three pages

Happy path: `pending` → `uploaded` → `scanning` → `processing`(spurious) →
`mastering` → `processing` → `completed`. Plus `failed`, and the ACRCloud statuses
which are written straight through to the document: `CLEARED`, `NEEDS_DOCS`,
`CONFLICT`, `SCAN_ERROR` (emitted by `acrcloud_check.py`).

`processing` is written twice and does **not** exclusively mean "separating".

**Since `/04` there are two writers of `completed`.** Under `STEM_ENGINE=lalal` the
pipeline reaches `completed` in-process. Under `STEM_ENGINE=modal`, `_process_stems`
dispatches to Modal and returns with status left at `processing`; `completed` is written
later by `POST /api/internal/stems/callback` (`server.py` ~L966), guarded against
overwriting a terminal state. This is the first async completion in the pipeline — a
track can now be `processing` with no process working on it. There is no callback
timeout or reconciliation (OQ-5).

**`failed` is written in exactly one place**: the `except` wrapping all of
`_process_stems` (L343–346), which stores `error: str(exc)` on the document.
`AdminPage.jsx:228` renders that string. **Read it before diagnosing anything.** A
non-`CLEARED` ACRCloud scan does *not* produce `failed` — it writes the ACR status and
returns.

Coverage differs per page and this matters:
- `AdminPage.jsx` — all 11 statuses. The most complete handler.
- `VaultPage.jsx` — all except `uploaded`-vs-`processing` nuance; handles the ACR statuses.
- `UploadPage.jsx` — `STATUS_LABELS` covers only 5 and is **currently dead code**: the page sets `stage='done'` immediately after `upload/complete` and never polls. It becomes live the moment anything introduces progress polling.

These strings are mirrored in **three** frontend files. Changing one without the others
silently breaks the UI:

- `frontend/src/pages/UploadPage.jsx` (`STATUS_LABELS`)
- `frontend/src/pages/VaultPage.jsx`
- `frontend/src/pages/AdminPage.jsx`

---

## 3. Frontend map (`frontend/src/`)

- `pages/UploadPage.jsx` — three-step upload: `POST /api/upload/presign` → `PUT` direct to R2 → `POST /api/upload/complete`. Clerk token in the `Authorization` header on steps 1 and 3, **never** on the R2 PUT.
- `pages/VaultPage.jsx` — artist's own submissions (`GET /api/vault/tracks`, Clerk-authed).
- `pages/AdminPage.jsx` — all submissions/appeals, gated by the `x-admin-password` header.
- `marketing/` + `components/` — the 3D scroll marketing site (phases 4–8 in git history). **Do not touch this while doing platform work.** It is prerender-sensitive: `react-snap` runs at postbuild and there is a postbuild gate.
- `content.js` — marketing copy.

The API base URL is **hardcoded** in the page files as
`https://ovoxi-website-production.up.railway.app/api`. If you add a new page, follow the
same pattern rather than inventing an env var, unless you refactor all of them at once.

---

## 4. Security / config facts

### Authentication and roles

Auth is **Clerk**, verified server-side via PyJWT + `PyJWKClient` with a 1-hour in-process key
cache. `verify_clerk_token` validates `RS256`, checks `iss` == `CLERK_ISSUER`, and rejects
`azp` values outside `CLERK_AUTHORIZED_PARTIES`. Keys are fetched from `CLERK_JWKS_URL` on cache
miss only -- no live HTTP call on every request.

Roles live in `metadata.role` inside the Clerk session token:

| Role | Set by | Access |
|---|---|---|
| `"artist"` | Hand-set in Clerk dashboard (or `scripts/backfill_artist_roles.py`) | upload, vault |
| `"admin"` | Hand-set in Clerk dashboard | admin endpoints |

`require_artist = require_role("artist", "admin")`, `require_admin = require_role("admin")`.

**`ADMIN_PASSWORD` no longer exists.** Removed in B1 (2026-09-25). Admin access is exclusively
a Clerk JWT with `role="admin"`. Do not rebuild any shared-secret admin gate.

### Job queue and sweeper

`complete_upload` sets status `"uploaded"` and returns immediately. The audio pipeline runs in a
Mongo-backed worker loop started at app startup when `RUN_WORKER=true`.

- `_claim_next()` atomically transitions `"uploaded"` to `"scanning"`, records
  `claimed_by=INSTANCE_ID`, increments `attempts`, and returns the document (FIFO by
  `upload_date`, `ReturnDocument.AFTER`).
- `INSTANCE_ID` is a per-startup UUID; multiple replicas claim safely because the update is atomic.
- `WORKER_CONCURRENCY` loops (default 1) run per instance, polling every `WORKER_POLL_INTERVAL=5s`.
- **`_set_status(sid, status, extra=None, match=None) -> int`** is the single writer for all
  status transitions. Writes `status + status_updated_at`, truncates `error` at 500 chars,
  accepts an optional conditional filter for terminal-state guards. Returns `matched_count`.

`_run_sweeper()` fires every `SWEEPER_INTERVAL=120s`:

1. **Stale local** (`scanning`/`mastering`, no `modal_dispatched_at`, `status_updated_at` older
   than `STALE_LOCAL_MIN=30` min): `attempts >= 2` sets `failed`/`pipeline_timeout`; else resets
   to `"uploaded"`. The 30-minute threshold assumes the Modal path where `"mastering"` ends at
   dispatch; revisit before re-enabling LALAL.
2. **Stale Modal** (`processing` + `modal_dispatched_at` older than `STALE_MODAL_MIN=45` min):
   sets `failed`/`stem_callback_timeout`. Not re-dispatched. 45-minute threshold exceeds Modal's
   function timeout (1800 s). `$exists:true` guard excludes pre-E1 documents with no
   `modal_dispatched_at`.
3. **Abandoned uploads** (`pending`, `upload_date` older than `ABANDON_PENDING_HOURS=2`): sets
   `failed`/`abandoned_upload`. Does not delete the R2 object -- see OQ-10.
   Run `scripts/cleanup_orphaned_r2.py` (dry-run by default, `--apply` to delete).

All sweeper updates use conditional filters on `{id, status, status_updated_at}` so two replicas
cannot double-handle the same document.

### Stem callback signing

`POST /api/internal/stems/callback` uses timestamped HMAC:

1. Modal worker adds `"ts": int(time.time())` to the payload, serializes with
   `json.dumps(sort_keys=True)`, and signs with `STEM_WEBHOOK_SECRET` (SHA-256 HMAC, header
   `X-Ovoxi-Signature: sha256=<hex>`).
2. Railway checks: `isinstance(ts, (int, float))` then `abs(time.time() - ts) <= 300` then
   `hmac.compare_digest`.
3. Both write paths filter on `{"status": "processing"}` -- stale or duplicate callbacks are
   silently ignored.
4. `stem_paths` validation: must be a dict, keys in `KNOWN_STEM_NAMES`, values must contain
   `f"/{submission_id}/stems/"` under the submission's top-level prefix.

Run `modal run infra/modal/preflight_callback.py` before every Modal deploy to verify both sides
share the same secret. Expected result: HTTP 400 (signature valid; `"ping"` status is unknown).

### Upload limits and rate limiting

- `MAX_UPLOAD_BYTES` (env, default 150 MB / `157286400`): enforced at presign and re-checked via
  `head_object` in `complete_upload`; over-size objects are deleted and marked `failed`.
- `MAX_TRACK_SECONDS` (env, default `900`): enforced via `ffprobe` after download, before ACRCloud.
- Per-user quotas: `MAX_UPLOADS_PER_DAY=20`, `MAX_OPEN_SUBMISSIONS=5` (admins exempt).
- Rate limits: presign/complete 10/min, contact/artists 5/min, vault/tracks 30/min, admin 30/min.

### Client IP (Railway-specific)

Railway **overwrites** both `X-Real-IP` and `X-Forwarded-For` -- verified 2026-09-25 by forging
both headers from outside the network and observing Railway replaced them. The leftmost value in
`X-Forwarded-For` is the real client IP. `get_real_client_ip` prefers `X-Real-IP`, falls back to
leftmost XFF, falls back to `request.client.host`. `slowapi` storage is in-process per-replica;
valid only under the single-replica assumption -- flag it if the service ever scales beyond one.

### Other

- `STEM_ENGINE` defaults to `"modal"` (LALAL account cancelled). `STEM_ENGINE=lalal` re-enables
  a dead path; do not set without a live account.
- FastAPI docs disabled: `docs_url=None, redoc_url=None, openapi_url=None`.
- The global exception handler runs outside `CORSMiddleware` -- unhandled 500s carry no CORS
  headers; browsers see a CORS error, not a 500. Internal path names never reach the client.
- `vercel.json` sets a **strict CSP**. `connect-src` allowlists only the Railway API and Clerk.
  **Any new external origin the browser must reach requires a `vercel.json` edit or it will be
  blocked in production and work fine locally.**
- `backend/.env` locally holds `MONGO_URL`, `DB_NAME`, the five `R2_*` values, `CLERK_JWKS_URL`,
  `CLERK_ISSUER`, `CLERK_AUTHORIZED_PARTIES`, `STEM_WEBHOOK_SECRET`, and ACRCloud credentials.
  `.gitignore` ignores all `.env*`. Keep it that way.

### Env vars added and removed during security hardening (2026-09-22 to 2026-09-25)

**Railway (backend):**

| Variable | Batch | Change | Value source |
|---|---|---|---|
| `ADMIN_PASSWORD` | A/B | **Removed** | Was a random value; deleted after B1 verified |
| `CLERK_JWKS_URL` | B0 | Added | Clerk dashboard -> API Keys -> JWKS URL |
| `CLERK_ISSUER` | B0 | Added | Clerk dashboard -> API Keys -> Frontend API URL |
| `CLERK_AUTHORIZED_PARTIES` | B0 | Added | `https://ovoxi.net,https://www.ovoxi.net` |
| `UPLOADS_ENABLED` | B2 | Added | `true` (set `false` to pause uploads instantly) |
| `MAX_UPLOADS_PER_DAY` | B2 | Added | `20` |
| `MAX_OPEN_SUBMISSIONS` | B2 | Added | `5` |
| `MAX_UPLOAD_BYTES` | C1 | Added | `157286400` (150 MB) |
| `MAX_TRACK_SECONDS` | C1 | Added | `900` (15 min) |
| `DEBUG_IP_ENDPOINT` | D-2 | **Removed** | Temporary; deleted after IP behaviour verified |
| `RUN_WORKER` | E1 | Added | `true` |
| `WORKER_CONCURRENCY` | E1 | Added (optional) | `1` |
| `STALE_LOCAL_MIN` | E1 | Added (optional) | `30` |
| `STALE_MODAL_MIN` | E1 | Added (optional) | `45` |

**Vercel (frontend) -- current variables (no changes during this hardening work):**

| Variable | Notes |
|---|---|
| `REACT_APP_CLERK_PUBLISHABLE_KEY` | Added in OQ-8 (2026-09-03, commit `6c937f7`); Clerk dashboard -> API Keys -> Publishable key |
| `REACT_APP_NEW_MARKETING` | Pre-existing; see `frontend/src/App.js:20` for its effect on the `/` route |

**Modal (`ovoxi-stem-secrets`) -- no changes during this work:**

| Variable | Notes |
|---|---|
| `STEM_WEBHOOK_SECRET` | Shared with Railway; `preflight_callback.py` verifies both sides match |
| `STEM_CALLBACK_URL` | `https://ovoxi-website-production.up.railway.app/api/internal/stems/callback` |

---

## 5. Rules for changes

1. **Plan before code.** Post the approach and the file list, get approval, then implement.
2. **Never break the pipeline contract.** R2 key shapes, the four `stem_paths` keys, and the status strings are the integration surface between backend and three frontend pages.
3. **No new blocking work inside the web process.** `_process_stems` already abuses `BackgroundTasks`; do not add more CPU/GPU work to the Railway container. New heavy work goes to an external worker.
4. **Additive first, delete second.** When replacing a vendor, land the replacement behind a flag, prove it on real tracks, then remove the old path in a separate commit.
5. **Touch one half at a time.** A backend change and a marketing-3D change do not belong in the same commit.
6. **Say "I do not know."** If a licensing, royalty, or PRO question is not answered in `docs/`, do not invent an answer — surface it as an open question.

---

## 6. Active work

- `docs/PRD-01-stem-splitter-migration.md` — replace LALAL.AI with an open-source separator on serverless GPU.
- `docs/PRD-02-royalty-splits.md` — writer/publisher/master share capture with ASCAP-compatible CWR export.
- `docs/claude-code-prompts.md` — the ordered execution prompts for both.
- `docs/open-questions.md` — parked findings that must not be lost.
