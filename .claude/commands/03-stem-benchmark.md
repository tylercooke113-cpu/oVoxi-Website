---
description: "Phase 1 · A/B the new engine against the captured LALAL baseline."
---

Follow `CLAUDE.md`. Plan before you code. If you do not know something, say "I do not
know" rather than guessing.

---

Per `docs/PRD-01-stem-splitter-migration.md` Phase 1.

Using `benchmark/lalal-baseline/`, run the Modal worker over the same mastered sources and
write the new stems to `benchmark/new-engine/{submission_id}/`.

Then write `docs/benchmark-stem-quality.md` containing, per track and per stem: file size,
duration, peak and RMS level, and a spectral comparison against the LALAL baseline.
Include the objective numbers you can actually compute — **do not assert perceptual
quality you have not measured**, and say so explicitly where a number is not available.

Generate a small static HTML page at `benchmark/compare.html` that plays the LALAL and new
stem side by side for each track so I can A/B them by ear. Self-contained, no CDN.

---

**GATE — this one is mine, not yours.** I listen to the A/B myself. Do not proceed to
`/04-stem-wire` until I say the new stems are not a regression.
