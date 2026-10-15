# HUD Fair Market Rents (FMR) -- research memo

**Date:** 2026-10-15 | **Candidate file:** `research/candidates/hud-fair-market-rents.json` | **Recommendation: RECOMMEND**

## What it is
HUD's annual rent benchmark, published for every OMB metro area (and HUD metro subdivision) plus
every non-metro county nationwide, used nationally to set Section 8 payment standards. Bulk files
are published on huduser.gov each fiscal year; a 2-bedroom CSV history runs back to 1983.

## Why it could help
Rent data in this project currently comes from two budget- or coverage-constrained sources:
RentCast (hard-capped at 31 requests/month -- `app/sources/rentcast.py`) and Zillow ZORI
(`zillow_research.py`, metro-limited). `neighborhood_rent` in `investment.py`'s `PropertyInputs`
needs a value everywhere the screener might be pointed, per the project's US-generalization goal.
HUD FMR is free, national, and updated yearly -- a plausible fallback/floor for rent estimation
outside RentCast/ZORI's footprint.

## Evaluation
- **Cost / access:** free. The *API* needs a free account + token, but the bulk files on the FMR
  dataset page (huduser.gov/PORTAL/datasets/fmr.html) download directly with no account at all --
  that's the route to use.
- **License:** federal data, effectively public domain; third-party write-ups of the FY2026 release
  describe it as free, no signup.
- **Format caveat:** the current full county-level release appears to be an Excel workbook (XLSX),
  not CSV (only the 2-bedroom historical series is CSV) -- adapter would need `openpyxl` or similar,
  a minor implementation note, not a blocker.
- **Granularity:** metro / metro-subdivision / non-metro county -- coarser than tract, fine for a
  rent benchmark.
- **Update frequency:** annual -- fine for a floor/fallback, too coarse to be a trend signal on its
  own.
- **Quantitative correlation:** not run (no evaluation tooling yet, see FHFA memo for the same
  caveat).

## Recommendation
Recommend. Free, genuinely national, no login wall for the files that matter. Implementer should
confirm the exact current-year file name/format on HUD's page before writing the adapter, since the
bulk format differs between the historical (CSV) and current (XLSX) releases.
