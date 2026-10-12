# FRED MORTGAGE30US (Freddie Mac Primary Mortgage Market Survey)

**Date:** 2026-10-12 · **Verdict:** Recommend with caveats · **Gap:**
`backend/app/scoring/investment.py:21` hardcodes `interest_rate: float = 0.065` with no data behind
it.

## What it is
The weekly US average 30-year fixed mortgage rate, from Freddie Mac's Primary Mortgage Market
Survey, distributed through the Federal Reserve Bank of St. Louis's FRED API.

- **URL:** https://fred.stlouisfed.org/series/MORTGAGE30US
- **Granularity:** national, single series -- one number per week, not a per-neighborhood metric.
- **Update frequency:** weekly (Thursdays). Methodology changed 2022-11-17 (moved from a phone
  survey to lender-submitted loan applications) -- a discontinuity worth a comment if anyone later
  backtests across that boundary.
- **History:** back to 1971-04-02.
- **Access:** free FRED API key, self-serve signup with instant approval -- same shape as the
  project's existing `census_api_key` (see `census_acs.py`'s `requires = ["census_api_key"]`), so
  there's direct precedent for a free-key source in this codebase. Rate limits (120 req/min general,
  40 req/min for series-observations) are irrelevant at one value/week.
- **License:** **not plain public domain.** The series itself carries a Freddie Mac copyright
  notice; FRED reprints it "with permission" and data is provided as-is, no warranty. FRED's own
  API terms of use are separate and permissive, but the content is Freddie Mac's, not the
  government's.

## Why it could help
This isn't a Growth Score candidate -- it's a direct fix for a literal hardcoded guess. Every IRR
and cash-flow projection in `investment.py` currently runs off a static 6.5% that has no
justification in the code or comments. A live weekly rate (or a rolling average of it) would make
every downstream investment number actually reflect current financing conditions.

## Evaluation
Not applicable to `evaluate_series.py`'s FHFA-HPI/ZORI correlation design -- this is a financing-cost
input to cash-flow math, not a predictor of neighborhood appreciation. No correlation was computed
or would be meaningful here.

## Caveats
- **Not a `NeighborhoodMetric`.** Per `backend/CLAUDE.md`, every Growth Score metric must become a
  percentile within a comparison set; a national constant is identical across every neighborhood
  and can't be ranked. This should feed `Assumptions.interest_rate`'s default (or a future
  `FactorDef.market_estimate()` in `app/valuation/`), never `sources.yaml`/`NeighborhoodMetric`.
- **Attribution required.** Freddie Mac is the actual rights holder; wherever the rate is surfaced
  in the UI (e.g. the assumptions panel), it needs a "Source: Freddie Mac PMMS via FRED" credit,
  not a bare number presented as the project's own data.

## Recommendation
**Recommend with caveats.** Real gap, long history, genuinely free, reasonable access pattern with
direct precedent in this codebase. Flagging the Freddie Mac copyright explicitly so it isn't waved
through as "just a government number" -- it's fine to use with attribution, but it is not public
domain the way most of this project's other sources are.
