# PRD 02 — Writer / publisher / master splits with ASCAP-compatible CWR export

Status: proposed · Owner: CTO · Touches: backend models + new routes, UploadPage, VaultPage, AdminPage

---

## 1. Problem

oVoxi's deal is a revenue split on mechanical and performance royalties in exchange for
training rights. Today `TrackSubmission` records only `pro_registered`, `pro_org` and
`pro_register_us` — three booleans/strings that the frontend does not even send. We have
no idea who actually owns the composition or the master of a track we ingest.

That is not a nice-to-have gap. If an artist owns 50% of the publishing and we pay them
as if they owned 100%, we have misallocated someone else's money, and if we register a
work we do not control, we create a conflicting claim at the PRO.

---

## 2. The domain model, stated plainly

Two entirely separate rights are involved and they must not be blended into one number:

**A. The composition (the song).** Performance royalties are conventionally divided into
two halves:

- the **writer's share** — 50% of the total, split among up to 4 songwriters
- the **publisher's share** — 50% of the total, split among up to 4 publishers

Each side is expressed as a percentage summing to **100% of its own side**, i.e. 50% of
the total performance royalty. This is why ASCAP statements show a writer at "100%" and
a publisher at "100%" for a solely-owned song. The UI must use the same convention or
artists will enter the wrong numbers.

**B. The master (the sound recording).** A separate right, not administered by a PRO.
Owners sum to 100%. Relevant to mechanical/neighbouring income and to whether we can
legally use the recording for training at all.

**Design decision:** three independent party lists — `writers[]`, `publishers[]`,
`master_owners[]` — each capped at 4 entries, each validated to sum to exactly 100%.
This is more honest than a single "splits" blob and maps 1:1 onto CWR records.

---

## 3. Data model

Store all shares as **integer basis points** (`5000` = 50.00%), never as floats.
Floating-point percentages will drift and a sum-to-100 validation on floats will
intermittently reject valid input. Range 1–10000, sides must sum to exactly 10000.

New embedded document on `track_submissions`:

```python
class RightsParty(BaseModel):
    name: str                      # legal name as registered
    ipi_name_number: Optional[str] # 9 or 11 digits, required for CWR export
    society: Optional[str]         # ASCAP / BMI / SESAC / PRS / ...
    role: Optional[str]            # CWR role code — writers/publishers only
    share_bp: int                  # basis points, 1..10000
    is_self: bool = False          # this party is the submitting artist

class TrackRights(BaseModel):
    owns_everything: bool = False  # the "I own 100%" shortcut
    writers: List[RightsParty]        # 1..4, sum(share_bp) == 10000
    publishers: List[RightsParty]     # 1..4, sum(share_bp) == 10000
    master_owners: List[RightsParty]  # 1..4, sum(share_bp) == 10000
    iswc: Optional[str] = None
    isrc: Optional[str] = None
    attested_at: datetime
    attested_by_clerk_user_id: str
```

`TrackSubmission` gains `rights: Optional[TrackRights] = None`. Nullable, so every
existing document keeps validating — **do not** make it required.

CWR role codes to offer for writers: `CA` composer/author, `C` composer, `A` author,
`AR` arranger, `AD` adaptor, `TR` translator. For publishers: `E` original publisher,
`AM` administrator, `SE` sub-publisher, `PA` income participant.

### Why embed rather than a separate `works` collection

One recording, one rights statement, in v1. A separate `works` collection becomes correct
once the same composition appears on multiple recordings (remixes, live versions, an
artist re-registering). Note it as the known v2 refactor; do not build it now.

---

## 4. Validation rules (enforce on the server — the client is a convenience)

1. Each of the three lists has 1–4 entries.
2. Each list's `share_bp` sums to exactly `10000`. Reject otherwise with a message naming which side is off and by how much.
3. Every `share_bp` ≥ 1. No zero-share parties.
4. Party names non-empty, ≤ 120 chars, deduplicated per list.
5. `ipi_name_number`, when present, is 9 or 11 digits. Required on every party if the submission is flagged for PRO registration.
6. `owns_everything: true` is a **server-side shortcut, not a bypass**: the server expands it into one 10000-bp self party on each of the three lists using the artist's profile name, then runs rules 1–5 normally. Never store a submission whose lists are empty because the flag was set.
7. Rights are immutable once `status == "completed"` and the work has been exported. Edits after that create a **revision** (CWR `REV` transaction), they do not mutate history. Append-only is a requirement of the provenance story, not a preference.

---

## 5. UI flow (UploadPage)

The current page is a single form. Add **step 2 of 2** between the form and the upload —
the file is not uploaded until rights are attested, so we never hold audio we have no
ownership statement for.

