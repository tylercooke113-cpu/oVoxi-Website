---
description: "Phase 3 · DESTRUCTIVE. Delete the LALAL.AI integration. Requires 01 and 03 to have passed."
---

**STOP.** Before running this, confirm both are true:

- `benchmark/lalal-baseline/` exists and is populated (`/01-stem-baseline` was run).
- The A/B in `docs/benchmark-stem-quality.md` was reviewed and approved by a human
  (`/03-stem-benchmark`).

If either is false, abort and tell me. Once LALAL is gone the baseline cannot be
regenerated.

---

Per `docs/PRD-01-stem-splitter-migration.md` Phase 3. **Separate commit, deletion only.**

Remove from `backend/server.py`: `_lalal_upload`, `_lalal_split`, `LALAL_API_KEY`,
`LALAL_BASE` (L61–63), the `"lalal"` branch in `_process_stems` (L287–312), and the
`STEM_ENGINE` flag now that there is one engine.

**Also remove the spurious `status: "processing"` write at L271**, per PRD-01 §10.2. It is
immediately overwritten by `mastering` and makes the status meaningless for any future
polling UI. This is the only behavioural change permitted in this deletion commit. Remove LALAL mentions from `docs/marketing-revamp-blueprint.md`.

Then run `grep -ri lalal .` excluding `node_modules`, `.git` and `frontend/build`, and show
me the output. **It must be empty.**

Do not remove anything else. In particular leave the ACRCloud gate, the Matchering
mastering step, and every R2 key convention exactly as they are.

---

**GATE:** after deploy, remove `LALAL_API_KEY` from Railway. Upload one more real track.
