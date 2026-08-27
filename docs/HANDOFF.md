# Build handoff — stem engine migration

Last updated: 2026-08-26. Read this first, then `CLAUDE.md`, then the PRD you're working on.

---

## Where we are

**PRD-01: /04 is LIVE on Railway (`1e716bb` or later, verified 2026-08-27).
`STEM_ENGINE` is unset or `"lalal"` — production still routes to the cancelled vendor.
The only remaining step to activate the new engine is the flag.**

### How Railway's deployed commit was verified (no CLI, no dashboard, no login)

`POST /api/internal/stems/callback` was introduced *only* in `1e716bb`
(`git log -S "internal/stems/callback"` returns that commit alone; absent in `508f141`).
A plain GET to that path on production returns **405 Method Not Allowed** — the path is
registered — while a control GET to a nonexistent sibling path returns **404**.
Route present ⇒ `1e716bb` or later is running.

Reusable: to test whether any deployment contains a given commit, GET a route that
commit introduced. 405 = present, 404 = absent.

### ✅ NEW ENGINE LIVE IN PRODUCTION — 2026-08-27

First real production upload ("100 Racks") completed end to end under
`STEM_ENGINE=modal`. Mastered file and stems present in R2, track `completed` in Admin,
stems visible in the artist Vault. **The `/05` precondition is met.**

Two problems were found and fixed on the way, both configuration, neither code:

1. `MODAL_TOKEN_SECRET` in Railway held a value beginning `fe…` — not a Modal
   credential (Modal secrets begin `as-`). Backend failed at dispatch with
   "Token validation failed" and no Modal run appeared. Fixed by issuing a dedicated
   production token (`modal token new --profile railway --no-activate`).
   ⚠️ Whatever that `fe…` value actually was got transmitted to Modal as a rejected
   login. If it is a live credential elsewhere, rotate it.
2. `STEM_ENGINE` had never been set at all, so production was still routing to the
   cancelled LALAL vendor. See the 26 Aug failure analysis below.

**Still outstanding before this is fully done:** Vercel's production branch is still
`feat/marketing-revamp`, so `AdminPage.jsx`'s `instrumental` label has not shipped.
Admin will render the raw key `instrumental` rather than "Instrumental" until repointed.

### Stem storage format reversed to 24-bit WAV — 2026-08-27

`/03` accepted MP3 320. Overturned after the first production run, because LALAL's
legacy stems were already `pcm_s24le` WAV and lossy stems are the wrong product for a
training-data business. Full reasoning in `docs/benchmark-stem-quality.md`.

Schema versions are now:

| Version | Stems | Format |
|---|---|---|
| v1 | four (LALAL) | WAV `pcm_s24le` |
| v2 | five | MP3 320 |
| v3 | five | 24-bit WAV, `stem_format: "wav24"` on the document |

Legacy documents are **not** rewritten. `VaultPage` and `AdminPage` are format-agnostic
(they iterate `stem_urls` and presign whatever key is stored), so no frontend change is
required.

⚠️ **The Modal worker does not auto-deploy.** `modal deploy infra/modal/stem_worker.py`
is required or stems keep landing as MP3. `WORKER_VERSION` was bumped to `wav24-v1`
specifically so the deploy is verifiable — the first log line of any run prints it.

⚠️ `scripts/run_stem_benchmark.py` still hardcodes `.mp3` and will find nothing if
re-run against the current worker. Commented in place, not fixed.

### Callback contract VERIFIED end to end — 2026-08-27

`modal run infra/modal/preflight_callback.py` sends one HMAC-signed request with
`status: "ping"` from inside Modal, using the real `ovoxi-stem-secrets` values.
Result:

```
STEM_CALLBACK_URL : https://ovoxi-website-production.up.railway.app/api/internal/stems/callback
secret fingerprint: 0cbe929defb8   (length 64)
HTTP 400  {"detail":"Unknown status: 'ping'"}
```

A 400 is the pass condition: the signature was accepted, the body parsed, and the
status rejected before any write path. This simultaneously proves:

- `STEM_CALLBACK_URL` is the real Railway route, not the old webhook.site endpoint
- `STEM_WEBHOOK_SECRET` matches byte-for-byte between Modal and Railway (64 chars,
  consistent with `openssl rand -hex 32`)
