# BLS Local Area Unemployment Statistics (LAUS)

**Date:** 2026-10-29 · **Candidate JSON:** `research/candidates/bls-laus-unemployment.json` ·
**Recommendation: recommend**

## What it is
BLS's county/metro/city unemployment rate and labor-force series, published monthly (plus annual
revisions) with multi-decade history for most counties. Free registration key for the public
timeseries API (`bls.gov/developers`); bulk flat files are available with no key at all. The API
has a published 50-series-per-request limit.

## Why it could help
The `demographics` pillar in `backend/app/scoring/neighborhood.py` currently runs entirely on
Census ACS 5-year estimates — structurally sound (population, income, education, age mix) but
slow by design: a 5-year rolling estimate lags real conditions by construction. County-level
monthly unemployment, and especially its recent trend (e.g. year-over-year or 2-year change),
would add a timelier economic-momentum read alongside ACS's slower structural trends, and it's
available at county granularity nationwide, so it generalizes beyond NYC's 5 counties with no
NYC-specific assumptions baked in.

## Evaluation
- **Granularity:** county (also available at metro/city level).
- **Update frequency / history:** monthly, with multi-decade series for most counties.
- **Cost / license:** free; US government data, no commercial-use restriction found. Key
  registration mirrors the `census_api_key` pattern already in this codebase.
- **Rate limit:** 50 series per API request — a non-issue for NYC's 5 counties today; would need
  simple request batching if expanded to many counties for national coverage, which is an
  implementation detail for `add-data-source`, not a blocker.
- No quantitative correlation run yet (`app/research/evaluate_series.py` doesn't exist). Once it
  does, worth testing county unemployment trend against FHFA/Zillow appreciation — falling
  unemployment is a standard leading indicator for housing demand, so a measurable lead/lag would
  strengthen the case further.

## Recommendation
**Recommend implementing.** Nationally generalizable, free, low integration cost (same key
pattern as Census), and fills a real gap — the demographics pillar currently has no timely
economic signal, only ACS's lagged structural one.
