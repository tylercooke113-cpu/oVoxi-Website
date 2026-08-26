---
description: "Splits Phase 2 · Add the rights-capture step to UploadPage."
---

Follow `CLAUDE.md`. Plan before you code — show me the component structure before writing
it. **Do not touch anything under `frontend/src/marketing/` or the 3D scene.**

---

Per `docs/PRD-02-royalty-splits.md` section 5.

Read PRD-02 **§10.1 and §10.2** first — they amend section 5.

Convert `frontend/src/pages/UploadPage.jsx` into two steps: the existing track form, then a
rights step, then upload. **The file must not be uploaded until rights are attested.**

**Order matters (PRD-02 §10.2):** pick file → validate type and size IMMEDIATELY → rights
step → presign → upload. Do not make an artist fill in three grids of splits and then lose
it all to "only MP3 or WAV files are accepted".

**Legal name (PRD-02 §10.1):** every party needs an explicit `legal_name` — the name the
IPI is registered to — prefilled from `artist_name` but clearly labelled *"Legal name as
registered with your PRO — not your artist name."* `artist_name` is a stage name and must
never be used silently as a registration name, including in the `owns_everything`
expansion.

Build the three grids (writers, publishers, master owners), each 1–4 rows with
name / IPI / role / PRO / share %. Per side: a live running total, the remaining
percentage, and a "split evenly" button that distributes basis points and gives the
remainder to the first row so the side always lands on exactly 100%.

The "I own 100% of the publishing and master of this recording" checkbox collapses all
three grids and pre-fills a self row in each; unchecking restores what was previously
typed.

Include the explanatory note that writer and publisher shares are each 100% *of their own
side*. Artists get this wrong constantly and it is the single most likely source of bad
data.

Convert percentages to basis points with `Math.round(pct * 100)` on submit and send
`rights` in the presign request body.

Use only the existing shadcn primitives in `frontend/src/components/ui/`. Do not add a form
library — the page uses plain `useState` today.

---

**GATE:** run it locally. Try to submit 33/33/33 — it must block at 99%. Try to add a 5th
writer — the UI must prevent it, and separately `curl` the presign route with 5 writers to
confirm the server rejects it too.
