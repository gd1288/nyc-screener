# BLS Local Area Unemployment Statistics (LAUS) -- research memo

**Date:** 2026-10-15 | **Candidate file:** `research/candidates/bls-laus-unemployment.json` | **Recommendation: RECOMMEND (lower confidence)**

## What it is
BLS's monthly unemployment-rate and labor-force estimates for states, metro areas, counties, and
cities. Published both through a metered JSON API and as raw flat files at
`download.bls.gov/pub/time.series/la/`.

## Why it could help
The project's Growth Score (`scoring/neighborhood.py`) and `census_acs.py` cover demographics but
not labor-market trend. County-level unemployment/labor-force direction is a standard real-estate
leading indicator, and -- unlike `census_acs` (which is already US-wide via the Census API) -- it
updates monthly rather than annually, which could give the growth score a faster-moving economic
input.

## Evaluation
- **Cost / access:** free. The documented API wants a free registration key for higher-volume
  queries, but the raw LAUS bulk files need no key or account at all.
- **License:** federal data, no restriction found.
- **Granularity:** county and county-equivalent -- coarser than what `neighborhood_metrics` is
  actually keyed to. This project's neighborhood geography is NTAs (`nta_boundaries.py`), and NYC
  has only 5 counties/boroughs against roughly 190 NTAs, so a county unemployment figure would be
  shared across dozens of NTAs within a borough rather than differentiating between them. Still
  useful as a city/metro-level economic trend input, just not a per-neighborhood one.
- **Update frequency:** monthly -- the fastest cadence of anything considered this run.
- **Gaps in this evaluation:** this run did not confirm the county series-ID naming convention or
  the exact history depth of the bulk files (stayed within the 8-search budget) -- an implementer
  should spend time on BLS's series-ID documentation before writing an adapter, since the flat-file
  format is less self-describing than a JSON API response.
- **Quantitative correlation:** not run (no evaluation tooling yet).

## Recommendation
Recommend, but with less confidence than FHFA HPI or HUD FMR, purely because this run didn't get
far enough into the bulk-file format to be certain the adapter work is as simple as it looks. The
underlying signal and its free/keyless access are solid.
