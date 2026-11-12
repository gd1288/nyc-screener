# BLS Local Area Unemployment Statistics (LAUS) — county unemployment rate

**Recommendation: recommend, moderate confidence.**

## What it is
BLS's monthly county-level unemployment rate and labor force series (LAUS program). Series IDs
follow a documented `LAUCN<state FIPS><county FIPS><measure code>` pattern. Available as rate-limited
JSON API (registration recommended) or as no-key bulk flat files at
`download.bls.gov/pub/time.series/la/`.

## Why it could help — and an important caveat
The growth pillar currently covers demographic trajectory via Census ACS
(`population_change_10y`, `income_cagr_10y`, `bachelors_share_change_10y`, `age_25_34_share`) but
has nothing on local employment. County unemployment/employment trends are a plausible leading
indicator for housing demand, and LAUS is free, national, monthly, and runs back decades.

But in NYC specifically, "county" means borough — all five boroughs are each their own county.
That's 5 LAUS values spread across roughly 200 NTAs. Since `score_frame` in `neighborhood.py`
scores NTAs relative to each other, a value shared by ~40 NTAs per borough is weak signal inside
NYC. The real case for this source is the project's *national* generalization goal: most other US
counties aren't subdivided into dozens of neighborhoods the way NYC boroughs are, so county-level
LAUS is a much more meaningful per-area signal in most of the rest of the country than it is here.

## Evaluation
- **Cost**: free. BLS's own FAQ says registration is required for API v2 to get useful rate limits;
  a third-party (unconfirmed against bls.gov) claims a keyless tier capped at 25 req/day vs.
  500/day registered.
- **License**: US government public data, no login wall on the bulk flat files, standard public-domain
  reuse.
- **Granularity**: county. In NYC this is just the 5 boroughs — weak intra-NYC signal. Elsewhere
  in the US, county-level is a much more meaningful neighborhood-area signal.
- **Update frequency**: monthly, with an annual benchmark revision.
- **History**: long monthly history in the flat files; exact API-exposed depth wasn't confirmed
  this pass.
- **Quantitative evaluation**: not run (`evaluate_series.py` doesn't exist yet in this repo).

## Recommendation detail
Implement against the **bulk flat files**, not the rate-limited JSON API — no key, no per-request
budget to manage, same pattern `zillow_research.py` already uses for a bulk pull. This sidesteps
the main uncertainty (whether a no-key API tier really exists and at what limit).

## Open questions
- Confirm the correct measure-code suffix for "unemployment rate" specifically (vs. labor force,
  employment level, unemployment level) in the `LAUCN...` series ID before writing an adapter.
- The bulk flat files are reported (unconfirmed this pass) to 403 requests without an identifying
  User-Agent header — confirm, and if real, use a generic one with no user-identifying information.
- A quarterly/annual refresh is probably enough — a given county's unemployment rate doesn't move
  fast enough to justify a monthly pull given this project's source-budget conventions.
- Decide whether to surface this inside NYC at all (weak, 5-borough signal) vs. gating it behind
  the screener actually covering other metros where county-level differentiates neighborhoods.

Candidate JSON: `research/candidates/bls-laus-county-unemployment.json`
