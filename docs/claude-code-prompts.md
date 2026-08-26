# Claude Code execution prompts

Run these **in order**, one per session or at least one per commit. Each ends with a
verification gate. Do not paste two at once.

Before starting: `git checkout -b feat/stem-engine-migration` and confirm
`git status` is clean.

---

## Prompt 0 — orient (run once, in a fresh session)

```
Read CLAUDE.md, docs/PRD-01-stem-splitter-migration.md and
docs/PRD-02-royalty-splits.md in full before doing anything.

Then, without writing any code, report back:
1. Every line in this repo that references LALAL.AI, with file and line number.
2. Every place the four stem_paths keys are read.
3. Every place a submission status string appears, backend and frontend.
4. Anything in the PRDs that contradicts what the code actually does.

Do not change any files in this session.
```

---

## Prompt 1 — Phase 0, capture the baseline

```
Per PRD-01 Phase 0. Write a standalone script at
scripts/capture_stem_baseline.py that connects to R2 with the existing
backend credentials and, for the 10 most recent submissions with
status "completed" and a non-empty stem_paths, copies their four stems
to benchmark/lalal-baseline/{submission_id}/ along with the mastered
source. Write a manifest.json recording submission id, artist, track,
and the source R2 keys.

This is a read-only script against production data. It must not write
to R2 and must not touch MongoDB except to read. Print what it would
copy and require an explicit --confirm flag before copying.

Do not modify backend/server.py in this session.
```

**Gate:** the baseline exists on disk. Once LALAL is deleted these cannot be regenerated.

---

## Prompt 2 — Phase 1, the Modal worker, standalone

```
Per PRD-01 Phase 1. Create infra/modal/stem_worker.py — a Modal app,
nothing else changes in this session.

Requirements:
- Modal image based on a CUDA-capable Python 3.12 base, with ffmpeg and
  python-audio-separator installed.
- Pre-download BOTH model checkpoints at IMAGE BUILD time using
  run_function, not at request time. Cold-start weight downloads are
  the single thing that will make this too slow and too expensive.
- One @app.function(gpu="L4", timeout=1800) entrypoint:
  separate_stems(submission_id, mastered_r2_key, artist_slug, track_slug)
- Inside: download mastered audio from R2; run the Mel-Band RoFormer
  vocals model to get vocals + instrumental; run htdemucs_ft to get
  drums + bass; encode each to MP3; upload to
  catalog/{artist_slug}/{track_slug}/stems/{vocals|drums|bass|other}.mp3
  with content type audio/mpeg. "other" is the RoFormer instrumental
  minus drums and bass, or htdemucs's "other" — pick one, and write a
  comment explaining which and why.
- On success POST to the callback URL with an HMAC-SHA256 signature over
  the raw JSON body using STEM_WEBHOOK_SECRET, in an X-Ovoxi-Signature
  header. On failure POST a failure payload the same way. Never let a
  job end silently.
- R2 creds, the webhook secret and the callback URL come from Modal
  secrets, never from literals.
- Add infra/modal/README.md with the exact `modal secret create` and
  `modal deploy` commands, and the list of secret keys required.
- Add a scripts/test_modal_stems.py that invokes the function on one
  local file and prints wall-clock time.

Confirm the plan and the file list with me before writing anything.
```

**Gate:** run `scripts/test_modal_stems.py` on 3 real tracks. Record wall-clock and the
Modal-reported cost per track. If a track costs more than $0.10 or takes more than 5
minutes on L4, stop and re-plan before continuing.

---

## Prompt 3 — Phase 1, the quality A/B

```
Per PRD-01 Phase 1. Using benchmark/lalal-baseline/, run the Modal
worker over the same mastered sources and write the new stems to
benchmark/new-engine/{submission_id}/.

Then write docs/benchmark-stem-quality.md containing, per track and per
stem: file size, duration, peak and RMS level, and a spectral
comparison against the LALAL baseline. Include the objective numbers
you can actually compute — do not assert perceptual quality you have
not measured, and say so explicitly where a number is not available.

Generate a small static HTML page at benchmark/compare.html that plays
the LALAL and new stem side by side for each track so I can A/B them by
ear. Self-contained, no CDN.
```

