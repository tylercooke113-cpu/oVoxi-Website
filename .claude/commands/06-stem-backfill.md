---
description: "Phase 4 · Admin route to reprocess submissions that failed under LALAL."
---

Follow `CLAUDE.md`. Plan before you code. Do not change status strings, `stem_paths` keys,
or R2 key conventions.

---

Per `docs/PRD-01-stem-splitter-migration.md` Phase 4.

Add an admin-only route `POST /api/admin/submissions/reprocess` that takes a list of
submission ids, verifies each is currently `failed`, and re-queues **the stem stage only**
— skipping the ACRCloud scan and the mastering step if a `mastered_r2_key` already exists
on the document.

Idempotent, rate-limited, gated by the existing `x-admin-password` header, and it must
refuse to run on more than 25 submissions per call.

Add a dry-run mode that reports what it would reprocess.
