# EPA National Walkability Index

**Date:** 2026-10-12 · **Verdict:** Recommend · **Gap:** US-wide replacement for the NYC-only
infrastructure/transit pillar (`subway_access`, `planned_catalysts` are NYC MTA-specific).

## What it is
EPA's Smart Location Database rolled up into a single 1-20 walkability score per census block
group, nationwide. Sub-components cover residential/employment density, land-use diversity, street
design, and proximity to transit. Published by EPA's Office of Land and Emergency Management /
Smart Growth program.

- **URL:** https://www.epa.gov/smartgrowth/smart-location-mapping
- **Granularity:** census block group -- finer than this project needs (NTA), aggregates cleanly.
- **Coverage:** all 50 states + DC + PR.
- **Access:** bulk ZIP/shapefile download, or an ArcGIS REST MapServer endpoint
  (geodata.epa.gov) for querying without downloading the whole file. No API key, no login.
- **Cost:** free, no rate limit found.
- **License:** US government work, public domain.
- **Vintage:** built on 2019 Census block groups; EPA's catalog metadata was last touched Feb 2025,
  but there's no evidence of a newer *index* vintage -- this looks like a point-in-time structural
  index, not a refreshed time series.

## Why it could help
This is the only candidate found this run that actually matches the project's stated goal --
"generalizing to any US neighborhood" -- at a granularity finer than the project's own NTA unit,
for free, with no registration. Right now the infrastructure/transit pillar
(`backend/app/sources/transit.py`: `SubwayAccess`, `PlannedCatalysts`) only works in NYC because it
reads MTA-specific feeds. Outside NYC there is currently no fallback at all for that pillar. This
index would give every US neighborhood a comparable walkability/transit-access score.

## Evaluation
Not run through `app/research/evaluate_series.py` -- that script doesn't exist yet, and wouldn't
apply cleanly here anyway: this is a static composite index, not a growth-rate time series, so
there's no lead/lag correlation against FHFA HPI or ZORI to compute. Any evaluation here is
fundamentals-only (access, license, granularity, coverage), not statistical.

## Caveats
- It's a bundled composite (density + diversity + design + transit sub-scores). An implementer
  should decide whether to ingest the single composite score or the sub-scores separately --
  pulling sub-scores would fit this project's existing one-`MetricDef`-per-signal style better and
  keep the "why is this neighborhood's score X" explanation legible.
- Static/rare-refresh cadence (more like `nta_boundaries`' yearly schedule than a frequent-refresh
  source) -- don't expect this to move meaningfully between refreshes.

## Recommendation
**Recommend.** Clears every bar (free, no login, right granularity, genuinely national, public
domain) and fills a real, named gap. The only open design question is composite-vs-sub-score
ingestion, which is an implementation detail for whoever picks this up via `add-data-source`, not a
reason to hold it back.
