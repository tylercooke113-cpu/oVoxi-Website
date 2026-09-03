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

---

## OQ-7 — Legacy mastered R2 keys carry the wrong extension

**Found:** 2026-08-27, during the first production run under `STEM_ENGINE=modal`.
Tyler noticed the mastered file was much larger than the original yet listed as `.mp3`.

**What happened:** `_master_track` derived the mastered key with
`r2_key.replace("/original/", "/mastered/")`, which preserves the *source* extension.
Matchering always writes 24-bit PCM WAV (`mg.pcm24`), so every mastered object uploaded
from a non-WAV source is a WAV file stored under a lying suffix — `mastered/{id}.mp3`
containing WAV bytes. The `Content-Type` header was always correct (`audio/wav`), which
is why downloads and playback never visibly broke.

**It propagated into the worker.** `infra/modal/stem_worker.py` reads
`src_ext = Path(mastered_r2_key).suffix` and writes the downloaded bytes to
`mastered{src_ext}`. So the separator was handed WAV bytes in a file named
`mastered.mp3`. It worked only because `audio-separator`/librosa sniff content rather
than trusting the extension — a stricter decode path or a future version breaks it.

**Fixed forward** (2026-08-27, `backend/server.py` `_master_track`): the key is now
derived with `PurePosixPath(...).with_suffix(".wav")`. Verified against `.mp3`, `.wav`,
`.flac`, `.m4a`, no-extension, and paths containing dots in earlier segments.

**Still open — the backfill.** Documents created before this fix keep `.mp3`/`.flac`
mastered keys pointing at WAV content. Every consumer reads `mastered_r2_key` off the
document rather than reconstructing it, so nothing is broken today and old and new
coexist safely. The catalog is simply mixed.

**To resolve:** decide whether to rewrite legacy keys (copy object to the `.wav` key,
update the document, delete the old object) or leave them. Not to be attempted during
PRD-01 — it is a data migration touching production objects, and it is not urgent.

**Owner:** unassigned. Deferred.

---

## Note — duplicate objects under original/ and mastered/ are NOT a bug

Investigated 2026-08-27 and closed. Both key shapes embed `{submission_id}`, so two
objects can only coexist in one folder if they came from two different submissions.
Re-uploading the same artist + title creates a second submission and therefore a second
pair of objects. A failed submission still leaves a pair behind if it got past the
mastering step before failing.

**Do not "fix" this by removing the submission id from the key.** That is exactly the
OQ-2 defect, which has already destroyed stem data twice. Orphaned objects from failed
submissions are a cleanup/retention concern, not a keying concern.

---

## OQ-8 — Production Clerk auth runs on a development instance

**Found:** 2026-08-27, while verifying Vercel env vars before repointing the production
branch.

`frontend/src/index.js:7` hardcodes the Clerk publishable key:

```js
const PUBLISHABLE_KEY = 'pk_test_Y3J1Y2lhbC1maWxseS00Ny5jbGVyay5hY2NvdW50cy5kZXYk';
```

It is a **`pk_test_`** key pointing at `crucial-filly-47.clerk.accounts.dev` — a Clerk
*development* instance, serving the live site at `ovoxi.net`.

Publishable keys are public by design, so this is not a credential leak. The problem is
that development instances are not production infrastructure: they carry user-count
ceilings, differ in session and email behaviour, and can be reset. Artist signups are
the top of oVoxi's funnel — hitting a dev-instance user cap would look like the product
being broken, with no error pointing at the cause.

**Also found:** `VITE_CLERK_PUBLISHABLE_KEY` is set in Vercel (Production + Preview) and
does nothing. This is a CRA/craco build (`react-scripts` 5.0.1 via `@craco/craco`), which
only exposes `REACT_APP_*` to the bundle. Nothing under `frontend/src/` reads `VITE_` or
`import.meta.env`. The variable is inert — presumably left from an earlier Vite scaffold.

**To resolve:** create a Clerk production instance, move the key to
`REACT_APP_CLERK_PUBLISHABLE_KEY` in Vercel rather than hardcoding it, and delete the
unused `VITE_` variable. Note that a production Clerk instance needs DNS records on
`ovoxi.net` — this is not a five-minute change.

**Blocks:** real artist signup at any volume. Does not block the stem pipeline.

**Owner:** unassigned.

---

## OQ-9 — verify_clerk_token fetches JWKS on every request and does not check HTTP status

**Found:** 2026-09-03, during the OQ-8 Clerk production-instance migration.

Two issues in `backend/server.py` `verify_clerk_token`:

1. `resp.json()` is called without first checking `resp.status_code`. A non-200 from
   the JWKS endpoint (network blip, DNS failure, rate limit) raises an unstructured
   exception that surfaces to the caller as `"Invalid token"` — the same message as a
   genuinely bad token. This misdirects debugging: a developer assumes the bearer token
   is malformed when the real problem is a failed JWKS fetch.

2. JWKS are fetched on every authenticated request with no in-process cache. In normal
   operation this is a live HTTP call to `https://clerk.ovoxi.net/.well-known/jwks.json`
   per request. Under any meaningful request rate this is unnecessary latency and an
   availability dependency on the Clerk endpoint. A single `asyncio`-safe LRU cache or
   background-refreshed singleton would eliminate both.

**Why it matters:** misread failures slow incident response. The JWKS URL is public,
unauthenticated, and changes rarely — caching it is safe and cheap.

**Do not fix during the OQ-8 cutover.** Changing `verify_clerk_token` while rotating
instance keys adds scope to an already-risky operation.

**Owner:** unassigned.

---

## Note — `REACT_APP_NEW_MARKETING` fails safe

`frontend/src/App.js:20` reads:

```js
const NEW_MARKETING = process.env.REACT_APP_NEW_MARKETING === 'true';
```

Strict comparison against the string `'true'`. Any other value — `false`, `False`,
empty, unset, `1` — renders `HomePage`. The `postbuild` script gates `react-snap` on the
same condition, so with the flag off the prerender step is skipped entirely.

CRA bakes `REACT_APP_*` in at **build** time, so the value present when Vercel builds is
what ships. Changing it in the dashboard has no effect until the next deployment.