- both sides agree on the HMAC serialization (`sort_keys=True`, `separators=(",",":")`,
  posted as `data=`, verified against raw bytes)
- Railway's running code has the callback route AND has the secret configured
  (a missing secret would have returned 500)

**The rotated secret is no longer unverified.** Re-run this script after any secret
rotation or callback-URL change — it is the cheapest possible regression test and
touches no data.

⚠️ Railway auto-deploys on push. The belief that `/04` was "committed but not deployed"
was wrong — the third time in this migration an auto-deploy assumption has been wrong.
Assume both platforms deploy on push unless proven otherwise.

Last updated 2026-08-27.

| Command | Status |
|---|---|
| `/00-audit` | ✅ Done. Findings folded into the PRDs as §10 amendments. |
| `/01-stem-baseline` | ✅ Done. LALAL stems captured to `benchmark/lalal-baseline/`. |
| `/02-stem-worker` | ✅ Done. Modal worker deployed, gate passed. |
| `/03-stem-benchmark` | ✅ Done. New engine accepted. `other` (htdemucs residual) selected. MP3 320. |
| `/04-stem-wire` | 🔶 Merged to `main` as `1e716bb`; `main` == `origin/main`. Never exercised in production. |
| `/05-stem-delete-lalal` | ⬜ Blocked until a real production upload reaches `completed` under `STEM_ENGINE=modal`, with five stems visible in the artist Vault and `instrumental` labelled correctly in Admin. Deleting LALAL is irreversible and `benchmark/lalal-baseline/` cannot be regenerated. |
| `/06-stem-backfill` | ⬜ |
| `/07`–`/10` (splits + CWR) | ⬜ Not started. |

**Measured Phase 1 gate results** (Modal L4, warm container) are recorded in
PRD-01 §11: mean ~131 s and ~$0.029 per track across three tracks. Gate threshold was
≤5 min and ≤$0.10. Passed.

---

## /03 decisions — made 2026-08-26

All three A/B calls made. Full notes and caveats in `docs/benchmark-stem-quality.md`
(four unique tracks, not five; pre-fix `other_subtract` comparisons void).

1. **Vocals:** New engine accepted.
2. **Residual:** `other_htdemucs` selected; `other_subtract` dropped (code path stays
   in the worker per CLAUDE.md rule 4; removal is a later commit).
3. **Format:** MP3 320 kbps; FLAC rejected.
4. **OQ-4 resolved:** Instrumental surfaces in the artist Vault. VaultPage.jsx iterates
   `stem_urls` dynamically — zero code changes needed there. AdminPage.jsx label change
   still required. Sanction recorded in `docs/open-questions.md`.

---

## Decisions already made — do not relitigate

- **Five stems, versioned schema** (PRD-01 §10.1). `other` = true residual, `instrumental` = full mix minus vocals (the old `other` meaning), `stem_schema_version: 2`. Legacy documents stay version 1 and are **not** rewritten.
- **Engine:** Mel-Band RoFormer (`vocals_mel_band_roformer.ckpt`) for vocals/instrumental, `htdemucs_ft.yaml` for drums/bass/other, via `python-audio-separator` on Modal L4.
- **Splits stored as integer basis points**, never floats (PRD-02 §3).
- **Explicit `legal_name` on every rights party** — `artist_name` is a stage name and must never be used silently for registration (PRD-02 §10.1).
- **`owns_everything` is a server-side expansion, never a validation bypass** (PRD-02 §4 rule 6).

---

## Resolved — the 2026-08-26 failed submission

A previously-cleared demo track was submitted on the evening of 26 Aug and came back
`failed` with `'NoneType' object has no attribute 'get'`. Mastering completed first.

**Root cause: the LALAL path ran, and LALAL is dead.** In `_lalal_split`
(`server.py:169–175`):

```python
data   = check.json()
result = data.get("result", {}).get(file_id, {})
state  = result.get("task", {}).get("state")
```

`data.get("result", {})` returns the default `{}` only when the key is *absent*. LALAL
returns the key present with a **null** value, so the expression evaluates to `None` and
the chained `.get(file_id)` raises exactly that `AttributeError`. Same shape if
`result[file_id]["task"]` is null.