**Gate: you listen to the A/B yourself.** Do not proceed to Prompt 4 until you are
satisfied the new stems are not a regression. This is the decision the PRD leaves to a
human on purpose.

---

## Prompt 4 — Phase 2, wire it in behind a flag

```
Per PRD-01 Phase 2. LALAL code stays in place this session — additive only.

1. Create backend/stem_service.py with a StemSeparator Protocol
   (async separate(submission_id, mastered_r2_key, artist_name,
   track_name) -> None) and a ModalStemSeparator implementation that
   invokes the deployed Modal function asynchronously and returns
   immediately.
2. In backend/server.py, add a STEM_ENGINE env var defaulting to
   "modal". In _process_stems, branch: "lalal" runs the existing block
   untouched, "modal" calls stem_service and returns, leaving status at
   "processing" for the callback to finish.
3. Add POST /api/internal/stems/callback:
   - read the raw body, verify the HMAC with hmac.compare_digest, 401
     on mismatch or missing signature
   - on success set status "completed" and stem_paths
   - on failure set status "failed" and error
   - not behind Clerk, not behind the admin password, exempt from the
     Clerk dependency, and rate-limited
4. Add `modal` to backend/requirements.txt.

Do not change any status strings. Do not change the stem_paths keys. Do
not change any file under frontend/. If you believe a frontend change
is needed, stop and tell me instead.

Show me the diff for _process_stems before applying it.
```

**Gate:** deploy to Railway with `STEM_ENGINE=modal`, upload a real track through the
live UI, confirm it reaches `completed` with four playable stems in the Vault. Then
`curl` the callback route with no signature and with a bad signature — both must 401.

---

## Prompt 5 — Phase 3, delete LALAL

```
Per PRD-01 Phase 3. Separate commit, deletion only.

Remove from backend/server.py: _lalal_upload, _lalal_split,
LALAL_API_KEY, LALAL_BASE, the "lalal" branch in _process_stems, and
the STEM_ENGINE flag now that there is one engine. Remove LALAL
mentions from docs/marketing-revamp-blueprint.md.

Then run `grep -ri lalal .` excluding node_modules, .git and
frontend/build, and show me the output. It must be empty.

Do not remove anything else. In particular leave the ACRCloud gate, the
Matchering mastering step, and every R2 key convention exactly as they
are.
```

**Gate:** after deploy, remove `LALAL_API_KEY` from Railway. Upload one more real track.

---

## Prompt 6 — Phase 4, backfill the failures

```
Per PRD-01 Phase 4. Add an admin-only route
POST /api/admin/submissions/reprocess that takes a list of submission
ids, verifies each is currently "failed", and re-queues the stem stage
only — skipping the ACRCloud scan and the mastering step if a
mastered_r2_key already exists on the document.

Idempotent, rate-limited, gated by the existing x-admin-password
header, and it must refuse to run on more than 25 submissions per call.

Add a dry-run mode that reports what it would reprocess.
```

---

## Prompt 7 — splits, Phase 1: model and validation

```
Read docs/PRD-02-royalty-splits.md, sections 3 and 4, in full.

Implement in backend/server.py: RightsParty and TrackRights Pydantic
models exactly as specified, with shares stored as integer basis points
(1..10000). Add `rights: Optional[TrackRights] = None` to
TrackSubmission — nullable, so existing documents keep validating.

Implement every validation rule from section 4 as Pydantic validators,
including the owns_everything server-side expansion (rule 6): the flag
must expand into one 10000-bp self party on each of the three lists and
then be validated normally. It is a shortcut, never a bypass.

Add backend/tests/test_rights.py covering, at minimum: three writers at
33.34/33.33/33.33 summing exactly; a side at 9999 rejected with the side
named and the delta reported; a 5th party rejected; a zero-share party
rejected; owns_everything producing three populated lists; an existing
submission document with no rights field still validating.

No UI changes and no route changes in this session. Show me the models
before writing the validators.
```

