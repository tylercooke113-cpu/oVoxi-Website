---
description: "Phase 2 · Wire the Modal engine into the backend behind a flag. Additive only."
---

Follow `CLAUDE.md`. Plan before you code — show me the approach and the file list, wait
for approval, then implement. Do not change status strings, `stem_paths` keys, or R2 key
conventions. Do not touch `frontend/src/marketing/`.

---

Per `docs/PRD-01-stem-splitter-migration.md` Phase 2. **LALAL code stays in place this
session — additive only.**

1. Create `backend/stem_service.py` with a `StemSeparator` Protocol
   (`async separate(submission_id, mastered_r2_key, artist_name, track_name) -> None`) and
   a `ModalStemSeparator` implementation that invokes the deployed Modal function
   asynchronously and returns immediately.
2. In `backend/server.py`, add a `STEM_ENGINE` env var defaulting to `"lalal"`. In
   `_process_stems`, branch: `"lalal"` runs the existing block untouched, `"modal"` calls
   `stem_service` and returns, leaving status at `processing` for the callback to finish.
3. Add `POST /api/internal/stems/callback`:
   - read the raw body, verify the HMAC with `hmac.compare_digest`, 401 on mismatch or
     missing signature
   - on success set status `completed`, `stem_paths` (five keys, per PRD-01 §10.1) and
     `stem_schema_version: 2`
   - on failure set status `failed` and `error`
   - not behind Clerk, not behind the admin password, exempt from the Clerk dependency,
     and rate-limited
4. Add `modal` to `backend/requirements.txt`.

Do not change any status strings. Do not remove or redefine any existing `stem_paths` key
beyond the `other`→`instrumental` split specified in PRD-01 §10.1.

**Exactly one frontend change is permitted by this command:** add an `instrumental` entry
to the `STEM_LABELS` map at `frontend/src/pages/AdminPage.jsx:11`. That is the only place
in the frontend where stem names are hardcoded — both VaultPage and AdminPage otherwise
iterate `stem_urls` dynamically. If you believe any other frontend change is needed, stop
and tell me instead.

Also add `stem_schema_version: Optional[int] = None` to `TrackSubmission`. Legacy
documents are version 1 implicitly; do not backfill them.

Show me the diff for `_process_stems` before applying it.

---

**GATE:** deploy to Railway with `STEM_ENGINE=modal`, upload a real track through the live
UI, confirm it reaches `completed` with four playable stems in the Vault. Then `curl` the
callback route with no signature and with a bad signature — both must 401.
