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

There is **no root `package.json`** and **no git remote workflow assumptions** — build
each half from its own directory.

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
catalog/{slug_artist}/{slug_track}/mastered/{submission_id}{ext}
catalog/{slug_artist}/{slug_track}/stems/{vocals|drums|bass|other}.mp3
```

`_master_track` derives the mastered key by string-replacing `/original/` → `/mastered/`.
The Vault and Admin pages read `stem_paths` by those exact four keys.

### Status values — DO NOT CHANGE without updating all three pages

Happy path: `pending` → `uploaded` → `scanning` → `processing`(spurious) →
`mastering` → `processing` → `completed`. Plus `failed`, and the ACRCloud statuses
which are written straight through to the document: `CLEARED`, `NEEDS_DOCS`,
`CONFLICT`, `SCAN_ERROR` (emitted by `acrcloud_check.py`).

`processing` is written twice and does **not** exclusively mean "separating".

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

- Auth is **Clerk**, verified server-side in `verify_clerk_token` against `CLERK_JWKS_URL`.
- Admin routes use a shared `ADMIN_PASSWORD` header. This is weak; do not extend it to new privileged routes without flagging it.
- Rate limiting is `slowapi`, keyed on `get_real_client_ip` (X-Forwarded-For aware).
- `vercel.json` sets a **strict CSP**. `connect-src` allowlists only the Railway API and Clerk. **Any new external origin the browser must reach requires a `vercel.json` edit or it will be blocked in production and work fine locally.**
- Secrets live in Railway/Vercel env vars, not in the repo. `backend/.env` locally holds
  `MONGO_URL`, `DB_NAME`, the five `R2_*` values, ACRCloud credentials, and admin values.
- `STEM_ENGINE` does not exist in code yet; it is introduced in `/04` as the flag that
  selects between engines. It is a `/04` deliverable, not a current prerequisite.
- `.gitignore` ignores all `.env*`. Keep it that way.

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
