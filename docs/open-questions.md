# Open questions

Parked items that are not blocking current work but must not be lost.

## OQ-1 — A Tupac recording is in the catalog with status `completed`

**Found:** 2026-08-26, during the PRD-01 Phase 0 baseline dry run.

A submission for artist `tupac`, track `hit em up`, is stored with
`status: "completed"` — meaning it either passed the ACRCloud gate as `CLEARED`
or predates that gate.

**Why it matters:** "Hit 'Em Up" is among the most heavily fingerprinted commercial
recordings in existence. If `acrcloud_check.py` returned `CLEARED` for it, that is a
false negative in the system whose sole purpose is preventing oVoxi from ingesting
recordings it has no rights to. For a company selling rights cleanliness, a
demonstrable false negative in the clearance gate is a material risk.

**Not yet determined** (do not assume):
- Whether the submission predates `acrcloud_check.py` (file dated 2026-06-30).
- Whether the status was set manually.
- Whether ACRCloud genuinely returned no match.

**To resolve:** read the submission document and check for `raw_code`, `confidence`,
`acrid`, `matched_title`, `matched_artist`. Absent → predates the gate, no issue.
Present and still `CLEARED` → investigate the confidence thresholds in
`acrcloud_check.py` (currently ≥90 CONFLICT / ≥70 NEEDS_DOCS / <70 CLEARED).

**Owner:** Tyler. Acknowledged and deferred 2026-08-26.

**Interim action taken:** excluded from the PRD-01 quality baseline. Third-party
commercial masters do not go in `benchmark/`, which is played back through
`benchmark/compare.html`.
