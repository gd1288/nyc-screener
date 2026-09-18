# Decisions log

Dated, one entry per decision that changes the plan, structure, or working rules. Newest first.
Add an entry (and update `docs/NEXT.md`) in the same session any such change is made. Facts about
what is built are NOT recorded here; run `app.cli status`.

## 2026-09-18
- **Stale listings: ACRIS fixed, RentCast recent-only sweep added.** The sold check no longer matches likely co-ops or
  deeds recorded before the listing date (it produced a false sale). RentCast has 8,472 active Manhattan-circle condos, so
  full sweeps are unaffordable on the free plan; `rentcast_sweep` asks only for the last 45 days (tracked listings are
  <=31 days old), never inserts, and only judges listings inside that window and circle. A first, oversized attempt spent
  1 request and correctly marked nothing (guard: a sweep that cannot cover everything proves nothing). Same shared
  budget and 24-hour gap as the daily job. The artifact flags a single missed check ("not in last check").
- **Perplexity paused by the user; code kept.** Listing pages for the top 10 properties were found instead with the
  assistant's web search tool (URLs only, same validation, never fetching listing sites). Building-level links must be
  a recognised building-page shape: a search returned another unit's page for 155 E 34th St, which the first, looser rule
  had labelled 'building'; it is now refused and covered by tests.
- **Listing pages found through Perplexity's Search API, links only.** The only automated caller is Perplexity (our own
  key); we never fetch listing sites (their terms forbid it), keep only validated https URLs from a domain allowlist
  that contain the street number and name, discard all result text, and cap spend at 300 requests a month (about
  $1.50). Dormant until `PERPLEXITY_API_KEY` is set and the user has read Perplexity's Search Service terms (their
  page blocked my fetch, so that part is unverified).
- **FRED series expanded** to the 10-year Treasury and the FHFA New York metro price index (both public domain,
  citation requested), stored as macro series. `app/valuation/macro.py` reports plain numbers from them (rates,
  spread, worst real price drawdown); no modelling. Case-Shiller rejected on license.
- **Artifact shows market context and a scenario reality check.** New York's worst price fall since 1975 was
  -18.2% (Q1 2007 to Q2 2012); on the sample deal 9 of 17 scenarios cut exit value by more than that, a sign
  the scenario magnitudes are harsh (though exit value there is NOI / cap rate, not a price index).
- **Listing links are built, never fetched.** Official NYC records, maps and search links; the user can save the
  real listing URL. No listing has a URL in the database, so this is the only route to it without scraping.
- **Free data sources: legal review before ingestion** (docs/DATA_LICENSES.md). Built FRED mortgage rate (Freddie
  Mac, attribution, personal use). Rejected Redfin (terms forbid automated access) and Walk Score (free tier is
  consumer-facing only). Held Apartment List (no published terms). HUD and the NYC RGB operating-cost index are
  approved but unbuilt (HUD terms unreadable by tooling; RGB needs PDF extraction). Rule: no new source without a
  DATA_LICENSES row, and never automate against a site whose terms forbid it.
- **Macro series live in `app_settings` as `macro:<SERIES>`,** exposed as `MarketContext.macro`, so a national time
  series needs no schema change. A factor stays a gap (fixed default) until its series has enough history.
- **Screener drawer in the artifact.** A "Browse screener" drawer opens from the deal header (the four
  tabs are unchanged). The artifact cannot call the backend, so listings are an embedded snapshot written by
  `scripts/embed_screener.py` from the backend's own analysis; rent and property tax are estimates for all
  246 listings and stay flagged unbacked once pulled. The screener's own IRR/cap are shown beside this tool's
  because the two models differ by design (see the parity item in NEXT.md).
- **Bug found in the approved main artifact, fixed in staging only:** scenario dials and events are
  adjustments but were passed to `model()` as absolute inputs (a "+1.0 pt rate" ran as a 1.0% rate). On the
  sample deal "Higher for longer" showed 21.3% against a 13.0% base; corrected it is 5.1%, and "Hard landing"
  goes from 7.1% to no computable IRR. Main still shows the old numbers until staging is promoted, which
  will change all 18 scenario cards. Regression check: downside worlds never beat base, upside never below.
- **UI knowledge lives in `docs/UI.md`.** Structure, components, checklist and changelog for the
  artifact; CLAUDE.md points to it. Why: UI facts were spread over a memory note, NEXT.md and this log,
  and auto-memory is per-machine, so a new session could miss them. Git-tracked docs reach every
  session and worktree.
- **Result bar is one sticky element for all four tabs,** content chosen by `TAB` in `bar()`. Added to
  staging with Read this first, cash flow insight, scenario summary, reset, per-card DSCR, tornado.
- **Backend is the only calculation engine.** The artifact's in-page `model()` is a prototype (it also
  uses flat 25%/23.8% sale-tax rates, unlike `taxes.py`); the app calls the backend. A parity test
  will compare them. Why: two engines silently diverge.
- **Product form: extend the existing Next.js app, local only, audience is the user.** No hosting,
  auth or database migration for now. Artifacts (staging -> main) are design references for it.
- **Fonts: keep Geist in the app;** port only colors and spacing as tokens. Why: simplest, fewest tokens.
- **Ordered plan recorded in docs/NEXT.md;** viable-product definition is its step 7.
- **claude-mem disabled** (user-level `~/.claude/settings.json`). Memory is now CLAUDE.md, NEXT.md,
  this log, `research/criteria.yaml`, `app.cli status`, and auto-memory. Why: it recorded claims
  that later proved false (it reported `proforma.py` as built) and stalled on quota.
- **Main artifact is locked; all new work goes to the staging artifact.** Enforced by
  `.claude/hooks/artifact-guard.sh` and `.claude/artifacts.json`. Promote with
  `scripts/promote_artifact.py`, then publish to main only on the user's explicit say-so. Why: a
  backend rebuild had silently replaced the approved Stress test UI.
- **Criteria ledger** (`research/criteria.yaml`, validated by `app.cli criteria`) links research to
  approval to valuation factor to UI. Only the user moves entries to approved/rejected/live.
- **Agent boundaries live in config** (`.claude/agent-boundaries.json`), not in shell code, so adding
  an agent is a checklist (`.claude/agents/README.md`), not a hook edit.
- **criteria-proposer agent added.** It may suggest UI changes only for the staging artifact.
- **Product direction:** an interactive UI for valuation and screening; a backend that keeps
  researching, proposes new criteria that refine the valuation, and those flow into the UI. This is
  the baseline; layers get added on top.
