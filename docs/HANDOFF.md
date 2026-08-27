# Build handoff — stem engine migration

Last updated: 2026-08-26. Read this first, then `CLAUDE.md`, then the PRD you're working on.

---

## Where we are

**PRD-01 (stem splitter migration): /04 code written. Not deployed. One pre-deployment blocker open.**

| Command | Status |
|---|---|
| `/00-audit` | ✅ Done. Findings folded into the PRDs as §10 amendments. |
| `/01-stem-baseline` | ✅ Done. LALAL stems captured to `benchmark/lalal-baseline/`. |
| `/02-stem-worker` | ✅ Done. Modal worker deployed, gate passed. |
| `/03-stem-benchmark` | ✅ Done. New engine accepted. `other` (htdemucs residual) selected. MP3 320. |
| `/04-stem-wire` | 🔶 Code committed to `feat/stem-engine-migration`. **Not deployed.** See blocker below. |
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

1. Correct `STEM_CALLBACK_URL` in `ovoxi-stem-secrets` (see blocker above).
2. Deploy Modal worker: `modal deploy infra/modal/stem_worker.py` (picks up `wire-v1`).
3. Deploy backend to Railway (picks up callback route + `STEM_ENGINE` dispatch).
4. Deploy frontend to Vercel (picks up `instrumental` label in AdminPage).
5. Set `STEM_ENGINE=modal` in Railway env vars.
6. Upload a real track. Verify: track reaches `completed`; five stems visible in artist Vault; `instrumental` shows as "Instrumental" in Admin.
7. `/05-stem-delete-lalal` stays blocked until a real production upload reaches `completed` under `STEM_ENGINE=modal`, with five stems visible in the artist Vault and `instrumental` labelled correctly in Admin. Deleting LALAL is irreversible and `benchmark/lalal-baseline/` cannot be regenerated.
