---
description: "Phase 1 · Build the standalone Modal GPU stem-separation worker."
---

Follow `CLAUDE.md`. Plan before you code — show me the approach and the file list, wait
for approval, then implement. Justify technical choices and name the alternatives you
rejected. If you do not know something, say "I do not know" rather than guessing. Do not
change status strings, `stem_paths` keys, or R2 key conventions. Do not touch
`frontend/src/marketing/` during platform work.

---

Per `docs/PRD-01-stem-splitter-migration.md` Phase 1. Create `infra/modal/stem_worker.py`
— a Modal app. **Nothing else changes in this session.**

Requirements:

- Modal image based on a CUDA-capable Python 3.12 base, with `ffmpeg` and
  `python-audio-separator` installed.
- Pre-download BOTH model checkpoints at **image build time** using `run_function`, not at
  request time. Cold-start weight downloads are the single thing that will make this too
  slow and too expensive.
- One `@app.function(gpu="L4", timeout=1800)` entrypoint:
  `separate_stems(submission_id, mastered_r2_key, artist_slug, track_slug)`
- Inside: download mastered audio from R2; run the Mel-Band RoFormer vocals model to get
  vocals + instrumental; run `htdemucs_ft` to get drums + bass; encode each to MP3; upload
  to `catalog/{artist_slug}/{track_slug}/stems/{name}.mp3` with content type `audio/mpeg`.
- **Emit FIVE stems, per PRD-01 §10.1** — read that section before writing anything:
  - `vocals` — RoFormer isolated vocal
  - `instrumental` — RoFormer full mix minus vocals (this is what the legacy `other` key held)
  - `drums`, `bass` — htdemucs_ft
  - `other` — htdemucs_ft TRUE residual (not the instrumental; the two are different things)
- Set `stem_schema_version: 2` in the callback payload.
- On success POST to the callback URL with an HMAC-SHA256 signature over the raw JSON body
  using `STEM_WEBHOOK_SECRET`, in an `X-Ovoxi-Signature` header. On failure POST a failure
  payload the same way. **Never let a job end silently.**
- R2 credentials, the webhook secret and the callback URL come from Modal secrets, never
  from literals.
- Add `infra/modal/README.md` with the exact `modal secret create` and `modal deploy`
  commands, and the list of secret keys required.
- Add `scripts/test_modal_stems.py` that invokes the function on one local file and prints
  wall-clock time.

Confirm the plan and the file list with me before writing anything.

---

**GATE:** run `scripts/test_modal_stems.py` on 3 real tracks. Record wall-clock and the
Modal-reported cost per track. If a track costs more than $0.10 or takes more than 5
minutes on L4, stop and re-plan before continuing.
