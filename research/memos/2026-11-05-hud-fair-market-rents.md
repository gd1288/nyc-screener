# HUD Fair Market Rents — national rent fallback

**Recommend as a fallback/complement to Zillow ZORI, not a replacement.**

## What it is
HUD's annual Fair Market Rent estimates (40th-percentile gross rent for a "standard quality" unit)
for every US county/metro since FY1983, plus Small Area (ZIP-level) FMRs within larger metros.
Free static downloads, public domain, no login or key.

## Why it could help
`gross_rent_yield` (valuation pillar) and the rent assumption feeding `investment.py`'s cash-flow
math both depend on Zillow ZORI, and `app/sources/zillow_research.py` hard-filters that feed to
NYC ZIP codes in the five NYC counties. The moment this screener is pointed at a county Zillow
doesn't cover (true for a lot of smaller US counties), there is currently no rent data at all to
fall back on.

## Evaluation
- **Coverage/granularity**: national, every county/metro, every fiscal year since 1983; Small Area
  FMRs add ZIP-level detail in large metros.
- **Update frequency**: annual, published by October 1 each fiscal year by law.
- **Cost/license**: free, US government work, public domain, no key.
- **Caveat**: FMR is a regulatory 40th-percentile Section 8 benchmark, not a market-rate index —
  it will be a noisier/lower proxy for condo asking rents than ZORI wherever ZORI is actually
  available. Its value is coverage, not precision.
- **Quantitative evaluation**: not run (no `evaluate_series.py` yet); the natural first test once
  built would be comparing FMR vs. ZORI for the NYC ZIPs where both exist, to quantify the gap
  before trusting FMR alone elsewhere.

## Recommendation
Implement as a documented fallback path (prefer ZORI where present, fall back to FMR where it
isn't), not a wholesale replacement. Lower priority than the mortgage-rate and FHFA candidates
since it only matters once non-NYC areas are actually being screened, but cheap to add given the
format and license.
