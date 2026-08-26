---
description: "Phase 0 · Capture LALAL baseline stems from R2 before anything is deleted."
---

Follow `CLAUDE.md`. Plan before you code — show me the approach and the file list, wait
for approval, then implement. Justify technical choices and name the alternatives you
rejected. If you do not know something, say "I do not know" rather than guessing. Do not
change status strings, `stem_paths` keys, or R2 key conventions. Do not touch
`frontend/src/marketing/` during platform work.

---

Per `docs/PRD-01-stem-splitter-migration.md` Phase 0.

Write a standalone script at `scripts/capture_stem_baseline.py` that connects to R2 with
the existing backend credentials and, for the 10 most recent submissions with status
`completed` and a non-empty `stem_paths`, copies their four stems to
`benchmark/lalal-baseline/{submission_id}/` along with the mastered source. Write a
`manifest.json` recording submission id, artist, track, and the source R2 keys.

This is a **read-only script against production data**. It must not write to R2 and must
not touch MongoDB except to read. Print what it *would* copy and require an explicit
`--confirm` flag before copying anything.

Do not modify `backend/server.py` in this session.

---

**GATE:** the baseline must exist on disk before `/05-stem-delete-lalal` is ever run.
Once LALAL is deleted these stems cannot be regenerated.