**What this proves:** `STEM_ENGINE` is unset or `"lalal"` in Railway, so production is
still routing to a cancelled vendor. Every upload will fail this way until the flag is
switched.

**What this does NOT prove:** whether Railway is running `/04`. The LALAL branch is
byte-identical in the old and new code, so this failure is indistinguishable between
them. **Resolve the deployed commit before setting `STEM_ENGINE=modal`** — on a
pre-`/04` deployment the variable is simply ignored, the upload fails identically, and
the failure looks like a Modal problem when it is a deployment problem.

Ruled out: ACRCloud (a non-`CLEARED` scan writes the ACR status and returns, never
`failed`); the webhook secret (a mismatch 401s the callback and hangs the track in
`processing`, it cannot write `failed`); the Modal worker (never invoked).

**Lesson for future diagnosis:** `server.py:346` stores `error: str(exc)` on the
document and `AdminPage.jsx:228` renders it. Read that string first. It cost four
rounds of hypothesis-building to arrive at a fact the Admin page was already showing.

---

## Stem quality — do not regress

Tyler's assessment of the new-engine output on the 2026-08-26 run: **"very crispy and
perfect."** This is the quality bar. It is the product, not an implementation detail —
the catalog's value to an AI licensee is the stems.

What that quality is a function of, and must not be changed without a fresh A/B:

- `vocals_mel_band_roformer.ckpt` for vocals/instrumental; `htdemucs_ft.yaml` for
  drums/bass/other. **Specific checkpoints, not model families.**
- The `_pick` fix at `aa956d9`. The pre-fix build produced stems that sounded wrong
  because the wrong file was selected, not because the model was worse.
- MP3 320 as the stored format (FLAC rejected at `/03`).
- htdemucs resamples everything to 44.1 kHz. 48 kHz sources are downsampled.

**Threats to this quality bar, in order of likelihood:**

1. **OQ-3 (model weight licensing).** If MUSDB18-derived checkpoints cannot be used
   commercially, the replacement checkpoint changes the sound. This is the single
   largest risk to the quality Tyler just approved, and it is a legal question, not an
   engineering one.
2. **`/06-stem-backfill`** reprocessing existing catalog entries under different
   settings.
3. Any loosening of the dependency pins in PRD-01 §11 — a different `audio-separator`
   or `torch` version can change inference output.

Re-run the `/03` A/B against `benchmark/lalal-baseline/` before accepting any change to
the four bullets above.

---

## Standing constraints

- **Never write to `catalog/` from a benchmark.** The worker takes a `key_prefix`; benchmarks use `_benchmark/{submission_id}/` and there is a guard that refuses a resolved prefix starting with `catalog/`.
- **Do not run `/05` until `/01` and `/03` are both complete and approved.** Once LALAL is deleted the baseline cannot be regenerated.
- **Phase 2 is additive only.** The spurious `status: "processing"` write at server.py L271 gets removed in Phase 3, not before.
- **Two authorised frontend changes in `/04` (OQ-4 resolution, 2026-08-26):**
  (1) `AdminPage.jsx` — add `instrumental` to `STEM_LABELS` at line 11.
  (2) `VaultPage.jsx` — no code change needed; instrumental appears automatically
  because it iterates `stem_urls` dynamically. The authorisation is explicit so this
  is not mistaken for scope creep. Nothing else under `frontend/`.
- **Never touch `frontend/src/marketing/`** during platform work.

---

## Deployment blockers — must resolve before setting STEM_ENGINE=modal

**🔴 STEM_CALLBACK_URL is stale (live blocker).**
`ovoxi-stem-secrets` currently has `STEM_CALLBACK_URL` set to a `webhook.site` test URL
from Phase 1. Every production track dispatched to Modal will POST its callback there
instead of Railway. The track will hang in `processing` indefinitely with no error.

Fix before deploying:
```bash
modal secret create ovoxi-stem-secrets --force \
  R2_ENDPOINT="..." \
  R2_ACCESS_KEY_ID="..." \
  R2_SECRET_ACCESS_KEY="..." \
  R2_BUCKET_NAME="..." \
  STEM_WEBHOOK_SECRET="..." \
  STEM_CALLBACK_URL="https://ovoxi-website-production.up.railway.app/api/internal/stems/callback"
```

Verify the key is correct before flipping the switch — see `infra/modal/README.md` for
the inline verification command.

