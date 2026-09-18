# Current goal and next steps

Read this first each session. Update it at the end of any session that changes direction.
Phase status is NOT recorded here: run `cd backend && uv run python -m app.cli status`.

## Goal
NYC condo screener + deal-grade valuation. The **Real Estate Tool** artifact
(https://claude.ai/artifact/NsoGmcY54cCHhXCYy2HSvQ, "Glass Box Underwriting") is the approved UI.

## UI lock
Tabs: Overview, Cash flow, Stress test, Assumptions. The Stress test tab (18 scenarios, Conditions,
Events, resolved assumptions, IRR range, diff table) stays as is. Only additive changes; read the
live artifact before every republish; never regenerate over it from a template.

## Artifacts
- Main (approved, locked): https://claude.ai/artifact/NsoGmcY54cCHhXCYy2HSvQ
- Staging (all new work): https://claude.ai/artifact/R7JtVjrZr6uPdW77WCzLm2, file `docs/artifact/staging.html`
- Registry: `.claude/artifacts.json`. Promote with `scripts/promote_artifact.py`, then ask before publishing to main.

## Where things are remembered
- Rules: `CLAUDE.md`. Progress: `app.cli status`. Criteria and decisions: `research/criteria.yaml`.
- Methodology reasoning: `research/memos/`. Approved UI copy: `docs/artifact/real-estate-tool.html`.
- Your preferences: auto-memory. Facts about the code live in git, not in memory.

## Open work (as of 2026-09-18)
1. Decide on `backend/app/valuation/proforma.py`: it does not exist on disk (only `taxes.py` does).
   Write it with tests and a `phases.yaml` check, or drop it.
2. Feed the artifact from backend scenarios (`scenarios.py`) instead of fixed 421 Harris numbers.
3. Stress test polish (proposed, not started): sticky result bar, grouped scenarios, reset button,
   risk colors, tornado chart, URL-shareable scenario, Excel export hook.
4. `scripts/valuation-spike/` is untracked: commit or delete.
5. Review and merge branch `valuation-phase-2a` (Phases 2a-4) to main via PR.
6. Manual: Phase 0 items, value 2-3 real properties, confirm research routine allowlist, pick a second metro.
