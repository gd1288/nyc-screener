# Census Bureau Building Permits Survey (BPS)

**Candidate file:** `research/candidates/census-building-permits-survey.json`
**Recommendation: recommend (scoped as a national fallback, not an NYC replacement)**

## What it is

The Census Bureau's monthly survey of new privately-owned residential construction permits,
published down to the county and permit-issuing-place level, with detailed CSV/Excel files for
2019-present and state/MSA text files back to 1995. No login or API key needed for the bulk flat
files; a free key (same `census_api_key` pattern this repo already has) only matters if pulling
through the generic `data.census.gov` API instead.

## Why it could help

`backend/app/sources/development.py` currently supplies the Growth Score's "development momentum"
pillar via `HousingDatabase` and `Rezonings` — both built against NYC's own DOB/DCP open-data
endpoints (filing status, rezoning history). That's a rich, NYC-specific signal with no equivalent
in a city that doesn't publish the same open-data feeds. BPS permit counts are a coarser version of
the same underlying idea — new units authorized — but they exist everywhere, because every
jurisdiction's permits roll up into this one federal survey.

## Evaluation

- **Measures:** new residential construction permits (single-family and multi-family unit
  counts), by county/place.
- **Granularity:** county and sub-county permit-issuing place; state/CBSA roll-ups also available.
- **Update frequency:** monthly, plus year-to-date and annual county files.
- **Cost:** free; bulk downloads need no key at all.
- **License:** US government work, public domain, no commercial-use restriction.
- **History:** detailed county/place files 2019-present on the current site; state/MSA text files
  back to 1995 for anyone needing a longer backtest window.

No quantitative correlation run — `app/research/evaluate_series.py` doesn't exist yet. This one
is also a harder fit for that kind of evaluation than the other three candidates: permit counts
are a supply-side leading indicator, not a price series, so "correlation with FHFA HPI growth"
isn't quite the right test — lead/lag against *future* price growth (does a permit surge precede
appreciation, by how many quarters) would be the more meaningful test once the tooling exists.

## Recommendation

Implement, scoped explicitly as the generic/national fallback for the development pillar — not a
replacement for the NYC-specific sources, which carry more detail (rezoning status, filing
pipeline stage) that BPS's raw permit counts don't capture. The main implementation cost is schema
work: it needs its own adapter mapping county/place permit data onto whatever neighborhood
geography a non-NYC market uses, separate from NYC's own NTA-based pipeline.
