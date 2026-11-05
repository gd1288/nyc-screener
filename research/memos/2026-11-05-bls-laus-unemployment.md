# BLS LAUS — county/metro unemployment rate

**Weak recommend — lower priority than FRED mortgage rate and FHFA HPI.**

## What it is
BLS's Local Area Unemployment Statistics: monthly unemployment rate and labor force size for every
US county, metro area (CBSA), and many cities, free via the BLS Public Data API.

## Why it could help
The demographics pillar covers population, income, education, and age mix (via Census ACS), but
nothing about current labor-market trajectory, and — same theme as the other national candidates
this run — every existing demographics/development/quality source is NYC-specific. Employment
growth is a standard leading indicator for housing demand.

## Evaluation
- **Coverage/granularity**: national, county and metro — genuinely nationwide, a real plus.
- **Update frequency**: monthly, with annual averages.
- **History**: multi-decade for most areas.
- **Cost/license**: free; public API works without a key (25 queries/day) or with a free
  registration key (500/day, bulk multi-series requests) — same pattern as the
  `census_api_key`/`rentcast_api_key` sources already in this project.
- **Quantitative evaluation**: not run (no `evaluate_series.py` yet).

## Recommendation
Worth doing, but after the two higher-value candidates. Unlike Census ACS variable codes, LAUS
series IDs are assembled per-area (no single lookup table the way ACS table/variable codes work),
so the adapter is more fiddly to get right, and the marginal signal over ACS income-growth trends
is smaller than what FRED/FHFA add. Revisit once the area-model migration (any-US-county support)
is further along and there's a concrete non-NYC area to validate against.