**Secrets status (as of 2026-08-26):**

- `STEM_CALLBACK_URL` — **WRONG VALUE in `ovoxi-stem-secrets`** (points at webhook.site). Must be corrected before `STEM_ENGINE=modal` is set. See above.
- `STEM_WEBHOOK_SECRET` — set in both `ovoxi-stem-secrets` and Railway. Value not
  verified by a live callback yet; the first production run is the verification. A mismatch
  fails silently and hangs tracks in `processing` forever.
- `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET` — set in Railway.
- `STEM_ENGINE` — introduced in `/04`. Set to `"modal"` in Railway only after the Modal
  worker is redeployed with `wire-v1` and `STEM_CALLBACK_URL` is corrected.

---

## Environment

- **Backend:** FastAPI on Railway (`ovoxi-website-production.up.railway.app`), CPU only.
- **Frontend:** React (CRA) on Vercel, react-snap prerender, strict CSP in `vercel.json`.
- **Worker:** Modal, workspace `tylercooke113-cpu`, app in `infra/modal/stem_worker.py`, L4 GPU, `retries=0`.
- **Storage:** Cloudflare R2. **DB:** MongoDB. **Auth:** Clerk.
- `backend/.env` now holds `MONGO_URL`, `DB_NAME` and the five `R2_*` values locally, in addition to ACRCloud and admin values.

### Load-bearing dependency pins

`audio-separator` does not install cleanly on a fresh Python 3.12 CUDA image. Five fixes
were required and are documented in PRD-01 §11 — `audioread` and `librosa==0.10.1`
declared explicitly, `torch==2.11.0`/`torchaudio==2.11.0`, `ffprobe` instead of
`torchaudio.info`, `_(other` prefix matching, and directory scanning instead of
constructed paths. **Do not loosen these pins.**

---

## Open questions (see `docs/open-questions.md`)

- **OQ-1** — a Tupac recording sits in the catalog with status `completed`, meaning it either passed the ACRCloud gate or predates it. Deferred by Tyler, acknowledged, not resolved. Excluded from the benchmark.
- **OQ-2** — stem R2 keys omit the submission id, so two uploads of the same artist + track title silently overwrite each other's stems. Already happened twice. **Do not fix during PRD-01.**
- **OQ-5** — under `STEM_ENGINE=modal`, if the callback never arrives the track hangs in `processing` indefinitely. No timeout, no retry trigger, no alerting. Not fixed in /04.
- **OQ-6** — no server-side guard on the catalog/ write path. A bad slug writes to a wrong path unchallenged. Preserves existing LALAL behaviour; deferred to after OQ-2 is fixed.

Also unresolved and blocking commercial catalog ingestion, not the build: **model weight
licensing** (PRD-01 §3). Several UVR/RoFormer checkpoints trace to MUSDB18, which carries
a non-commercial research licence. Needs IP counsel before production use.

And blocking PRD-02 Phase 5: oVoxi needs a **CISAC-assigned CWR Sender ID** to transmit
registrations to ASCAP. Status unknown.

---

## Next action

0. ~~Establish what commit Railway is running.~~ ✅ Done 2026-08-27 — `/04` is live.
1. Correct `STEM_CALLBACK_URL` in `ovoxi-stem-secrets` (see blocker above).
2. Deploy Modal worker: `modal deploy infra/modal/stem_worker.py` (picks up `wire-v1`).
3. Deploy backend to Railway (picks up callback route + `STEM_ENGINE` dispatch).
4. Repoint Vercel's production branch to `main`, then deploy frontend (picks up the
   `instrumental` label in AdminPage). Until repointed, nothing built on `main` ships.
5. Set `STEM_ENGINE=modal` in Railway env vars. Step 0 confirmed `/04` is live, so the
   variable **will** take effect. This is the switch that activates the new engine.
6. Upload a real track. Verify: track reaches `completed`; five stems visible in artist Vault; `instrumental` shows as "Instrumental" in Admin.
7. `/05-stem-delete-lalal` stays blocked until a real production upload reaches `completed` under `STEM_ENGINE=modal`, with five stems visible in the artist Vault and `instrumental` labelled correctly in Admin. Deleting LALAL is irreversible and `benchmark/lalal-baseline/` cannot be regenerated.
