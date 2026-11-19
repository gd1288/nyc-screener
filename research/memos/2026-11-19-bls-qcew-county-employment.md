# BLS QCEW County Employment & Establishment Counts

**Recommendation: conditional - don't build yet, revisit once `evaluate_series.py` exists**

## What it is
The Quarterly Census of Employment and Wages: total covered employment and establishment counts
by county and NAICS industry, published by BLS as open flat-file data (not a key-gated REST API).
Covers every US county. Roughly a 5-6 month publication lag per quarter.

## Why it could help
The project's `demographics` pillar (`backend/app/scoring/neighborhood.py`) currently only has
Census ACS population/income/education/age metrics - no direct jobs or employment-growth signal,
which is a standard real-estate demand driver absent from the current Growth Score.

## Evaluation against the project's bar
- **Free, no trial, no key**: yes - flat CSV/open-data files at a documented BLS URL convention.
- **License**: public-domain federal statistics, no restriction found.
- **Granularity**: county-level, so it's National and would need the same kind of
  tract/county -> NTA apportionment that `census_acs.py` already does for ACS tracts (precedent
  exists, but it's still new glue code, not a drop-in Socrata call).
- **History**: county series run back to the 1990s - plenty for a 10-year backtest.
- **Lag/leading-ness concern**: QCEW is a lagging confirmation of what already happened
  economically (plus its own 5-6 month publication delay), not a forward-looking signal. The
  project's own backtest (`backend/app/scoring/backtest.py`) already found trailing momentum
  metrics are mostly mean-reverting/negative predictors (hence `momentum` weight of only 5 vs.
  `valuation` at 25) - an employment-growth metric risks landing in the same bucket rather than
  adding real predictive lift.

## Recommendation detail
Don't build this now. It's a real, free, national, well-documented government source and would
plug an actual pillar gap, but:
1. Implementation cost is nontrivial (large per-area file downloads, a new county->NTA crosswalk).
2. There's a real risk it just restates momentum the project has already found weak, rather than
   adding signal like the valuation-gap metrics did.

Once `app/research/evaluate_series.py` exists (Phase 4 per the research-sources skill), re-run this
candidate and actually compute the lead/lag correlation against FHFA HPI / Zillow ZORI before
spending engineering time on the crosswalk work. If it shows real lead time, revisit as a
`recommend`; if not, drop it.
