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

---

## OQ-2 — Stem R2 keys collide across submissions of the same artist + track name

**Found:** 2026-08-26, during PRD-01 Phase 1 benchmark planning.

The stem key convention omits the submission id:

```
catalog/{artist_slug}/{track_slug}/original/{submission_id}{ext}   ← unique
catalog/{artist_slug}/{track_slug}/mastered/{submission_id}{ext}   ← unique
catalog/{artist_slug}/{track_slug}/stems/{label}.mp3               ← NOT unique
```

If an artist uploads the same track title twice, the second submission's stems
**silently overwrite** the first's. Both MongoDB documents then carry `stem_paths`
pointing at the same objects, and nothing errors.

**Already happened, at least twice** in the current catalog:
- `teewhy / ceo` — submissions `5cdb3197…` and `8ccb8ab3…`
- `teewhy / Dirty Secret` — submissions `86677473…` and `4d3c5ca4…`

**Why it matters:** for a rights catalog, two distinct submissions resolving to one set of
audio files breaks the provenance chain. The record says these are separate ingestions
with separate rights attestations; the storage says they are the same bytes.

**Also note:** artist name and track name are free text from the upload form, so this is
reachable by an honest re-upload, not just a deliberate collision.

**Candidate fix:** include the submission id in the stems path, matching the other two
prefixes. This changes the key convention, so it needs a migration plan for existing
documents rather than a unilateral change — the current `stem_paths` values are the only
pointer legacy documents have.

**Do not fix during PRD-01 Phase 1–3.** Log it, finish the engine migration, then address
it deliberately. Rewriting key conventions mid-migration is how baselines get lost.

**Owner:** unassigned.

---

## OQ-3 — Model weight licensing

**Found:** PRD-01 §3 (original, 2026-08-26). Elevated to open-questions 2026-08-26.

Several UVR/RoFormer checkpoints distributed via `python-audio-separator` trace to
MUSDB18 or MUSDB18-HQ as training data, which carries a non-commercial research
licence. The specific checkpoint in use — `vocals_mel_band_roformer.ckpt` (Kimberley
Jensen edition) — has not been individually cleared for commercial use.

`htdemucs_ft.yaml` code is MIT; the licence attached to the released pretrained
weights must be read directly from `facebookresearch/demucs` and confirmed. Not yet
verified.

**Why it matters:** oVoxi's product is rights cleanliness. Running a commercial
catalog ingestion pipeline on a checkpoint with an unresolved non-commercial
restriction directly contradicts the product's value proposition, regardless of audio
quality.

**Blocks:** commercial catalog ingestion. Does not block the engine migration build
(Phases 1–4), but must be resolved before any artist audio is processed into the
production catalog under the new engine.

**To resolve:** IP counsel reviews the licences attached to both checkpoints and
confirms clearance for commercial use, or identifies a cleared alternative and
accepts the SDR delta.

**Owner:** unassigned. Needs Tyler → counsel.

---

## OQ-4 — Instrumental stem visibility in the artist Vault

**Found:** 2026-08-26, during /04 planning.  
**Resolved:** 2026-08-26. Decision: Tyler.

**Decision: surface instrumental in the artist Vault.**

Reasoning: artists receive mastering and stems as the consideration for non-exclusive
AI training rights. The instrumental is the most useful stem to a working musician
(backing track, sync pitching, live performance) and belongs in the artist-facing view.

**What VaultPage.jsx actually does (lines 162–167):**

```jsx
{t.stem_urls && Object.entries(t.stem_urls).map(([stem, url]) => (
  <a key={stem} href={url} target="_blank" rel="noopener noreferrer"
    className="...">
    {stem.charAt(0).toUpperCase() + stem.slice(1)} <ExternalLink size={10} />
  </a>
))}
```

VaultPage iterates `Object.entries(t.stem_urls)` dynamically. The display label is
`stem.charAt(0).toUpperCase() + stem.slice(1)`. There is no hardcoded key list.
Adding `instrumental` to `stem_paths` in the backend automatically surfaces it in
the Vault as "Instrumental". **Zero VaultPage.jsx code changes are required.**

**Authorised frontend scope for `/04` (expanded from PRD-01 §10.1):**

1. `frontend/src/pages/AdminPage.jsx` — add `instrumental` to `STEM_LABELS` at line 11.
2. `frontend/src/pages/VaultPage.jsx` — no code change needed; instrumental appears
   automatically. The authorisation is recorded here so this is a known, sanctioned
   behaviour rather than an accidental side-effect.

Everything else under `frontend/` stays untouched, `frontend/src/marketing/` in
particular. This authorisation does not extend to `UploadPage.jsx` or any other file.

---

## OQ-5 — Callback timeout and reconciliation under STEM_ENGINE=modal

**Found:** 2026-08-26, during /04 planning.

Under `STEM_ENGINE=modal`, `_process_stems` submits the separation job to Modal and
returns. The track sits in `status: "processing"` until Modal POSTs the callback to
`POST /api/internal/stems/callback`, which writes `status: "completed"` and
`stem_paths`. If the callback never arrives — Modal failure, network drop, bad
signature, Railway restart between submit and callback — the track hangs in
`processing` indefinitely. No timeout, no retry trigger, no alerting.

**Why it matters:** a hung track gives the artist no feedback and no recourse. The
admin page shows `Processing` forever. The only current recovery path is a manual
MongoDB write or a backfill run.

**Not built in /04** — the change from synchronous to async completion is the
regression risk in /04; adding reconciliation on top increases scope and surface area.
Addressed in a later phase.

**Candidate approaches (do not implement without planning):**
- A scheduled reconciliation job that finds documents in `processing` older than N
  minutes and either re-triggers Modal or marks them `failed` with a timeout error.
- A Modal-side deadline that fires the failure callback if separation exceeds a wall
  clock threshold.
- An admin-triggered re-queue route.

**Owner:** unassigned.

---

## OQ-6 — No catalog/ write guard in the production dispatch path

**Found:** 2026-08-26, during /04 planning.

`separate_stems` defaults `key_prefix` to `"catalog"` and the production dispatch in
`_process_stems` omits that argument:

```python
fn.spawn(submission_id, mastered_r2_key, _slugify(artist_name), _slugify(track_name))
# key_prefix uses default → "catalog"
# stem_prefix → "catalog/{artist_slug}/{track_slug}/stems"
```

There is no server-side guard that validates the resulting prefix before R2 writes. If
`artist_slug` or `track_slug` is empty, blank, or collides with another submission,
the worker writes to a wrong or shared path under `catalog/` without any rejection.

The guard that prevents erroneous writes exists only in `run_stem_benchmark.py` and
blocks the benchmark script from writing *into* `catalog/` — not the reverse.

Combined with OQ-2 (stem keys omit the submission id; two uploads of the same artist +
track title silently overwrite each other's stems — already happened twice), this is a
live overwrite path with no runtime defence.

**This preserves existing behaviour, not introduces new risk.** The LALAL path in
`_process_stems` has the same exposure: it writes to
`catalog/{safe_artist}/{safe_track}/stems/{label}.mp3` with no guard either.

**Not fixed in /04.** Fixing it correctly requires addressing OQ-2 first (include
`submission_id` in the stem key prefix) and then adding input validation in
`_process_stems` before the dispatch. Both are deferred.

**Owner:** unassigned.
