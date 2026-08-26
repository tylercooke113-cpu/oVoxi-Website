# oVoxi Modal Stem Worker

Phase 1 of PRD-01: GPU stem separation on Modal L4.

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

`STEM_WEBHOOK_SECRET` is the same value that must be set in Railway as `STEM_WEBHOOK_SECRET` for
the Phase 2 callback route. Generate it once with `openssl rand -hex 32` and keep it in both places.

For Phase 1 testing (before the callback route exists), set `STEM_CALLBACK_URL` to a temporary
endpoint such as `https://httpbin.org/post` to capture and inspect the signed payload.

To update an existing secret (e.g. to swap in the real callback URL for Phase 2):
```bash
modal secret create ovoxi-stem-secrets --force \
  R2_ENDPOINT="..." \
  ...
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

## Six stems produced (stem_schema_version: 2)

| Key | Source | Description |
|---|---|---|
| `vocals` | RoFormer | Isolated vocal |
| `instrumental` | RoFormer | Full mix minus vocals |
| `drums` | htdemucs_ft | Isolated drums |
| `bass` | htdemucs_ft | Isolated bass |
| `other_htdemucs` | htdemucs_ft | Residual (guitars, keys, pads) — non-overlapping |
| `other_subtract` | arithmetic | `instrumental − drums − bass`, sample-aligned |

Both `other_*` variants are written in Phase 1 for the `/03` A/B benchmark.
One will become the canonical `other` key in Phase 2; the other is dropped.

Each stem is written as both MP3 (320kbps) and FLAC to `catalog/{artist}/{track}/stems/`.
The FLAC storage delta is reported in the callback payload (`storage_delta_flac_bytes`).

---

## HMAC callback signature

The callback POST body is compact JSON (`sort_keys=True, separators=(',',':')`).
The `X-Ovoxi-Signature` header is `sha256=<hex>` where `<hex>` is
`HMAC-SHA256(STEM_WEBHOOK_SECRET, raw_body).hexdigest()`.

The Phase 2 callback route (`/api/internal/stems/callback`) must:
1. Read the raw body before JSON-parsing it.
2. Compute the same HMAC.
3. Compare with `hmac.compare_digest`.

---

## Phase 1 gate test

```bash
# After deploying, run the gate test on one baseline track:
python3 scripts/test_modal_stems.py --from-manifest --index 0

# Or against a specific R2 key:
python3 scripts/test_modal_stems.py \
  --r2-key catalog/teewhy/ceo/mastered/8ccb8ab3-8a79-43f2-b8cc-326615030273.mp3 \
  --artist teewhy \
  --track ceo
```

Gate criteria (from PRD-01 §6 Phase 1):
- Cost per track ≤ $0.10
- Wall-clock ≤ 5 minutes on L4

If either fails, stop and re-plan before proceeding to `/04-stem-wire`.

---

## Licensing open questions (PRD-01 §3 — not yet resolved)

- `vocals_mel_band_roformer.ckpt` — checkpoint by Kimberley Jensen. Licence not confirmed
  for commercial use. Must be resolved by IP counsel before production ingestion.
- `htdemucs_ft` — Demucs weights from `facebookresearch/demucs`. Licence of released
  pretrained weights needs direct confirmation. Code is MIT; weights may differ.

**Do not ingest production catalog until both are cleared.**
