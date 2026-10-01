# FRED MORTGAGE30US (Freddie Mac 30-Year Fixed Mortgage Rate)

**Candidate file:** `research/candidates/fred-mortgage30us.json`
**Recommend:** Yes

## What it is
FRED's `MORTGAGE30US` series: the US average 30-year fixed-rate mortgage rate, from Freddie
Mac's Primary Mortgage Market Survey, published weekly and mirrored by the St. Louis Fed. Plain
CSV download, no API key, no login:

```
https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US
```

Public, free, weekly, history back to 1971.

## Why it could help
This isn't a neighborhood-growth predictor -- it's a single national number, so it can't be used
to rank NTAs and there's nothing to correlate it against (FHFA HPI / ZORI correlation only makes
sense for a candidate that *varies by neighborhood*). Its value is as an **investment-assumption
input**: `backend/app/scoring/investment.py:21` currently hardcodes

```python
interest_rate: float = 0.065
```

and that constant feeds every mortgage payment and cash-flow projection in the investment engine
(`monthly_payment`, `loan_balance`, the 10/20-year projections). As market rates move, every
return estimate the screener produces silently drifts away from what a buyer could actually get
financed at today. A live weekly rate (or even a periodically-refreshed single value) would fix
that without touching the rest of the investment math.

## Evaluation
- **Coverage/granularity:** national, single series -- not applicable to per-neighborhood scoring.
- **Update frequency:** weekly.
- **History:** 1971-present, far more than enough for any backtest this project runs.
- **Cost/license:** free, no key, no login; FRED's terms permit free reuse of this series.
- **Quantitative correlation (Phase 4 `evaluate_series.py`):** not run -- that tool doesn't exist
  in this repo yet, and wouldn't apply to a national scalar anyway.

## Verification caveat
`fred.stlouisfed.org` is blocked by this sandbox's outbound network policy (confirmed via both
`WebFetch` and a direct `curl` through the session's egress proxy, which returned a 403 on the
CONNECT). Everything above is corroborated through web search results pointing at FRED's own
documented CSV-gateway endpoint, not a live fetch this session. This is a sandbox-network
restriction, not evidence against the source -- `census_acs` already reaches a comparable
government-adjacent host from this project's actual runtime.

## Recommendation
**Recommend.** Concrete, already-identified consumer in the code (the hardcoded `interest_rate`
assumption); trivial ingest (one national scalar, no geocoding, no entity matching); free,
long-history, no key. Suggested follow-up if approved: a small source that writes the latest (and
maybe a trailing window of) `MORTGAGE30US` values somewhere the investment engine can read as a
default for `Assumptions.interest_rate`, rather than a fixed constant.
