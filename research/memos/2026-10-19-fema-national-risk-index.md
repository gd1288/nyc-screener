# FEMA National Risk Index (NRI) — research memo

**Date:** 2026-10-19 · **Candidate file:** `research/candidates/fema-national-risk-index.json` · **Recommendation: recommend**

## What it is
FEMA's composite natural-hazard risk score, published at county and census-tract level for all
50 states, DC, and US territories. Covers 18 individual hazard types (flood, wildfire, heat,
wind, winter weather, earthquake, etc.) plus one composite Risk Index score per geography,
combining expected annual loss, social vulnerability (CDC/ATSDR SVI), and community resilience
(USC HVRI). Free bulk geodatabase/shapefile/CSV downloads, no login; public ArcGIS Online layers
also queryable with no key.

## Why it could help
`app/sources/livability.py`'s `FutureFloodplain` source is a single NYC Open Data layer (dataset
`27ya-gqtm`, a 2050s floodplain projection) with no equivalent anywhere outside NYC. The project's
own stated goal ("generalizing to any US neighborhood and property type" — CLAUDE.md's first
line) breaks immediately for the livability/climate-risk pillar the moment the screener points at
a non-NYC market: there's no flood signal, and no other hazard signal (wildfire, heat, wind) at
all, anywhere else in the country.

NRI is the natural national superset: flood is one of its 18 hazard components, at a finer grain
(census tract) than most of this project's other "national-aspiration" sources, plus the hazards
that matter in non-NYC markets (wildfire in the West, hurricane wind on the Gulf/Atlantic coasts,
etc.) that NYC-specific data simply has no version of.

## Evaluation
- **Geography:** county and census tract, nationwide.
- **Update frequency:** periodic re-releases, not a fixed cadence. The most recent release
  confirmed in search results was dated March 2023 — this needs re-checking against the live site
  before implementation, since a newer vintage may well have shipped since.
- **History:** not applicable — each release is a point-in-time composite score, not a
  time series. This makes it unsuitable for the backtest (unlike FHFA HPI); its value here is as
  an independent risk/livability pillar input, not a growth predictor.
- **Cost/license:** free, public domain, no login, no rate limit on the bulk download.

## Caveats / what to re-check before implementing
- Could not reach hazards.fema.gov directly this run (sandbox DNS/proxy issue) — confirm the
  current release vintage and update cadence before building on the March 2023 figure found via
  search.
- FEMA's shapefiles use `-9999` as an explicit null sentinel. An adapter must filter that out, or
  it will silently corrupt percentile scoring in `scoring/neighborhood.py` (a `-9999` reads as an
  extreme real value otherwise).
- This is a snapshot, not a series — don't try to feed it into the backtest alongside FHFA HPI;
  it's a different kind of input (cross-sectional risk vs. time-series growth).

## Recommendation
**Recommend.** Best available national-scale climate/hazard risk layer, directly fixes the
"NYC-only" ceiling on `FutureFloodplain`, and comes at finer geographic grain (tract) than most of
this project's other sources. Implement as a new source in the livability pillar, separate from
(not replacing) `FutureFloodplain`, once the release-vintage caveat above is resolved.
