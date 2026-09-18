# Current goal and next steps

Read this first each session. Update it at the end of any session that changes direction.
Phase status is NOT recorded here: run `cd backend && uv run python -m app.cli status`.
How work is saved and how to resume in a new window: `docs/SESSIONS.md`.

## Goal
NYC condo screener + deal-grade valuation, with research that keeps finding better criteria. The **Real Estate Tool**
artifact ("Glass Box Underwriting") is the approved UI design; the app is built from it (backend = the only calculation engine).

## UI lock
The first four tabs (Overview, Cash flow, Stress test, Assumptions) and the Stress test content are locked: additive changes
only, all work on **staging**, main only by promotion with the user's explicit OK. Staging also has Purchase and Saved tabs
(added 2026-09-18 with the user's approval).

## Artifacts
- Main (approved, locked): https://claude.ai/artifact/NsoGmcY54cCHhXCYy2HSvQ  (restore tag `artifact-main-1`)
- Staging (all new work): https://claude.ai/artifact/R7JtVjrZr6uPdW77WCzLm2, file `docs/artifact/staging.html`
- Registry: `.claude/artifacts.json`. Promote with `scripts/promote_artifact.py`, then ask before publishing to main.

## Latest saved state (2026-09-18)
- Staging = **version 11**, tag `staging-v11-2026-09-18` (earlier tags `staging-v5` to `staging-v10`, same date). Published with the
  platform `db` capability (Saved tab): leave `capabilities` out when republishing. How to change it: `docs/UI.md`, "Picking this up in a new window".
- **NOT yet on GitHub.** The user asked (2026-09-18) for everything to be pushed, but the push was blocked by the permission system
  because the repo (gd1288/nyc-screener) is **PUBLIC**, and `staging.html` embeds a RentCast listings snapshot and FRED figures. All work
  is committed locally with restore tags. To push, the user runs `git push origin valuation-phase-2a` and `git push origin --tags`
  from the project folder (after deciding about privacy). Autosave pushing stays OFF (`.claude/autosave.json`).
- Tests, lint and `app.cli status` were clean at the last commit. Memory: `docs/SESSIONS.md`, Claude's notes are backed up in
  `.claude/memory-backup/`.

## Needs the user's decision
0. **Push to GitHub** (see above): 36 commits and 8 tags are local only.
1. **GitHub repo is public.** Make it private (recommended) and set `"push": true` in `.claude/autosave.json`, or strip the
   embedded third-party data from `staging.html` (and history). Until decided, autosave does not push.
2. **Promote staging to main?** Staging bundles the result bar, screener drawer, market strip, links menu, sold view, Purchase and
   Saved tabs, and a fix for a scenario bug main still has (downside scenarios could beat base). Promoting changes all 18 scenario cards.
3. **`scripts/valuation-spike/`** (untracked leftover of the old proforma spike): keep or delete. Never `git add` the `scripts/` folder wholesale.
4. Which next feature: Formulas (with deep dives), Purchase follow-ups, or re-scaling the stress scenarios.

## Time-bound
- **Stale-listing sweeps:** RentCast allows one request per 24 hours. Run `cd backend && uv run python -m app.cli refresh rentcast_sweep`
  **after Sep 19 3:34 PM** and again **after Sep 20 3:35 PM**. A listing goes to Sold & off market after two misses in a row (one miss shows a
  "not in last check" chip). Then run `uv run python ../scripts/embed_screener.py` and republish staging. Budget used: 3 of 31 this month;
  from October the daily job leaves no room for sweeps under the 31 cap (fetch every second day, or raise `monthly_request_limit`, still under the free 50).

## Built on 2026-09-18 (so a new window knows the state)
- Backend: `valuation/purchase.py` (itemised closing costs, monthly obligations, ownership years, sale, scenarios via phases), `valuation/macro.py`,
  `pipeline/listing_urls.py`, `sources/fred.py` (mortgage rate, 10-year Treasury, FHFA NY index; the mortgage rate factor is live), RentCast update-only sweep,
  ACRIS sold-check fix (skips likely co-ops, deed must not precede the listing), `unmark_sold`. 367 tests.
- Staging UI: screener drawer with save, sold and off-market view, market strip, scenario reality check, links menu (official records, maps, search links,
  found listing pages for the top 10), Purchase tab, Saved tab. Legal review of every data source: `docs/DATA_LICENSES.md`.
- Process: main lock + guard hook, agents and boundaries (`.claude/agents/README.md`), criteria ledger, autosave hook, restore tags.

## Next features
- **Formulas feature** (`docs/plans/formulas-tab.md`, paste-ready prompt included): info marker on every number, inspector panel, Formulas tab with a
  deep-dive page per formula, backend-authored registry.
- **Purchase follow-ups** (`docs/plans/purchase-analysis.md`): 12-month cash calendar, printable view or Excel export, more custom-cost presets, formula markers on each line.
- **Re-scale the stress scenarios** using the FHFA history: 9 of 17 are harsher than New York's worst real price fall (-18.2%, Q1 2007 to Q2 2012).
- Anchor the exit cap and discount rate to the 10-year Treasury (needs an exit-cap input in the engine).

## Data and quality
- Search summaries suggest 5 of the 10 highest-scored listings may not be for sale (141 E 55th St 1A, 315 7th Ave 16C shows as a rental, 280 Rector Pl 9H,
  2 S End Ave 3W, 303 W 149th St 5F). Unverified: open their links. The sweeps above are the real check.
- Click an ACRIS link from the links menu and confirm it lands on the property's records (the URL pattern is unverified).
- Sources: read HUD's API terms then build it; email Apartment List for terms; RGB operating-cost table needs PDF extraction. Perplexity finder is **paused by
  the user** (code kept; to enable later: paid key in the project-root env file, read their Search Service terms, `app.cli find-listing-urls --limit 10`).

## Housekeeping
- Rotate the FRED key when convenient (it appeared in a transcript before log redaction was added).
- Review and merge branch `valuation-phase-2a` (Phases 2a to 4 and this session's work) to main via PR (#1 is open).
- Manual: Phase 0 items, value 2 or 3 real properties, confirm the research routine allowlist, pick a second metro.

## Ordered plan (from docs/PLAN.md and the architecture decision; verify progress with `app.cli status`)
1. Baseline: resolve `scripts/valuation-spike/`, restore tag `artifact-main-1` (done).
2. Backend single engine: scenario worlds/dials/events as backend data behind the API, one response schema, tax parity with the artifact's `model()`.
3. Staging polish, then promote to main, tag `artifact-main-2`, design-freeze note (`docs/design-freeze.md`).
4. Design tokens (colours and spacing) feeding Tailwind, after the freeze.
5. Port to Next.js one section at a time (Overview, Cash flow, Assumptions, Stress test, then Purchase and Saved), each checked at 1280px and 400px.
6. Research: `/propose-criteria`, then source the remaining gap factors (rent growth, vacancy, expense growth).
7. Viable-product check: pick a property, backend values it, Stress test on real numbers, Excel matches the screen, save and reopen by link.
Also: add a `stage` field (staged / main / app) to `criteria.yaml` `ui_suggestion` (with a validator test).

## Where things are remembered
- Rules `CLAUDE.md`; UI `docs/UI.md`; decisions `docs/DECISIONS.md`; sessions and restore `docs/SESSIONS.md`; data terms `docs/DATA_LICENSES.md`;
  plans `docs/plans/`; criteria `research/criteria.yaml`; progress `app.cli status`; preferences in Claude's memory notes (backed up in `.claude/memory-backup/`).
