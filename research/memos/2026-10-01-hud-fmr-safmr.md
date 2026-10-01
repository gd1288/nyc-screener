# HUD Fair Market Rents / Small Area FMRs (SAFMR)

**Candidate file:** `research/candidates/hud-fmr-safmr.json`
**Recommend:** Conditional (not now; revisit for non-NYC metros)

## What it is
HUD's administratively-set "fair market rent," used to set Section 8 housing-voucher payment
standards, published annually by county/metro (standard FMR) and, in SAFMR-designated metros, by
individual ZIP code. Bulk Excel/CSV/ZIP files, no login:

```
https://www.huduser.gov/portal/datasets/fmr.html
```

(A separate HUD REST API at `huduser.gov/hudapi/public/fmr` also exists but requires a free API
token -- the bulk files avoid that and are the right access path per this project's preference
for no-login bulk downloads over key-gated APIs.)

## Why it's only a partial gap
`backend/app/sources/zillow_research.py` already ingests Zillow ZORI (observed asking rents) at
ZIP level, currently filtered to NYC counties. FMR/SAFMR measures something different -- a
regulatory benchmark rent, not an observed market rent -- and it isn't a good predictor source
for that reason (it's smoothed and updated only annually, so it lags the market). What it does
have that ZORI doesn't: **guaranteed ZIP coverage for essentially every US ZIP every year**,
where ZORI only publishes for ZIPs with enough listing volume -- smaller and mid-size markets are
often missing from ZORI entirely.

## Evaluation
- **Coverage/granularity:** national; ZIP (SAFMR, where designated) or county/metro (standard
  FMR) elsewhere.
- **Update frequency:** annual (fiscal year).
- **History:** bulk files published back to 1983 per HUD's own dataset page.
- **Cost/license:** free, public-domain federal data, bulk files need no signup.
- **Existing overlap:** partial -- ZORI already covers NYC rents at ZIP level; FMR's edge is
  coverage completeness in markets ZORI doesn't reach, not accuracy where both exist.
- **Quantitative correlation:** not run (no `evaluate_series.py` in this repo yet).

## Verification caveat
`huduser.gov` is blocked by this sandbox's outbound network policy -- could not fetch the
datasets page or confirm the current fiscal-year file URL. Corroborated via search results
referencing HUD's own dataset page and documented 1983-present bulk history.

## Recommendation
**Conditional, not now.** ZORI already covers NYC rents adequately, so FMR/SAFMR adds little here
today. Its value is as a rent-coverage backstop once the project scores smaller non-NYC metros
where ZORI's listing-volume threshold leaves gaps -- use it as a fallback where ZORI has no data,
not a replacement where it does. Hold until a non-NYC market is being onboarded.
