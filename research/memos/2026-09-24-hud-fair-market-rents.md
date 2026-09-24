# HUD Fair Market Rents (FMR) API

**Recommendation: recommend, as a complement to Zillow ZORI rather than a replacement.**

## What it is
HUD's annual estimate of gross rent (base rent + essential utilities) by bedroom count
(efficiency through 4-bedroom), published for every US county and metro FMR area. Used to set
Housing Choice Voucher payment standards, so it's maintained and audited as a matter of federal
program compliance. Official REST API documented at
https://www.huduser.gov/portal/dataset/fmr-api.html.

## Why it could help
`backend/app/scoring/investment.py`'s `PropertyInputs.neighborhood_rent` is sourced from Zillow
ZORI (`zillow_research.py`), and `BEDROOM_RENT_FACTOR` approximates how rent scales by bedroom
count off that single neighborhood figure. ZORI's coverage is metro-dependent — strong in NYC and
other large markets Zillow tracks, thin or absent elsewhere. HUD FMR covers every US county and
already breaks rent out by bedroom count directly, which is exactly the axis `BEDROOM_RENT_FACTOR`
currently has to estimate. It's a natural fallback for `neighborhood_rent` in markets where ZORI
has no data, and a more precise per-bedroom source even where ZORI does.

## Evaluation
- **Cost**: free. **Auth**: free bearer token (self-serve registration + email confirmation).
- **Rate limit**: reported as 1,200 requests/minute per token in third-party summaries — generous
  for this project's refresh cadence either way.
- **Granularity**: county / metro FMR area; Small Area FMRs go to ZIP level in some metros.
- **Update frequency**: annual — coarser than ZORI, which is the tradeoff for universal coverage.
- **License**: federal government data; no commercial-use restriction found in this pass. **Caveat**:
  this session could not directly fetch huduser.gov (egress was blocked from this environment), so
  the license/ToS assessment here comes from search-engine summaries of the HUD USER API Terms of
  Service page, not a direct read of that page's text. Read
  https://www.huduser.gov/portal/dataset/api-terms-of-service.html directly before implementing.
- No `evaluate_series.py` correlation run — the tool doesn't exist yet in this repo.

## Bottom line
Recommend as a coverage-gap filler, not a ZORI replacement: annual cadence is coarser, but
universal US county coverage plus native per-bedroom breakdown directly serves the
"any US neighborhood" goal and removes an estimated multiplier from the investment model. Confirm
the ToS text directly (this session's read was indirect) before moving to implementation.