**Gate:** `pytest backend/tests/test_rights.py` green, and the existing test suite still green.

---

## Prompt 8 — splits, Phase 2: the UploadPage step

```
Per PRD-02 section 5. Convert frontend/src/pages/UploadPage.jsx into
two steps: the existing track form, then a rights step, then upload.
The file must not be uploaded until rights are attested.

Build the three grids (writers, publishers, master owners), each 1-4
rows with name / IPI / role / PRO / share %. Per side: a live running
total, the remaining percentage, and a "split evenly" button that
distributes basis points and gives the remainder to the first row so the
side always lands on exactly 100%.

The "I own 100% of the publishing and master of this recording"
checkbox collapses all three grids and pre-fills a self row in each;
unchecking restores what was previously typed.

Include the explanatory note that writer and publisher shares are each
100% of their own side. Artists get this wrong constantly and it is the
single most likely source of bad data.

Convert percentages to basis points with Math.round(pct * 100) on
submit and send `rights` in the presign request body.

Use only the existing shadcn primitives in frontend/src/components/ui/.
Do not add a form library — the page uses plain useState today. Do not
touch anything under frontend/src/marketing/ or the 3D scene.

Show me the component structure before writing it.
```

**Gate:** run it locally. Try to submit 33/33/33 — it must block at 99%. Try to add a 5th
writer — the UI must prevent it and, separately, `curl` the presign route with 5 writers
and confirm the server rejects it too.

---

## Prompt 9 — splits, Phase 3: read surfaces and revisions

```
Per PRD-02 section 6. Add `rights` to the projections in
GET /api/vault/tracks and GET /api/submissions. Add
POST /api/rights/{submission_id}/revise — Clerk-authed, appends a
revision document rather than mutating the original, per rule 7.

Frontend: a read-only rights summary card on VaultPage per track, and a
rights review column plus a "disputed" flag on AdminPage.

Existing submissions have no rights field. Every one of these surfaces
must render correctly when rights is null. Verify that explicitly.
```

---

## Prompt 10 — splits, Phase 4: the CWR generator

```
Per PRD-02 section 7. Create backend/cwr/writer.py containing a PURE
function: given a TrackRights plus work metadata, return a CWR v2.1
revision 8 transmission as a string. No database access, no I/O, no
network inside it.

Emit HDR / GRH / NWR / SPU / SPT / SWR / SWT / PWR / OWR / OPU / REC /
ORN / GRT / TRL with correct fixed-width field offsets. Shares are in
hundredths of a percent, which our basis points map to directly.

Master owners are NOT part of CWR — export those separately as a JSON
manifest alongside the CWR file. Do not force them into CWR records.

Add backend/tests/test_cwr.py with fixture files: solo writer/publisher,
a 3-writer split with 2 publishers, and one uncontrolled co-writer.
Compare generated output against checked-in expected fixtures byte for
byte.

Then add POST /api/registrations/export (admin-only) returning the
generated file, and GET /api/registrations for history.

Before writing: read the MLC CWR User Guide and the MusicMark CWR
manual linked in the PRD and confirm the field offsets from those
documents. If you cannot confirm an offset, say so and leave a TODO
rather than guessing — a wrong offset produces a file that is silently
rejected by the PRO.
```

**Gate:** validate the output against an independent CWR validator before believing it.
And confirm the business prerequisite in PRD-02 §7 — oVoxi needs a CISAC CWR Sender ID
before any of this can actually be transmitted to ASCAP.

---

## Standing rules to paste at the top of any session

```
Follow CLAUDE.md. Plan before you code — show me the approach and the
file list, wait for approval, then implement. Justify technical choices
and name the alternatives you rejected. If you do not know something,
say "I do not know" rather than guessing. Do not change status strings,
stem_paths keys, or R2 key conventions. Do not touch
frontend/src/marketing/ during platform work.
```
