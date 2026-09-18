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

## Direction (decided 2026-09-18) - see docs/ARCHITECTURE.md
Staging artifact = design lab. Main artifact = signed-off design spec. The app (existing Next.js
frontend, run locally, audience: the user only) is built from main's design but uses the backend as
the ONLY calculation engine. Hosting is out of scope for now. Fonts: keep Geist in the app; port
only colors/spacing tokens.

## Ordered plan (work top to bottom; steps marked || can run in a second window)
1. Baseline: resolve `scripts/valuation-spike/` (commit or delete), tag `artifact-main-1`.
2. Backend single engine (Window B, Opus): plan first, then scenario worlds/dials/events as backend
   data + API, one response schema, tax parity with the artifact's model(). Gate: parity test passes.
3. || Staging polish (Window A, Sonnet): one feature at a time, incl. a "sample deal" label. Then
   promote to main, tag `artifact-main-2`, write the design-freeze note (docs/design-freeze.md).
4. Design tokens: extract colors/spacing to one file feeding Tailwind (after step 3's freeze).
5. Port to Next.js one section at a time: Overview, Cash flow, Assumptions, then Stress test. Each
   checked with /verify-viewports (1280px and 400px) against main. Needs steps 2 and 3 done.
6. || Research (Window C, Sonnet): /propose-criteria, then source the four gap factors, mortgage rate first.
7. Viable-product check (all must pass): pick a property -> backend values it -> Stress test on real
   numbers -> Excel matches the screen -> save and reopen by link. Add each as a phases.yaml check.
Also: add a `stage` field (staged / main / app) to criteria.yaml `ui_suggestion` (with a validator test).

## Other open work
- Review and merge branch `valuation-phase-2a` (Phases 2a-4) to main via PR.
- Manual: Phase 0 items, value 2-3 real properties, confirm research routine allowlist, pick a second metro.