```
┌ Who owns this recording? ───────────────────────────┐
│                                                     │
│  ☑ I own 100% of the publishing and master of this  │
│    recording                                        │
│                                                     │
│  ── or enter the splits ──                          │
│                                                     │
│  WRITERS (must total 100%)          [+ Add writer]  │
│  ┌───────────────┬─────┬──────┬──────┬───────────┐  │
│  │ Name          │ IPI │ Role │ PRO  │  Share %  │  │
│  └───────────────┴─────┴──────┴──────┴───────────┘  │
│  Running total: 100% ✓                              │
│                                                     │
│  PUBLISHERS (must total 100%)    [+ Add publisher]  │
│  … same grid …                                      │
│  Running total: 75%  — 25% remaining                │
│                                                     │
│  MASTER OWNERS (must total 100%)    [+ Add owner]   │
│  … same grid …                                      │
│                                                     │
│  ⓘ Writer and publisher shares are each 100% of     │
│    their own side — together they make up the       │
│    full performance royalty (50/50).                │
│                                                     │
│  ☐ I attest these splits are accurate and I have    │
│    the authority to license this recording.         │
└─────────────────────────────────────────────────────┘
```

Behaviour:

- The "I own 100%" checkbox collapses all three grids and pre-fills a single self row in each. Unchecking restores whatever was typed before.
- Live running total per side, with the remainder shown. Submit disabled until all three read 100% and the attestation box is ticked.
- "Split evenly" button per side — divides 10000 bp across the rows and gives the remainder basis points to the first row so it always lands on exactly 100%.
- Percent input accepts two decimals; convert to bp on submit (`Math.round(pct * 100)`).
- Reuse the existing shadcn `Input` / `Select` / `Checkbox` primitives already in `frontend/src/components/ui/`. Do not add a form library — the page currently uses plain `useState`.

**VaultPage:** show a read-only rights summary per track and a "Registration: not filed / filed / conflict" badge.

**AdminPage:** rights review column, an export action, and the ability to flag a
submission as disputed.

---

## 6. API changes

| Route | Change |
|---|---|
| `POST /api/upload/presign` | `PresignRequest` gains `rights: TrackRights`. Validate before generating the URL, so an invalid split never produces an upload slot. |
| `GET /api/vault/tracks` | Return `rights` in the projection. |
| `GET /api/submissions` | Return `rights`. |
| `POST /api/rights/{submission_id}/revise` | **new.** Clerk-authed. Creates a revision, does not mutate. |
| `POST /api/registrations/export` | **new.** Admin-only. Body: list of submission ids. Returns a CWR file. |
| `GET /api/registrations` | **new.** Admin-only. Export history. |

Keep `pro_registered` / `pro_org` / `pro_register_us` on the model for now — they are
written by existing documents. Mark them deprecated in a comment; remove in a later pass.

---

## 7. CWR export

**Format:** CWR v2.1 revision 8. It is the version PROs and the MLC accept most broadly;
CWR 3.0 exists but adoption is uneven. Fixed-width ASCII records, one file per batch.

Record sequence for a new registration:

```
HDR   transmission header (sender type, sender ID, sender name, creation date)
 GRH  group header — transaction type NWR
  NWR new work registration   (title, submitter work #, ISWC, duration, ...)
   SPU publisher controlled by submitter  (+ SPT territory/collection shares)
   SWR writer controlled by submitter     (+ SWT territory, PWR writer→publisher link)
   OWR other writer / OPU other publisher (uncontrolled parties)
   REC recording detail (ISRC, recording date)
   ORN work origin
 GRT  group trailer
TRL   transmission trailer
```

- `writers[]` → `SWR` (controlled) or `OWR` (not controlled), share in `SWT`.
- `publishers[]` → `SPU`/`OPU`, share in `SPT`, linked to writers via `PWR`.
- `master_owners[]` → **not part of CWR.** CWR is composition-side only. Master ownership is exported separately (DDEX or a plain manifest) — do not try to force it into CWR.
- Shares in CWR are expressed in hundredths of a percent — our basis-points storage maps directly, which is the reason for the choice.
- Filename convention: `CW{yy}{nnnn}{sender}_{recipient}.V21`.

**Build the generator as a pure function** — `rights → CWR string` — in
`backend/cwr/writer.py`, with fixture-based tests. No DB access inside it. It is the
piece most likely to need repeated correction against PRO feedback, and it must be
testable without a database.

### Business prerequisite — flag this before building

Submitting CWR to ASCAP requires oVoxi to be a **registered publisher** with a
**CISAC-assigned CWR Sender ID** and an IPI Name Number, and to be onboarded to a
delivery channel (ASCAP/MusicMark or a distributor). Writing the file is an engineering
task of days; getting the right to transmit it is a business task of weeks to months.

**I do not know** oVoxi's current publisher registration status. Confirm it before Phase 3
of this PRD, because the export is worthless without it. v1 therefore ships the generator
plus a validated downloadable file, not an automated transmission.

