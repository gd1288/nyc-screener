# Census Bureau: Building Permits Survey (BPS)

**Recommendation: Approve — highest priority this run (alongside the mortgage-rate candidate).**

## What it is
The Census Bureau's monthly survey of new privately-owned residential housing units authorized
by building permit, aggregated to county/CBSA/state/national. Free static downloads at
`https://www.census.gov/permits`, no account or key required. Monthly files cover ~900
permit-reporting counties; the annual file covers essentially all US counties.

## Why it could help
This project's stated goal is a screener that generalizes "to any US neighborhood and property
type," but the only development-pipeline signal currently wired up —
`backend/app/sources/development.py`'s `HousingDatabase` — queries NYC's own DCP Housing
Database via Socrata and is keyed to 2020 NTA codes. Outside NYC, the Growth Score has no
supply-pipeline input at all. BPS is the natural national equivalent: same underlying concept
(permitted/pipeline housing units), available for every US county.

## Evaluation
- **Coverage/granularity**: national, county level (monthly: ~900 counties; annual: effectively
  all counties with a permit-issuing jurisdiction).
- **Update frequency**: monthly, with an annual rollup.
- **History**: varies by geography; county-level annual data goes back to the 1980s.
- **Cost / access**: free, static file download, no login.
- **License**: federal statistical publication, public domain.
- **Granularity tradeoff**: county is coarser than the NYC NTA-level signal it would sit next
  to. That's an acceptable tradeoff per this project's own stated preference for national
  coverage over NYC-only granularity, and still far more granular than state/national.
- **Quantitative correlation**: not run — would be a Phase 4 (`evaluate_series.py`) exercise,
  and that tooling doesn't exist in this repo yet. Qualitatively, more permitting activity is a
  standard leading indicator of future supply/completions, which is exactly what the existing
  NYC `HousingDatabase` source is used for.

## Recommendation
Approve. This is the single best fit this run for the project's explicit "any US neighborhood"
goal — it's the one gap found where a currently NYC-only signal has a direct, free, federal
national equivalent, not just an adjacent/overlapping series.
