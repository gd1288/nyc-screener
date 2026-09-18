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
- UI: `docs/UI.md`. Rules: `CLAUDE.md`. Progress: `app.cli status`. Criteria and decisions: `research/criteria.yaml`.
- Methodology reasoning: `research/memos/`. Approved UI copy: `docs/artifact/real-estate-tool.html`.
- Your preferences: auto-memory. Facts about the code live in git, not in memory.

## Latest saved state
Staging = version 10 (tag `staging-v10-2026-09-18`; earlier: `staging-v9-2026-09-18`, `staging-v8-2026-09-18`, `staging-v7-2026-09-18`, `staging-v6-2026-09-18`, `staging-v5-2026-09-18`; file `docs/artifact/staging.html`). How to change it from a new window:
`docs/UI.md`, section "Picking this up in a new window". Main = `artifact-main-1`, unchanged, promotion pending your decision.

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
- **Stale-listing checks (applied 2026-09-18).** ACRIS fix done: the sold check now skips likely co-ops and only accepts a
  deed dated on or after the listing date; listing 55 (121 W 17th St #3B, a false "sold") was restored to active. RentCast
  finding: the Manhattan circle has 8,472 active condo listings, so a full sweep would need 17 requests. Instead a
  **recent-only sweep** exists: `rentcast_sweep` in `sources.yaml` (manual-only, `days_old: 45`, update-only, never adds
  listings, only judges tracked listings listed within the window). Run it by hand:
  `cd backend && uv run python -m app.cli refresh rentcast_sweep`. The 24-hour request gap means the first real sweep can
  run **after Sep 19 3:34 PM**, the second **after Sep 20 3:35 PM** (a listing goes off market after two misses in a row;
  after ONE miss it shows a "not in last check" chip in the artifact). Budget used this month: 3 of 31. From October the
  daily job (about 31 requests) leaves no room for sweeps under the 31-request cap, so before then either fetch every
  second day or raise `monthly_request_limit` (still under the free plan's 50).
- **Purchase property page (designed, awaiting the user's 5 answers):** `docs/plans/purchase-analysis.md` has four options (recommended: a
  Purchase plan tab), the cost data the tool already has, and a paste-ready prompt.
- **Formulas feature (planned, not started; now includes deep-dive pages per formula):** `docs/plans/formulas-tab.md` has the design, the phases and a paste-ready
  prompt for a new window (info marker on every number, formula inspector panel, Formulas tab, backend-authored registry).
- FRED is live (mortgage rate, 10-year Treasury, FHFA New York price index). Rotate the FRED key at some point: it appeared
  in a transcript before log redaction was added. Key lives in the project-root `.env`.
- Data-source follow-ups (see docs/DATA_LICENSES.md): read HUD's API terms, then build it; email Apartment List for
  terms; the RGB operating-cost table needs PDF extraction.
- **Data-quality flag from the link search:** search summaries suggest 5 of the 10 highest-scored screener listings
  may not be for sale now (141 E 55th St 1A, 315 7th Ave 16C shows as a rental, 280 Rector Pl 9H, 2 S End Ave 3W,
  303 W 149th St 5F). Unverified (pages were not opened); open the links to check. RentCast's feed can go stale, so
  consider a freshness check (last seen, ACRIS sold) before trusting the top of the ranking.
- Perplexity finder is PAUSED by the user (code kept). Found links so far were added by hand with the search tool
  (`listing_urls.record_found`), for the top 10 only. To turn Perplexity on later: sign up for Perplexity's API (paid, about $5 per 1,000 requests), read the Search
  Service terms, put `PERPLEXITY_API_KEY=` in the project-root `.env`, then run
  `cd backend && uv run python -m app.cli find-listing-urls --limit 10` and check the results by hand before running the
  rest, then `uv run python ../scripts/embed_screener.py` and republish staging.
- **Listing links** are built in staging (official records, maps, search links, save-your-own). Better link finding via
  Perplexity's Search API was requested 2026-09-18: see docs/DATA_LICENSES.md for the legal review and status. The ACRIS
  link format is unverified: click one and confirm. Re-scale the stress scenarios using the FHFA history (9 of 17 are harsher
  than New York's worst real price fall).
- **Decide on promoting staging to main** (deferred by the user). Staging now has the result bar, the screener
  drawer, and a fix for a scenario bug that main still has (downside worlds could show HIGHER returns than base).
  Promoting will change the numbers on all 18 scenario cards. Run `scripts/promote_artifact.py` first.
- Screener drawer follow-ups: refresh the snapshot with `scripts/embed_screener.py`; the live Next.js version
  should use `/api/valuation/importable-listings` and `/properties/from-listing/{id}` (already exist).
- Review and merge branch `valuation-phase-2a` (Phases 2a-4) to main via PR.
- Manual: Phase 0 items, value 2-3 real properties, confirm research routine allowlist, pick a second metro.
