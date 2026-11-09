# Census Bureau Building Permits Survey (BPS)

**Recommendation: recommend-with-caveats**

## What it is
The Census Bureau's monthly count of new privately-owned housing units authorized by building permits,
aggregated to county/place/metro/state/national. Roughly 9,000 permit-issuing jurisdictions respond to
the monthly survey (per HUD's SOCDS); about 900+ counties achieve 100% monthly reporting completeness,
with full nationwide county coverage otherwise guaranteed only in the annual rollup. HUD mirrors the
same underlying data in a web query tool (SOCDS Building Permits Database,
`socds.huduser.gov/permits`) back to January 1997.

## Why it could help
The project's existing supply-side growth signals (`housing_database`, `rezonings` in
`app/sources/development.py`) are NYC-specific Socrata/Open Data feeds. BPS is the closest free,
nationally-available analog — new permits as a leading indicator of future housing supply — and would
let the growth score's supply pillar work anywhere in the US, not just NYC.

## Evaluation
- **Coverage/granularity:** national; county, place, CBSA, state levels; ~900+ reporting
  jurisdictions.
- **Update frequency:** monthly, plus year-to-date and annual rollups.
- **Cost:** free.
- **License:** US government work / public domain.
- **History:** monthly back to January 1997 (per HUD's SOCDS mirror).
- **Access mechanics — the open question:** no documented REST API for *county-level* permits was
  confirmed in this run. The Census EITS time-series API appears to cover New Residential Construction
  (`eits/resconst`) only at the national/regional level, not by county. County-level access looks to be
  via direct bulk file download from census.gov/construction/bps's "Current Data" page (Excel format
  currently; the older ASCII/comma-delimited text files were discontinued after October 2019), or via
  HUD's SOCDS web tool over the same data.
- **Quantitative evaluation:** not run — `evaluate_series.py` doesn't exist yet.

## Caveats
- Needs a direct look at census.gov/construction/bps's "Current Data" page (or HUD SOCDS) to pin down
  the exact current file format/schema before writing an adapter — this would be a bulk-file adapter in
  the shape of `zillow_research.py`'s CSV fetch, not an API-key adapter.
- County-level permit counts give at most borough-level (5-way) differentiation inside NYC, since each
  borough is its own county — coarser than NTA; the real payoff is for the stated any-US-neighborhood
  goal, where county is often the finest free unit available anyway.

## Bottom line
Recommend as a candidate for the national-generalization roadmap, not as an urgent NYC-focused win.
Before implementing, spend a few minutes confirming the current file format directly on
census.gov/construction/bps or deciding to go through HUD's SOCDS tool instead.
