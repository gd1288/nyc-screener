# FEMA National Risk Index (NRI)

**Date:** 2026-10-26 · **Candidate file:** `research/candidates/fema-national-risk-index.json`

## What it is
A composite hazard-risk score per county and census tract, combining expected annual loss, social
vulnerability and community resilience across 18 natural hazards (flood, wildfire, heat, hurricane
wind, etc.) — broader than flood alone. Free, no login found, U.S. government public-domain data per
its data.gov catalog listing.

## Why it could help
`app/sources/livability.py`'s `FutureFloodplain` source is NYC-specific (NYC Open Data, 2050s/100-year
floodplain share) and flood-only. NRI is the national, multi-hazard equivalent that CLAUDE.md's
"generalizing to any US neighborhood" goal would eventually need, and it would also capture hazards
NYC's own climate exposure only partly represents today (e.g. extreme heat).

## Evaluation
Not applicable, and this is the key finding: NRI is **not a time series**. Each release is a
point-in-time composite score, not a backdated annual series. The skill's own bar requires "enough
backdated history for the backtest to mean anything" — NRI has essentially none to offer. There is
nothing to lead/lag-correlate against FHFA HPI growth or Zillow ZORI the way a genuine predictor
candidate would be tested, independent of whether `evaluate_series.py` exists.

## Verification caveat
hazards.fema.gov and catalog.data.gov both returned `403 connect_rejected` from this session's proxy.
Findings are from WebSearch summaries of the data.gov catalog entry and FEMA's older announcement
pages, not a direct read of FEMA's current data-resources page. Confirm current download format
(CSV/GDB/shapefile) before implementing.

## Recommendation: **Don't recommend** (for this cycle)
Free, national, government, and squarely in the requested source list — but it fails the skill's own
history/backtest criterion outright, since it isn't a time series at all. It would slot in as a
static risk-penalty overlay (the same role `FutureFloodplain` already plays for NYC), which is a real
but much smaller win than a validated predictor. Worth a dedicated future pass once the area-model
migration (`backend/CLAUDE.md`) is underway and the project needs a non-NYC hazard overlay — not a
priority add today.
