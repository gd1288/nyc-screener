# FEMA National Risk Index (NRI)

**Date:** 2026-10-29 · **Candidate JSON:** `research/candidates/fema-national-risk-index.json` ·
**Recommendation: recommend**

## What it is
FEMA's National Risk Index: a composite, census-tract-level score covering 18 natural hazards
(riverine/coastal flooding, hurricane, wildfire, tornado, winter weather, earthquake, etc.) for
every county and tract in the US. Free bulk downloads (geodatabase/shapefile/CSV) and a keyless
ArcGIS FeatureServer. Versioned releases (most recent found in search results: December 2025,
v1.20.0) rather than a monthly/quarterly time series.

## Why it could help
The screener's `flood_risk_penalty` pillar (`backend/app/sources/livability.py:FutureFloodplain`)
currently pulls NYC's own "Future Floodplain 2050s" dataset from NYC Open Data
(`27ya-gqtm`) — a NYC Panel on Climate Change product that, by construction, exists nowhere else.
`CLAUDE.md` states this project's goal is "generalizing to any US neighborhood," but the climate
pillar as built today has no path to do that: there's no equivalent dataset to swap in for a
different city. NRI is the one candidate reviewed this run that is itself a drop-in national
replacement for an existing NYC-only metric, not just a new signal.

## Evaluation
- **Granularity:** tract (also available at county level).
- **Update frequency / history:** versioned snapshots, not a long trend series; cross-version
  comparison is possible but the product isn't designed as one.
- **Cost / license:** free, no API key for bulk files or the FeatureServer. FEMA's metadata
  flags the index for "planning purposes only" — an interpretation caveat, not a reuse or
  commercial-use restriction, and no stricter than how this project already treats
  `NypdFelonies` or `FutureFloodplain` (screening signals, not transaction-grade determinations).
- No quantitative correlation run (not a price/rent series); the right validation is a direct
  comparison of NRI's flood-hazard component against the existing NYC floodplain data for the same
  tracts, as a sanity check before leaning on it elsewhere.

## Recommendation
**Recommend implementing.** It's the clearest fit for this project's stated national-generalization
goal: free, tract-level, covers every county in the country out of the box, and gives the climate
pillar a path to work outside NYC — something it currently has none. Suggest a NYC-first rollout
(validate the flood component against `FutureFloodplain` on the same tracts) with the intent that
NRI eventually supersedes the NYC-only dataset once other metros are added, rather than running
both indefinitely.
