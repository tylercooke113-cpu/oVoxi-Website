---
description: "Phase 0 · READ-ONLY. Orient in the repo and report every LALAL / stem / status touchpoint."
allowed-tools: Read, Grep, Glob
---

Read `CLAUDE.md`, `docs/PRD-01-stem-splitter-migration.md` and
`docs/PRD-02-royalty-splits.md` in full before doing anything.

Then, without writing any code, report back:

1. Every line in this repo that references LALAL.AI, with file and line number.
2. Every place the four `stem_paths` keys (`vocals`, `drums`, `bass`, `other`) are read.
3. Every place a submission status string appears, backend and frontend.
4. Anything in the PRDs that contradicts what the code actually does.

**Do not change any files in this session.** This command is deliberately restricted to
read-only tools.
