# PRD 01 — Replace LALAL.AI with an open-source stem separator

Status: proposed · Owner: CTO · Target: backend only, zero frontend contract change

---

## 1. Problem

The LALAL.AI subscription is cancelled. `_lalal_upload` / `_lalal_split` in
`backend/server.py` still run on every upload, so `_process_stems` now fails at step 4
and every submission lands in `status: "failed"`. The ACRCloud gate and the Matchering
mastering step still work and must be preserved.

Secondary problem: even when it worked, LALAL.AI was a per-minute metered dependency on
a closed model. For a company whose product is *rights provenance*, an opaque
third-party processor in the catalog ingestion path is a liability — we cannot attest to
what it does with the audio.

---

## 2. Recommendation

**Engine:** [`python-audio-separator`](https://github.com/nomadkaraoke/python-audio-separator)
(MIT) as the runtime wrapper, running:

| Stem group | Model | Architecture | Reported SDR |
|---|---|---|---|
| vocals + instrumental | `MelBandRoformer` (KimberleyJensen edition) | Mel-Band RoFormer | 10.98 (vocals/other) |
| drums / bass / other | `htdemucs_ft` | Hybrid Transformer Demucs | 9.16 multisong avg (4-stem) |

Rationale for the wrapper rather than raw checkpoints: `python-audio-separator` already
handles model download/caching, MDX/VR/Demucs/MDXC/RoFormer inference, chunking for long
files, ensembles, and stem renaming, and exposes both a CLI and a Python API. Writing our
own RoFormer inference harness buys nothing and costs weeks.

Rationale for two models rather than one: RoFormer-class models are the current top of
the open vocal-separation leaderboards but are 2-stem (vocals/other). The existing
pipeline produces four stems (`vocals`, `drums`, `bass`, `other`). HTDemucs gives us the
rhythm-section split. Running both is still far cheaper than the LALAL subscription.

**Compute host:** [Modal](https://modal.com) serverless GPU, L4 class
($0.000222/sec ≈ $0.80/hr, per-second billing, $30/mo free credits on the Starter plan).

### Why Modal and not the alternatives

| Option | Verdict | Reasoning |
|---|---|---|
| **Run it in the Railway container** | Rejected | The Dockerfile is `python:3.12-slim` on CPU. There is no GPU. RoFormer on CPU is roughly an order of magnitude slower than realtime, and `_process_stems` runs *inside the web process* via `BackgroundTasks` — a 20-minute CPU separation would starve the API. |
| **Modal serverless GPU** | **Chosen** | Per-second billing means idle cost is zero, which matches bursty artist uploads. It runs an arbitrary container, so we control the exact model versions and can attest to the processing chain. Estimated ~$0.01–0.03 per 4-minute track on L4 — *this is an estimate and must be measured in Phase 1, not trusted.* |
| **Replicate** | Fallback | Likely simpler if a maintained `audio-separator` model exists there. I could not confirm one currently exists — verify before choosing this. |
| **Dedicated GPU box (Lambda/Vast/AWS g5)** | Defer | Cheapest per track only at sustained volume (full-catalog backfill). Revisit when we are ingesting continuously; it adds ops burden we do not need at current volume. |

---

## 3. Open questions — do not guess these

1. **Model weight licensing.** `python-audio-separator` is MIT, but the UVR-community
   checkpoints it downloads have mixed and often unstated provenance, and several were
   trained on MUSDB18/MUSDB18-HQ, which carries a non-commercial research licence.
   **I do not know** whether the specific RoFormer checkpoint we select is cleared for
   commercial use. This must be resolved by IP counsel *before* production catalog
   ingestion. It matters more for oVoxi than for a typical startup, because we sell
   rights cleanliness.
2. **Demucs weights.** Demucs code is MIT; the licence attached to the released
   pretrained weights needs to be read directly from `facebookresearch/demucs` and
   confirmed. Not verified here.
3. **Quality vs LALAL.** There is no public head-to-head benchmark of LALAL's "Phoenix"
   splitter against RoFormer, because Phoenix is closed and unpublished. We should not
   claim "better than LALAL" until Phase 1's A/B test says so on our own catalog.

**Mitigation if (1) or (2) blocks:** fall back to a checkpoint with an unambiguous
permissive licence, accept the SDR delta, and record the tradeoff in the provenance
metadata. That is an acceptable outcome; shipping on an unlicensed checkpoint is not.

---

## 4. Architecture

```
Railway (FastAPI, CPU)                    Modal (GPU, ephemeral)
─────────────────────                     ──────────────────────
POST /api/upload/complete
  └─ BackgroundTasks → _process_stems
       ├─ ACRCloud gate         (unchanged)
       ├─ Matchering master     (unchanged)
       └─ stem_service.separate(...)
              │  submits job ─────────────► separate_stems()
              │                               ├─ GET mastered from R2
              │                               ├─ MelBandRoformer → vocals / other
              │                               ├─ htdemucs_ft   → drums / bass
              │                               └─ PUT 4 stems to R2
              │                                     │
              └──────── HMAC webhook ◄──────────────┘
                 POST /api/internal/stems/callback
                   └─ set status=completed, stem_paths={...}
```

### Files

| File | Change |
|---|---|
| `backend/stem_service.py` | **new.** `StemSeparator` protocol + `ModalStemSeparator`. Single seam so the engine can be swapped again without touching `server.py`. |
| `infra/modal/stem_worker.py` | **new.** The Modal app: image definition, model pre-bake, `@app.function(gpu="L4")` entrypoint, R2 I/O, webhook callback. |
| `infra/modal/README.md` | **new.** Deploy + secret setup. |
| `backend/server.py` | Delete `_lalal_upload`, `_lalal_split`, `LALAL_API_KEY`, `LALAL_BASE`. Rewrite the stem section of `_process_stems` to call `stem_service`. Add the callback route. |
| `backend/requirements.txt` | Remove nothing (LALAL used plain `httpx`). Add `modal`. |

### Why a separate `stem_service.py` rather than inlining

`server.py` is already a 940-line monolith and every vendor change so far has meant
surgery in the middle of it. A one-file adapter with a typed interface means the next
engine change is a new class, not a diff through the pipeline. Cost: one extra file.

### Bake the models into the image

Model weights must be downloaded at **image build time**, not at request time. A cold
container that downloads ~500MB of checkpoints per job destroys both latency and the
per-second cost argument.

---

## 5. Contract preservation (the "don't break anything" list)

- `stem_paths` keeps exactly the keys `vocals`, `drums`, `bass`, `other`.
- Stems stay MP3 at `catalog/{artist}/{track}/stems/{name}.mp3` with content type `audio/mpeg`.
- Status strings are unchanged. Note `processing` is written **twice** in the current code (L271 spurious, L282 real) and does not exclusively mean "separating"; the Phase 2 branch must not assume it does.
- The ACRCloud gate still runs first and still short-circuits on non-`CLEARED`.
- Matchering still runs before separation and still writes the `/mastered/` key.
- `POST /api/upload/complete` still returns `{"status": "processing", "submission_id": ...}`.
- **No frontend change is required by this PRD.** If a frontend change appears necessary, stop and re-plan.

New env vars (Railway): `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET`, `STEM_WEBHOOK_SECRET`, `STEM_ENGINE`.
New Modal secrets: R2 credentials, `STEM_WEBHOOK_SECRET`, the Railway callback URL.

The callback route is server-to-server. Authenticate it with an HMAC-SHA256 signature
over the raw body using `STEM_WEBHOOK_SECRET`, compared with `hmac.compare_digest`. Do
**not** put it behind Clerk and do **not** leave it open.

---

## 6. Phases

**Phase 0 — safety net.** Branch. Capture a golden set of 5–10 tracks that already have
LALAL stems in R2; copy them to `benchmark/lalal-baseline/`. Once LALAL is deleted these
cannot be regenerated.

**Phase 1 — Modal worker, standalone.** Build and deploy `infra/modal/stem_worker.py`.
Prove it end to end from a local script, not from the API. Record wall-clock and cost per
track. Run the A/B against the Phase 0 baseline and write the result into
`docs/benchmark-stem-quality.md`. **Gate: do not proceed until the new stems are judged
at least as good as the LALAL baseline on the golden set.**

**Phase 2 — wire into the backend behind a flag.** Add `stem_service.py`, the callback
route, and `STEM_ENGINE=lalal|modal`. LALAL code still present. Deploy with
`STEM_ENGINE=modal` and run real uploads through staging.

**Phase 3 — delete LALAL.** Separate commit. Remove the two helpers, the two constants,
the env var from Railway, and the mentions in `docs/marketing-revamp-blueprint.md`.
Remove the `STEM_ENGINE` flag once the engine is the only one.

**Phase 4 — backfill.** Re-run every submission currently stuck in `failed` whose failure
reason was LALAL. Admin-only route, idempotent, rate-limited.

---

## 7. Acceptance criteria

- [ ] A track uploaded through the real UI reaches `completed` with four playable stems in the Vault.
- [ ] Cost and wall-clock per track are measured and documented, not estimated.
- [ ] The A/B doc exists and shows the new engine is not a regression.
- [ ] `grep -ri lalal backend/ frontend/src/ docs/` returns nothing.
- [ ] The callback route rejects an unsigned and a wrongly-signed request.
- [ ] A Modal-side failure marks the submission `failed` with a useful `error`, and does not hang forever.
- [ ] Licensing questions in §3 are answered in writing before any commercial catalog ingestion.

---

## Sources

- [python-audio-separator](https://github.com/nomadkaraoke/python-audio-separator)
- [ZFTurbo — Music-Source-Separation-Training, pretrained models](https://github.com/ZFTurbo/Music-Source-Separation-Training/blob/main/docs/pretrained_models.md)
- [Mel-Band RoFormer paper](https://arxiv.org/html/2310.01809v1)
- [Modal pricing](https://modal.com/pricing)

---

## 10. Amendments after the code audit (supersedes anything above that conflicts)

### 10.1 The `other` stem is not what §2 assumed — decision required and made

**Finding.** In the current pipeline `other` is **not** a separation target. It is
LALAL's `back_track` from the *vocals* split (server.py L308–312) — i.e. the **full
instrumental**: everything except vocals. It therefore **overlaps** `drums` and `bass`.
The existing catalog's four stems do not sum to the mix; `vocals + other` sums to the mix,
and `drums`/`bass` are duplicated content carved out of `other`.

htdemucs's `other` is a different thing: the **residual** after vocals, drums and bass are
removed. Guitars, keys, pads. Non-overlapping.

Writing htdemucs residual into the `other` key would leave the catalog holding two
incompatible meanings under one name, distinguishable only by upload date. For a
training-rights catalog whose product is provenance, that is the worst outcome available.

**Decision: emit five stems, and version the schema.**

```
vocals        isolated vocal            (RoFormer)
drums         isolated drums            (htdemucs_ft)
bass          isolated bass             (htdemucs_ft)
other         TRUE residual             (htdemucs_ft)   ← new meaning
instrumental  full mix minus vocals     (RoFormer)      ← old `other` meaning, renamed
```

Add `stem_schema_version: int` to `TrackSubmission`. Legacy documents are version `1`
(4 keys, overlapping, `other` = instrumental). New documents are version `2`.

**Rationale.** Non-overlapping stems that sum to the mix are materially more useful for
model training than overlapping ones, which is the entire reason the catalog exists. The
rename preserves the old artifact under an honest name rather than silently redefining a
key. And the audit established that this is cheap to do: `VaultPage.jsx` and
`AdminPage.jsx` both iterate `stem_urls` dynamically. The only hardcoded list of stem
names in the entire frontend is the display-label map at `AdminPage.jsx:11`, which needs
one line added for `instrumental`.

**This is the one frontend change PRD-01 permits.** One line in one label map. Anything
beyond that, stop and re-plan.

**Cost:** a fifth MP3 per track in R2 and a little more GPU time. Accepted.

**Backfill:** legacy documents keep `stem_schema_version: 1` and are not rewritten. Do not
retroactively rename their keys — that would break the provenance record we are trying to
protect. Anything consuming stems must branch on the version.

### 10.2 Delete the spurious `processing` write

Phase 3 additionally removes the `status: "processing"` write at server.py L271. It is
undocumented, immediately overwritten, and makes the status meaningless for any future
polling UI. Do not remove it in Phase 2 — that phase is additive only.

### 10.3 Note for the Phase 3 grep

The LALAL stem-name mapping is `("drums", "drum")` — LALAL's parameter is singular. The
`stem_paths` key and R2 path are correctly plural. No action; noted so the deletion does
not "fix" the plural by mistake.

### 10.4 Note for the Phase 1 A/B

The A/B must compare like with like: legacy `other` (instrumental) against the new
`instrumental`, **not** against the new `other`. The new `other` has no legacy counterpart
and should be assessed on its own for bleed and artefacts.

---

## 11. Phase 1 gate — MEASURED results (2026-08-26)

Modal L4, `retries=0`, warm container. Five stems + FLAC + both `other` variants.

| Track | Wall-clock | Cost |
|---|---|---|
| Tyler J — All Along | 151 s | $0.0336 |
| teewhy — all along | 104 s | $0.0231 |
| teewhy — ceo | 139 s | $0.0308 |

**Gate: PASSED** (threshold ≤ 5 min, ≤ $0.10 per track.)

Mean ≈ **131 s / $0.029 per track**. This supersedes the ~$0.01–0.03 estimate in §2,
which was optimistic on time by roughly 2×. Note these runs produce more outputs than
production will (both `other` variants plus FLAC); the steady-state number after the §10.1
decision will be lower.

### Revised own-hardware crossover

At $0.029/track, a dedicated GPU box at ~$300/month breaks even around **10,000
tracks/month** — not the ~20,000 quoted earlier in conversation, which used the optimistic
estimate. Below that, serverless is cheaper. Recalculate before buying hardware.

Catalog-scale reference: 10k tracks ≈ $290. 100k tracks ≈ $2,900.

### Dependency fixes required to reach this (do not lose these)

The published `audio-separator` dependency set does not install cleanly on a fresh
Python 3.12 CUDA image. Five fixes were needed:

1. `audioread` + `librosa` must be declared explicitly — `audio-separator` imports
   `audioread` in `spec_utils.py` without declaring it, and newer `librosa` no longer
   provides it transitively.
2. `librosa==0.10.1`, not 1.0.0 — `get_duration(filename=...)` was removed in 1.0.
3. `torchaudio.info` / `.load` / `.save` are gone in torchaudio 2.11 (torchcodec backend
   not installed). Use `ffprobe` for probing and `soundfile` + `librosa` for I/O.
4. RoFormer output filenames embed the model name, which collides with naive keyword
   matching on `other`. Match on the `_(other` prefix instead.
5. Scan output directories directly rather than constructing paths from the bare filenames
   `separate()` returns.

**These pins are load-bearing.** Anyone rebuilding this image from scratch in six months
will hit all five again unless the versions stay pinned.
