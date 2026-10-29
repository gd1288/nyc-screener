# HUD Fair Market Rents (FMR)

**Date:** 2026-10-29 · **Candidate JSON:** `research/candidates/hud-fair-market-rents.json` ·
**Recommendation: do-not-recommend**

## What it is
HUD's annual Fair Market Rent figures by county/metro area, set each federal fiscal year (Oct 1
effective), used primarily to set Section 8 housing-assistance payment standards. Free yearly
files on `huduser.gov`, public domain; a newer official API wants a free registration token for
current-year/programmatic pulls, but the bulk yearly files don't need one.

## Why it was considered
It's a free, national, government rent dataset — on paper a candidate to strengthen the
`valuation` pillar's `gross_rent_yield` metric or to extend rent coverage to places Zillow's
ZORI series doesn't reach.

## Evaluation
- **Granularity / cadence:** county, annual — coarser and slower than the ZIP-level, monthly
  Zillow ZORI series already in production (`backend/app/sources/zillow_research.py`).
- **Structural mismatch:** FMR is defined around the 40th percentile of gross rent for
  Section-8 payment-standard purposes, not market-rate rent. Folding it into
  `gross_rent_yield` alongside ZORI would introduce a systematic downward bias relative to the
  market-rate series already in use, rather than genuinely new signal.
- **Cost / license:** free, no commercial-use restriction found.
- No quantitative correlation run — the structural mismatch above is a strong enough signal on
  its own without needing `evaluate_series.py`.

## Recommendation
**Do not recommend, for now.** Strictly worse than the metric already in production for every
place that metric already covers (annual vs. monthly, county vs. ZIP, policy-rent vs.
market-rent). Its only genuine use case — filling Zillow ZORI's coverage gaps in rural/small
markets — only materializes once the area-model migration adds non-metro areas. Worth a second
look then; not a fit for the app as it stands.