---

## 8. Phases

**Phase 1 — model + validation.** `RightsParty`, `TrackRights`, basis-point arithmetic,
`owns_everything` server-side expansion, unit tests for every rule in §4. No UI.

**Phase 2 — UploadPage step 2.** The three grids, the shortcut checkbox, live totals,
split-evenly, attestation. Wire into `presign`.

**Phase 3 — read surfaces.** Vault summary, Admin review column, revision route.

**Phase 4 — CWR generator.** `backend/cwr/writer.py` + fixtures + the admin export route.
Validate output against a third-party CWR validator before claiming it works.

**Phase 5 — registration lifecycle.** Track filed/acknowledged/conflict state from PRO
acknowledgement files (`ACK`). Only after the sender ID exists.

---

## 9. Acceptance criteria

- [ ] A submission with 3 writers at 33.34/33.33/33.33 and 2 publishers at 50/50 validates and round-trips exactly, with no rounding drift.
- [ ] A side summing to 99.99% or 100.01% is rejected with a message naming the side and the delta.
- [ ] A 5th party on any side is rejected by the server, not only by the UI.
- [ ] "I own 100%" produces three fully populated lists server-side, never empty ones.
- [ ] Existing submissions with no `rights` field still load in Vault and Admin.
- [ ] The generated CWR file passes an independent CWR 2.1 validator.
- [ ] Master ownership is exported outside CWR and is not silently dropped.
- [ ] A rights edit after completion creates a revision; the original is still readable.

---

## Sources

- [The MLC — CWR User Guide](https://www.themlc.com/hubfs/CWR%20User%20Guide_May%202024_FINAL.pdf)
- [MusicMark — Common Works Registration User Manual](https://musicmark.com/documents/cwr11-1494_cwr_user_manual_2011-09-23_e_2011-09-23_en.pdf)
- [CWR documentation — matijakolaric.com](https://matijakolaric.com/articles/formats/cwr/documentation/)
- [DDEX KB — MWN and CWR](https://kb.ddex.net/implementing-each-standard/musical-work-data-and-rights-communication-(mwdr)/musical-work-right-share-notification-standard-(mwn)/mwn-explained/mwn-and-the-common-works-registration-(cwr)/)

---

## 10. Amendments after the code audit (supersedes anything above that conflicts)

### 10.1 `owns_everything` needs a legal name, and `artist_name` is not one

**Finding.** §4 rule 6 says the server expands the shortcut "using the artist's profile
name". At presign time no such profile exists — the only name available is `artist_name`,
a free-text form field. It is a **stage name**. Registering "Lil Something" as a writer at
ASCAP against an IPI issued to a legal person produces a rejected or, worse, a silently
mismatched registration.

**Decision.** `RightsParty` gains an explicit legal-name field:

```python
legal_name: str          # the name the IPI is registered to
performing_name: Optional[str]   # stage name, display only
```

The rights step asks for legal name explicitly, prefilled from `artist_name` and clearly
labelled *"Legal name as registered with your PRO — not your artist name."* The
`owns_everything` expansion uses `legal_name`, and `legal_name` is **required** on every
party, shortcut or not. Never derive it from `artist_name` silently.

This is the field most likely to be filled in wrong by a hurried artist, and the one whose
error surfaces months later as an unpayable registration.

### 10.2 Move file validation before the rights step

**Finding.** §5 puts rights capture before upload, which is correct — we should not hold
audio we have no ownership statement for. But file type and size are validated
client-side in `handleFile`, and the server only rejects a bad extension at presign,
*after* the artist has filled in three grids of splits. Losing that work to "only MP3 or
WAV files are accepted" is a gratuitous way to lose a submission.

**Decision.** UI order is: pick file → validate type and size immediately → rights step →
presign → upload. Server-side extension and genre validation must still run at presign,
unchanged. This is a UI ordering change only; no contract moves.

### 10.3 The deprecated PRO fields are confirmed unused

`pro_registered`, `pro_org` and `pro_register_us` exist on `TrackSubmission` (L465–467)
and the frontend has never sent them, so every document holds defaults. Confirmed safe to
deprecate. Leave them in place through Phase 3; remove in a dedicated cleanup commit once
`rights` is populated on new submissions.

### 10.4 `STATUS_LABELS` is dead code today — do not revive it accidentally

`UploadPage.jsx` sets `stage='done'` immediately after `upload/complete` and never polls,
so its `STATUS_LABELS` map is unreachable. It covers only 5 of the 11 real statuses. If
any phase of this PRD introduces progress polling on the upload page, that map must be
completed first or artists will see blank states for `scanning`, `mastering`, `CONFLICT`,
`NEEDS_DOCS` and `SCAN_ERROR`.
