# EPA National Walkability Index

**Date:** 2026-10-12 · **Verdict:** Recommend with caveats · **Gap:** US-wide replacement for the
NYC-only infrastructure/transit pillar (`subway_access`, `planned_catalysts` are NYC MTA-specific).

## What it is
EPA's Smart Location Database rolled up into a single 1-20 walkability score per census block
group, nationwide. Sub-components cover residential/employment density, land-use diversity, street
design, and proximity to transit. Published by EPA's Office of Land and Emergency Management /
Smart Growth program.

- **URL:** https://www.epa.gov/smartgrowth/smart-location-mapping
- **Granularity:** census block group -- finer than this project needs (NTA), but does **not**
  aggregate cleanly: this vintage uses 2010-Census block-group geography, while the project's NTAs
  are the 2020 vintage (per `census_acs.py`'s docstring). Block-group IDs won't nest directly into
  2020 NTA codes -- a spatial/area-weighted join against the index's shapefile geometries (`shapely`
  is already a dependency) would be needed instead of a plain code lookup.
- **Coverage:** all 50 states + DC + PR per the data.gov catalog description (not independently
  re-verified this run).
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
Not run through `app/research/evaluate_series.py` -- that script doesn't exist yet. This is testable,
just not with that script's lead/lag design (built for growth-rate series): as a static level it
should instead be tested cross-sectionally against later ZHVI/ZORI growth, the same way
`backtest.py` already tests the valuation-gap level against next-period appreciation (see the
Spearman-correlation comment above `DEFAULT_WEIGHTS` in `neighborhood.py`). That test wasn't run
this round -- this is a note on how to evaluate it, not a result, so there's no statistical evidence
behind this recommendation yet.

## Caveats
- **No correlation evidence yet** -- see above. The fundamentals (access, license, granularity,
  coverage) check out, but nobody has shown this index actually predicts appreciation here.
- **Geography mismatch.** 2010-vintage block groups vs. this project's 2020 NTAs -- needs a spatial
  join, not a code lookup (see Granularity above).
- It's a bundled composite (density + diversity + design + transit sub-scores). An implementer
  should decide whether to ingest the single composite score or the sub-scores separately --
  pulling sub-scores would fit this project's existing one-`MetricDef`-per-signal style better and
  keep the "why is this neighborhood's score X" explanation legible.
- Static/rare-refresh cadence (more like `nta_boundaries`' yearly schedule than a frequent-refresh
  source) -- don't expect this to move meaningfully between refreshes.

## Recommendation
**Recommend with caveats.** Strongest fit found for the stated gap on fundamentals (free, no login,
block-group granularity, genuinely national, public domain), but not an unqualified pick: it has no
correlation evidence behind it yet and needs a real geography join, not a code lookup, before it's
usable. Both are solvable by whoever implements it via `add-data-source`, not reasons to reject --
just reasons not to oversell it as a slam dunk.
