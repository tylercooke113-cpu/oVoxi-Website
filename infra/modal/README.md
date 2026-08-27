# oVoxi Modal Stem Worker

Phase 2 of PRD-01: GPU stem separation on Modal L4, wired to the backend callback route.

---

## Secret keys required

Create the Modal secret **before deploying**. All six keys must be present.

```bash
modal secret create ovoxi-stem-secrets \
  R2_ENDPOINT="https://<account_id>.r2.cloudflarestorage.com" \
  R2_ACCESS_KEY_ID="<key_id>" \
  R2_SECRET_ACCESS_KEY="<secret>" \
  R2_BUCKET_NAME="<bucket>" \
  STEM_WEBHOOK_SECRET="<hex_from_openssl_rand_hex_32>" \
  STEM_CALLBACK_URL="https://ovoxi-website-production.up.railway.app/api/internal/stems/callback"
```

`STEM_WEBHOOK_SECRET` is the same value that must be set in Railway as `STEM_WEBHOOK_SECRET`
for the callback route. Generate it once with `openssl rand -hex 32` and keep it in both places.

**Verify `STEM_CALLBACK_URL` before setting `STEM_ENGINE=modal` in Railway.** During Phase 1
testing it was set to a temporary webhook.site URL. A stale URL silently hangs every track in
`processing` with no error. To verify the value inside the container run:

```bash
python3 - <<'EOF'
import modal, os
app = modal.App("ovoxi-check-secret")

@app.function(secrets=[modal.Secret.from_name("ovoxi-stem-secrets")])
def check():
    url = os.environ.get("STEM_CALLBACK_URL", "__MISSING__")
    print(f"STEM_CALLBACK_URL: {url}")

@app.local_entrypoint()
def main():
    check.remote()
EOF
modal run -
```

To update an existing secret (e.g. to correct `STEM_CALLBACK_URL`):
```bash
modal secret create ovoxi-stem-secrets --force \
  R2_ENDPOINT="..." \
  R2_ACCESS_KEY_ID="..." \
  R2_SECRET_ACCESS_KEY="..." \
  R2_BUCKET_NAME="..." \
  STEM_WEBHOOK_SECRET="..." \
  STEM_CALLBACK_URL="https://ovoxi-website-production.up.railway.app/api/internal/stems/callback"
```

---

## Deploy

```bash
# From repo root
modal deploy infra/modal/stem_worker.py
```

The first deploy triggers `_download_models()` inside the image build. This downloads
~500 MB of model weights (vocals_mel_band_roformer.ckpt + htdemucs_ft) and bakes them
into the image layer. Subsequent deploys reuse the cached layer unless the image
definition changes.

---

## Model names (confirmed against audio-separator 0.31.3)

| Constant | Checkpoint | Description |
|---|---|---|
| `ROFORMER_MODEL` | `vocals_mel_band_roformer.ckpt` | MelBand Roformer – Vocals by Kimberley Jensen, 2-stem |
| `DEMUCS_MODEL` | `htdemucs_ft.yaml` | Demucs v4 htdemucs_ft, 4-stem (vocals/drums/bass/other) |

Confirmed via `modal run infra/modal/list_models.py` — see that file for the full catalogue.

---

## Five stems produced (stem_schema_version: 2)

| Key | Source | Description |
|---|---|---|
| `vocals` | RoFormer | Isolated vocal |
| `instrumental` | RoFormer | Full mix minus vocals |
| `drums` | htdemucs_ft | Isolated drums |
| `bass` | htdemucs_ft | Isolated bass |
| `other` | htdemucs_ft | True residual (guitars, keys, pads) — non-overlapping |

`other_subtract` (instrumental − drums − bass) is computed inside the worker but not
uploaded. Kept per CLAUDE.md rule 4; removal is a later commit.

Each stem is written as MP3 320 kbps to `catalog/{artist}/{track}/stems/`.
FLAC was evaluated in Phase 1 and rejected after the /03 A/B benchmark.

### `key_prefix` parameter

`separate_stems` accepts a `key_prefix` argument that controls the R2 write destination:

- **Production** (`_process_stems` in `server.py`): omits the argument, so the default
  `"catalog"` is used. Stems land at `catalog/{artist_slug}/{track_slug}/stems/`.
- **Benchmark** (`run_stem_benchmark.py`): passes `key_prefix=f"_benchmark/{sid}"` to
  stay out of `catalog/`. The benchmark script has a hard refuse if the resolved prefix
  starts with `catalog/`.

There is no server-side guard in the worker or in `_process_stems` that validates the
resolved prefix before writing. A bad slug writes to a wrong path under `catalog/`
unchallenged. See **OQ-6** in `docs/open-questions.md`.

---

## HMAC callback signature

The callback POST body is compact JSON (`sort_keys=True, separators=(',',':')`).
The `X-Ovoxi-Signature` header is `sha256=<hex>` where `<hex>` is
`HMAC-SHA256(STEM_WEBHOOK_SECRET, raw_body).hexdigest()`.

The callback route (`/api/internal/stems/callback`) must:
1. Read the raw body before JSON-parsing it.
2. Compute the same HMAC.
3. Compare with `hmac.compare_digest`.

The HMAC is computed over the exact bytes sent. The worker uses `data=body`, never
`json=payload` — requests' `json=` re-serializes with different separators and the
server's `hmac.compare_digest` would always fail.

---

## Phase 1 gate — PASSED (2026-08-26)

Gate criteria (PRD-01 §6 Phase 1): cost per track ≤ $0.10, wall-clock ≤ 5 min on L4.

**Gate of record (/02, three tracks, warm L4):** mean ~131 s / ~$0.029 per track.
Both thresholds passed. Recorded in PRD-01 §11.

**Post-fix rerun (2026-08-26, five rows / four unique tracks):** run after the
`_pick` keyword bug fix to verify correct stem assignment. `1800f622` and `dc9cbb73`
are the same source recording (OQ-2), so the five rows cover four unique tracks.
These are not the gate measurements — the /02 figures above are.

| Track | Submission | Wall-clock | Cost |
|---|---|---|---|
| Tyler J — All Along | 1800f622 | 169.7 s | $0.0377 |
| teewhy — all along | dc9cbb73 † | 92.2 s | $0.0205 |
| teewhy — ceo | 8ccb8ab3 | 60.4 s | $0.0134 |
| teewhy — Dirty Secret | 86677473 | 122.9 s | $0.0273 |
| damnsonic — cutthroat | b114fc07 | 106.4 s | $0.0236 |
| **Mean (4 unique)** | | **~116 s / ~1.9 min** | **~$0.026** |

† Same source recording as 1800f622 (OQ-2 collision). Full details in
`docs/benchmark-stem-quality.md`.

---

## Licensing open questions (PRD-01 §3 — not yet resolved)

- `vocals_mel_band_roformer.ckpt` — checkpoint by Kimberley Jensen. Licence not confirmed
  for commercial use. Must be resolved by IP counsel before production ingestion.
- `htdemucs_ft` — Demucs weights from `facebookresearch/demucs`. Licence of released
  pretrained weights needs direct confirmation. Code is MIT; weights may differ.

**Do not ingest production catalog until both are cleared.**
