---
name: add-region
description: Onboard a new US region (CBSA/metro) into the screener's area-based neighborhood research once Phase 1's areas model exists. Use for "add <city> as a test metro", "onboard a new region", or "load tracts for <metro>". Checks Phase 1 has actually landed before doing anything, since this skill is written ahead of that code.
---

# add-region — onboard a new US metro

**Precondition**: this skill assumes Phase 1 of the approved workflow plan
(`/Users/bobjoe/.claude/plans/i-want-to-create-mellow-quill.md`) has landed — an `areas` model,
generalized scoring, and a `POST /api/regions` endpoint. As of this skill's creation (2026-09-17),
none of that exists yet (`grep -n "class Area" backend/app/models.py` returns nothing). **Step 0
below checks this for real every time** — don't skip it and don't implement Phase 1 from inside
this skill if it's missing; that's separate, larger work the user would ask for directly.

## 1. Name
`add-region`.

## 2. Description
Fires on "add Austin as a test metro", "onboard a new region", "load tracts for \<metro\>", or
similar — the recurring task named directly in the workflow plan ("Pick a second test metro" is
listed as the user's part of Phase 1).

## 3. Body / instructions
0. **Check the precondition**: `grep -n "class Area" backend/app/models.py`. If empty, stop and
   tell the user Phase 1 hasn't landed yet — nothing to onboard a region into. Don't guess at
   commands that might exist; check the actual current API instead (`grep -rn "regions" backend/app/api/routes.py`)
   since the real implementation may differ from the plan's sketch by the time it's built.
1. **Confirm scope with the user** if not already given: which CBSA/metro, and whether this is a
   one-off test load or should become a **watched** region (watched regions get scheduled refreshes
   going forward — that's a standing config change, not a one-off action, see Guardrails).
2. **Load it**: call whatever the real Phase-1 endpoint/CLI turns out to be (re-derive the exact
   command from the actual code at step 0's grep results — don't trust this file's wording once
   Phase 1 code exists and may have drifted from the plan).
3. **Sanity-check coverage**: confirm tracts loaded, and that the national sources (ACS, FHFA HPI,
   Zillow, walkability, etc. per Phase 1) report non-empty coverage for the new region — a region
   with mostly-missing data will produce misleading neutral-filled scores.
4. **Run the backtest** for the new region and report the correlation number next to at least one
   already-working metro's (e.g. NYC) for comparison — a number with no baseline to compare against
   isn't useful on its own.
5. **Report**: tracts loaded, coverage gaps found, backtest correlation, and whether it was marked
   watched (only if the user said yes to that in step 1).

Expected output: a short report (tracts/coverage/backtest), not a claim of success without the
actual correlation number shown.

## 4. Gotchas
- *(none yet — this skill hasn't had a real run against live Phase 1 code. Add a dated entry the
  first time it's actually used.)*

## 5. Guardrails
- **Step 0's precondition check is not optional** — never proceed past it on the assumption Phase 1
  "probably" exists by now; check the actual file.
- **Marking a region "watched" needs an explicit yes**, separate from "load this region for
  testing" — it changes what runs on a schedule going forward (a standing-configuration change),
  not just a one-off read.
- Never call `api.rentcast.io` or any RentCast-touching code as part of loading a new region —
  RentCast is NYC-listings-specific and budget-capped; a new region's *area* data (tracts, ACS,
  FHFA, etc.) never needs it (see root `CLAUDE.md`'s hard rules).
- If national-source coverage for the new region is mostly missing, say so plainly rather than
  reporting a score that's actually just neutral-filled defaults.

## 6. Embedded skills and callouts
- **`add-data-source`** — if onboarding a region reveals a genuinely missing national source (not
  just a coverage gap in one that exists), that's a separate `add-data-source` job, not this
  skill's — don't build a new adapter from inside `add-region`.
- **`valuation-eval-gate`** — a different check (property-level valuation regression), not this
  skill's neighborhood-level backtest; don't conflate the two reports.

## 7. Memory allocation
Nothing needs to persist beyond the chat report — "watched" status lives in the `regions` table
itself (per the plan), which is this skill's actual source of truth once Phase 1 exists.

## 8. Frontmatter controls
Only `name` and `description`. No `context: fork` — the watched/not-watched decision in step 1
needs to happen in the main conversation. No `agent:`, not `background:`.

## 9. Sub-files, scripts and evals
- **Structural check**: shared linter —
  `python3 .claude/skills/tony-stark/scripts/structural_check.py .claude/skills/add-region/SKILL.md`.
- **Live run**: at creation time, the only real thing to invoke is step 0's precondition check —
  see [CHANGELOG.md](CHANGELOG.md) for its actual (negative) result. A full live run against a real
  region has to wait for Phase 1 to exist; re-run this skill for real the first time it's used and
  log what happened as a gotcha.

## 10. Versioning and iteration
Logged in [CHANGELOG.md](CHANGELOG.md). Expect this file to need real edits once Phase 1's actual
API shape is known — the plan is a sketch, not a guarantee of exact function/route names.
