---
name: Bug
about: Something is broken or looks wrong
title: ""
labels: bug
---

## Symptom
What you saw, exactly — a screenshot, an error message, a wrong number. Not "the neighborhoods
page is broken" but "the neighborhoods page shows 6 rows starting at #6, no #1-5."

## Where
Page/URL, or CLI command, or which data source's `source_runs` row.

## Expected
What should have happened instead.

## Acceptance criteria
- [ ] Root cause identified (not just the symptom papered over)
- [ ] Fix verified against the original symptom
- [ ] `uv run pytest` / `npx tsc --noEmit` still pass

## Verify by
The exact repro steps (URL + filters, or CLI command + args) a reviewer can run to confirm the fix.

## `/goal`
`<the /goal quality-gate condition for this issue — checks that must pass, and a turn cap>`
