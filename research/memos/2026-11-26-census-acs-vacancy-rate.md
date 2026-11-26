# Census ACS vacancy rate (B25002/B25004) — RECOMMEND

**What it is:** American Community Survey 5-year tables on occupancy/vacancy status, by census
tract. `B25002_001E` (total housing units) and `B25002_003E` (vacant) give an overall vacancy rate;
`B25004_002E` ("for rent") over `B25002_001E` gives a rental-specific vacancy rate. Same Census
Bureau API, same `CENSUS_API_KEY`, same tract geography the repo already pulls via `census_acs.py`.

**Why it could help:** `app/scoring/investment.py`'s `Assumptions.vacancy_pct` is a flat `0.05`
applied to every property, in every neighborhood, regardless of how tight or loose that
neighborhood's rental market actually is. A real, neighborhood-varying vacancy rate would let a
high-vacancy area's cash-flow and cap-rate projections come out worse (correctly) instead of being
scored identically to a tight market.

**Evaluation:**
- Granularity: tract → aggregated to NTA, same as every other ACS metric in this project.
- Coverage: national (ACS runs everywhere), so it holds up for the project's any-US-neighborhood
  goal without special-casing NYC.
- History: 5-year ACS releases back to 2009, comparable to the 10-year-lookback pattern
  `census_acs.py` already uses for other variables.
- Cost/license: free, Census Bureau public data, already-satisfied `CENSUS_API_KEY` requirement.
- Quantitative correlation: not run. `app/research/evaluate_series.py` (the Phase 4 tool the
  research-sources skill calls for) doesn't exist in this repo yet, so no lead/lag check against
  FHFA HPI or Zillow ZORI was possible this pass. The case for this one doesn't rest on predicting
  appreciation, though — it rests on replacing a constant that's currently wrong for every
  neighborhood except whichever one happens to sit at exactly 5% vacancy.

**Implementation note for whoever picks this up:** `vacancy_pct` in the investment math means
*rental* vacancy, so the numerator and denominator both need to stay within the rental-market
universe. The standard ACS rental vacancy rate (the same definition behind the Census's published
DP04 rental vacancy rate) is:

```
B25004_002E / (B25003_003E + B25004_002E + B25004_003E)
```

— for-rent-vacant units, divided by (renter-occupied + for-rent-vacant + rented-but-not-yet-occupied).
`B25003_003E` ("renters") is already in `census_acs.py`'s `VARS` dict. A simpler-looking
vacant/total-housing-units formula (dividing by `B25002_001E`, which includes owner-occupied units)
understates rental vacancy, badly so in owner-heavy neighborhoods — easy mistake to make since
`B25002` (the table already in `census_acs.py`'s neighborhood) looks like the obvious source, but
the denominator needs to come from the rental-specific tables instead.

**Recommendation: recommend.** Lowest-friction of the five candidates evaluated this run — it's a
few new variables on an adapter that already exists, not a new `Source` subclass, and it directly
fixes a known hardcoded assumption.
