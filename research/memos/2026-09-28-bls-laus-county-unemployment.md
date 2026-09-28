# BLS Local Area Unemployment Statistics (LAUS), county unemployment rate

**Recommendation: recommend-with-caveats**

## What it is
Monthly county-level unemployment rate and labor force size from the BLS LAUS program. Free,
public-domain (US federal government work), no login required for basic use (API v1: 25
queries/day, no key; v2: free registered key, 500/day). County series commonly run back into the
1990s. Not seasonally adjusted below the state level.

## Why it could help
Nothing in this codebase currently tracks an employment/labor-market signal. The demographics
pillar (`backend/app/scoring/neighborhood.py`) has `income_cagr_10y` from Census ACS, but that's a
slow-moving 5-year-rolling-estimate series released annually. LAUS unemployment would be a
faster, monthly complement -- a genuine "is the local economy getting stronger or weaker right
now" signal that nothing else in the pillar set currently provides.

It also fits the county granularity already used by `app/sources/census_acs.py` (same 5-county
FIPS list: 005/047/061/081/085 for NYC's boroughs), and it fits the existing `neighborhood` source
kind cleanly -- no new architecture needed, unlike the FRED mortgage-rate candidate evaluated
alongside this one.

## Evaluation
- **Cost**: free, public domain.
- **License**: no restriction on commercial/product use (US government work).
- **Granularity**: county. For NYC, each of the 5 boroughs *is* a county, so coverage is complete
  but coarse -- one number shared by all ~40 NTAs within a borough, versus every other metric in
  the demographics pillar being resolved at the individual-neighborhood level via tract
  aggregation.
- **History**: sufficient (1990s+ for most counties).
- **Correlation**: not computed -- `app/research/evaluate_series.py` doesn't exist yet in this
  repo (same limitation as the FRED candidate this run). Should be checked once it's built, to see
  whether the monthly cadence actually adds predictive value over the existing annual ACS income
  growth metric, or is redundant with it.

## Concern: granularity mismatch
This is the honest reason for "recommend-with-caveats" rather than a flat recommend. Sharing one
value across every neighborhood in a borough works against the scoring model's design principle
(`backend/CLAUDE.md`: "Every metric becomes a percentile within its comparison set... never a raw
value... mixed across incomparable markets") in spirit, if not in mechanism -- it would compress
to essentially a 5-way borough signal riding inside an NTA-level pillar, likely contributing very
little differentiation within a borough where development/transit/demographics pillars are doing
real work.

It's a much better match for `backend/CLAUDE.md`'s mentioned (in-progress) area-model migration:
"today: all NYC neighborhoods; after the area-model migration: the area's CBSA" -- in a lot of
non-NYC markets, county *is* the natural unit (a small city/suburb won't have NTA-equivalent
tracts), so this candidate is worth keeping on file for that migration rather than either
implementing it now at diluted NYC resolution or discarding it.

## Bottom line
Real gap, free and unrestricted source, fits the existing source-kind contract with no schema
changes -- but the value-add at NYC's neighborhood resolution is genuinely uncertain until
measured, and the natural moment to add it is after the area-model migration rather than before.
