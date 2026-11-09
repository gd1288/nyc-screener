# BLS Local Area Unemployment Statistics (LAUS)

**Recommendation: recommend-with-caveats**

## What it is
BLS's monthly county-level (and other sub-state) unemployment rate and labor force series, covering
roughly 7,000 areas including every US county. Free via the BLS API v2 (a free registered key raises
the daily query cap; a bulk flat-file mirror at `download.bls.gov/pub/time.series/la/` needs no key at
all) and backed by decades of history for most counties.

## Why it could help
None of the project's current neighborhood-growth signals (`housing_database`, `rezonings` in
`app/sources/development.py`; `subway_access`, `planned_catalysts` in `app/sources/transit.py`;
`nypd_felonies`, `liquor_licenses`, `future_floodplain` in `app/sources/livability.py`) generalize
outside NYC — most are NYC Open Data / Socrata feeds (`planned_catalysts` is the exception: it reads a
local `catalysts.yaml` config, not Socrata). I also checked `census_acs.py`: it's ACS, which is national
tract-level data in principle, but the adapter is hardcoded to NYC's 5 counties and its `VARS` dict has
no employment-status variable. County unemployment via LAUS is a standard, free, nationally-available
economic-health input that would give the growth score something real to work with anywhere in the US.

## Evaluation
- **Coverage/granularity:** national, county (and other LAUS areas).
- **Update frequency:** monthly.
- **Cost:** free; bulk flat files need no key at all, API key (if used) is also free.
- **License:** US government work, public domain.
- **History:** decades for most counties.
- **Quantitative evaluation:** not run — `app/research/evaluate_series.py` (Phase 4) doesn't exist yet
  in this repo, and no correlation/lead-lag against FHFA HPI was computed for this candidate. Worth
  prioritizing for that evaluation once the harness exists, rather than asserting a relationship here
  without having tested it.

## Caveats
- NYC's 5 boroughs are each their own county (New York, Kings, Queens, Bronx, Richmond), so county-level
  LAUS does give borough-level differentiation inside NYC today — not zero signal, just coarser than
  the NTA granularity the other pillars use. Full non-NYC value is realized once the CBSA/area-model
  migration mentioned in `backend/CLAUDE.md` lands.
- Monthly cadence is finer than needed for a slow-moving structural indicator — a quarterly refresh
  would be plenty and cheaper.
- Confirm the current BLS API v2 endpoint and rate-limit numbers directly at bls.gov during
  implementation; this run relied on secondary sources for the specifics.

## Bottom line
Recommend. Inside NYC it only gives borough-level (not NTA-level) differentiation today, so it's a
modest win there, but it generalizes immediately to every other US county, which is the project's
stated goal — worth sequencing alongside the CBSA/area-model migration rather than treating it as an
NYC-focused win on its own.
