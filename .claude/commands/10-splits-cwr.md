---
description: "Splits Phase 4 · CWR v2.1 generator, fixtures, and the admin export route."
---

Follow `CLAUDE.md`. Plan before you code. **If you cannot confirm a CWR field offset from
the source documents, say "I do not know" and leave a TODO rather than guessing** — a wrong
offset produces a file that is silently rejected by the PRO.

---

Per `docs/PRD-02-royalty-splits.md` section 7.

Create `backend/cwr/writer.py` containing a **pure function**: given a `TrackRights` plus
work metadata, return a CWR v2.1 revision 8 transmission as a string. No database access,
no I/O, no network inside it.

Emit `HDR / GRH / NWR / SPU / SPT / SWR / SWT / PWR / OWR / OPU / REC / ORN / GRT / TRL`
with correct fixed-width field offsets. Shares are in hundredths of a percent, which our
basis points map to directly.

**Master owners are NOT part of CWR** — export those separately as a JSON manifest
alongside the CWR file. Do not force them into CWR records.

Add `backend/tests/test_cwr.py` with fixture files: solo writer/publisher, a 3-writer split
with 2 publishers, and one uncontrolled co-writer. Compare generated output against
checked-in expected fixtures byte for byte.

Then add `POST /api/registrations/export` (admin-only) returning the generated file, and
`GET /api/registrations` for history.

Before writing: read the MLC CWR User Guide and the MusicMark CWR manual linked in the PRD
and confirm the field offsets from those documents.

---

**GATE:** validate the output against an independent CWR validator before believing it.
And confirm the business prerequisite in PRD-02 §7 — oVoxi needs a CISAC CWR Sender ID
before any of this can be transmitted to ASCAP.
