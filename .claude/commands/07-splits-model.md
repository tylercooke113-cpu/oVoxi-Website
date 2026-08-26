---
description: "Splits Phase 1 · RightsParty / TrackRights models, basis-point shares, validation + tests."
---

Follow `CLAUDE.md`. Plan before you code — show me the models before writing the
validators. If you do not know something, say "I do not know" rather than guessing.

---

Read `docs/PRD-02-royalty-splits.md`, sections 3 and 4, in full.

Implement in `backend/server.py`: `RightsParty` and `TrackRights` Pydantic models exactly
as specified, with shares stored as **integer basis points** (1..10000). Add
`rights: Optional[TrackRights] = None` to `TrackSubmission` — nullable, so existing
documents keep validating.

Implement every validation rule from section 4 as Pydantic validators, including the
`owns_everything` server-side expansion (rule 6): the flag must expand into one 10000-bp
self party on each of the three lists and then be validated normally. **It is a shortcut,
never a bypass.**

Add `backend/tests/test_rights.py` covering, at minimum:

- three writers at 33.34 / 33.33 / 33.33 summing exactly
- a side at 9999 rejected, with the side named and the delta reported
- a 5th party rejected
- a zero-share party rejected
- `owns_everything` producing three populated lists
- an existing submission document with no `rights` field still validating

No UI changes and no route changes in this session.

---

**GATE:** `pytest backend/tests/test_rights.py` green, and the existing suite still green.
