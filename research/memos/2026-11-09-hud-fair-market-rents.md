# HUD Fair Market Rents (FMR)

**Recommendation: recommend**

## What it is
HUD's Fair Market Rents are the annually-published 40th-percentile gross rent (rent + utilities) for
every US county, CBSA, and HUD metro FMR area, broken out by unit size (efficiency through 4BR). HUD
exposes them through a free API (token via huduser.gov registration): a state endpoint returning every
county/metro in a state, and an entity endpoint by county FIPS or CBSA code. Static CSV/Excel schedules
per fiscal year are also published directly on huduser.gov as a fallback if the live API's historical
range turns out to be thin.

## Why it could help
The project's growth score and investment math (`backend/app/scoring/investment.py`) need a rent
benchmark for yield/cash-flow estimates. Today that comes from Zillow ZORI (ZIP-level, mapped to NTA via
`zillow_research.py`) or RentCast listings, which is budget-capped at 31 requests/month. ZORI's own
upstream CSV is national, but `zillow_research.py` filters it down to NYC's 5 counties
(`NYC_COUNTIES`) as currently written. I also checked `census_acs.py`, since ACS is a national,
tract-level dataset in principle — but as implemented it's hardcoded to the same 5 NYC counties
(`COUNTIES`, `state:36`) and its `VARS` dict has no rent field at all (no `B25064`-type variable; it
pulls population, income, education, age, and tenure only). So, as the code stands today, there is no
rent benchmark anywhere outside NYC in this project — not because the underlying data doesn't exist
nationally, but because neither existing adapter is wired that way. FMR is government-published, covers
literally every US county out of the box, and needs no per-request budget management the way RentCast
does.

## Evaluation
- **Coverage/granularity:** national, county/CBSA (finer "Small Area FMR" exists for ~80 metros at ZIP
  level).
- **Update frequency:** annual.
- **Cost:** free; API requires a free token (no payment, no trial window).
- **License:** a third-party API aggregator (apis.io) lists it as Public Domain, linking to HUD's own
  API terms — not independently re-checked against huduser.gov's ToS page directly in this run.
- **History:** static annual schedules go back decades on huduser.gov; how many years the *live API*
  itself exposes wasn't confirmed and should be checked during implementation.
- **Quantitative evaluation:** `app/research/evaluate_series.py` (Phase 4) doesn't exist yet in this
  repo, so no correlation/lead-lag against FHFA HPI or Zillow ZORI was computed. This is a level
  benchmark (40th-percentile rent), not a growth-rate series, so correlation evaluation would need to
  be against rent *levels*, not FHFA's price-growth series — worth deciding how evaluate_series.py
  should handle level-vs-growth series when that phase is built.

## Caveats
- Re-confirm the API's historical depth and the official license page before implementing.
- This is a regulatory rent-setting number, not a transaction-based market rent — best used as a level
  benchmark alongside Zillow ZORI's trend, not a replacement for it where ZORI already has coverage.

## Bottom line
Recommend pursuing this as the next `add-data-source` candidate. It's free, public-domain-licensed per
available evidence, genuinely national, and fills a real, currently-unaddressed gap (rent benchmark
outside NYC / outside RentCast's budget) rather than duplicating what Zillow Research already provides.
