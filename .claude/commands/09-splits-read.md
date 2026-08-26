---
description: "Splits Phase 3 · Vault + Admin read surfaces and the revision route."
---

Follow `CLAUDE.md`. Plan before you code. Do not touch `frontend/src/marketing/`.

---

Per `docs/PRD-02-royalty-splits.md` section 6.

Add `rights` to the projections in `GET /api/vault/tracks` and `GET /api/submissions`. Add
`POST /api/rights/{submission_id}/revise` — Clerk-authed, appends a revision document
rather than mutating the original, per rule 7.

Frontend: a read-only rights summary card on `VaultPage` per track, and a rights review
column plus a "disputed" flag on `AdminPage`.

**Existing submissions have no `rights` field.** Every one of these surfaces must render
correctly when `rights` is null. Verify that explicitly, don't assume it.
