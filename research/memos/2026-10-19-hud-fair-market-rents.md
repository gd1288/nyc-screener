# HUD Fair Market Rents (FMR / SAFMR) — research memo

**Date:** 2026-10-19 · **Candidate file:** `research/candidates/hud-fair-market-rents.json` · **Recommendation: lean-recommend**

## What it is
HUD's annual estimate of 40th-percentile gross rent for standard-quality units, published for
every US metro area and nonmetro county (standard FMRs), plus Small Area FMRs (SAFMRs) at 5-digit
ZIP level for all metro areas. Free bulk XLSX/CSV downloads from huduser.gov, no login required
for the published files.

## Why it could help
`scoring/investment.py`'s `estimate_rent()` falls back to Zillow ZORI × a fixed bedroom factor
whenever there's no live listing rent. The only other rent signal anywhere in the pipeline is
`rentcast_listings`, which `sources.yaml` caps at 31 requests/month across exactly 5 hardcoded NYC
boroughs. Outside those 5 areas — which is most of the country, and exactly where the project's
stated US-wide ambition points — there is currently no rent data source at all. HUD FMR would give
`estimate_rent()` a free, national fallback basis that doesn't touch the RentCast budget.

## Evaluation
- **Geography:** metro area / nonmetro county for standard FMRs nationwide; 5-digit ZIP for
  SAFMRs in all metro areas.
- **Update frequency:** annual (new fiscal-year file each fall).
- **History:** HUD publishes current + prior-year files; a back-series exists but requires
  stitching together each year's archived release rather than pulling one continuous time series.
- **Cost/license:** free either way. The bulk XLSX/CSV files need no login at all. A separate
  programmatic FMR API exists and appears (based on a third-party R package's behavior, not HUD's
  own docs) to require a free key for ZIP-level/SAFMR lookups.

## Caveats / what to re-check before implementing
- Could not reach huduser.gov directly this run (sandbox DNS/proxy issue) — confirm the API key
  requirement and the SAFMR file structure against HUD's own API documentation, not a third-party
  client library's behavior, before implementing.
- Annual cadence makes this meaningfully coarser than a live listing or than Zillow ZORI's
  monthly update — best positioned as the out-of-NYC fallback tier for `estimate_rent()`, not a
  replacement for existing NYC rent signals.

## Recommendation
**Lean-recommend.** Real, free, genuinely national fit for the stated generalization goal, but
rated a notch below the top candidates because the no-login bulk files are only metro/county
grain (ZIP-level SAFMR needs the unconfirmed keyed API) and the annual update is coarse relative
to what the project already has for NYC specifically.
