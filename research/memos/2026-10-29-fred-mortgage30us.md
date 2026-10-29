# FRED MORTGAGE30US — 30-Year Fixed Mortgage Rate

**Date:** 2026-10-29 · **Candidate JSON:** `research/candidates/fred-mortgage30us.json` ·
**Recommendation: recommend**

## What it is
Freddie Mac's Primary Mortgage Market Survey (PMMS) 30-year fixed mortgage rate, published weekly
by the Federal Reserve Bank of St. Louis as FRED series `MORTGAGE30US`. National series, no
sub-national breakdown, weekly (Thursday), back to 1971. Free; a direct CSV pull
(`fredgraph.csv?id=MORTGAGE30US`) needs no key at all, and the programmatic `api.stlouisfed.org`
endpoint wants a free, instant API key — the same registration pattern this codebase already uses
for `census_api_key`.

## Why it could help
`backend/app/scoring/investment.py` hardcodes `Assumptions.interest_rate: float = 0.065` — every
mortgage payment, monthly cash flow, and IRR the app shows a user is computed against that one
fixed number, with no indication of how current it is. A weekly national rate feed would let the
default track the real market rate (and would let a future UI show "as of" so users know the
assumption's vintage), with essentially no new geographic-joining logic since it's a single scalar,
not a per-neighborhood metric.

## Evaluation
- **Granularity:** national (no county/ZIP/tract breakdown exists or is needed for this use).
- **Update frequency / history:** weekly, 1971–present.
- **Cost:** free; FRED flags the series "Copyrighted: Citation Required," which is a citation
  requirement, not a reuse restriction — consistent with how other FRED/government series are
  commonly redistributed.
- **License:** no commercial-use block found; standard free-key registration, no paid tier
  involved.
- Quantitative correlation testing (`app/research/evaluate_series.py`) doesn't apply here — this is
  a macro assumption input, not a neighborhood-level predictor to backtest against local
  appreciation.

## Recommendation
**Recommend implementing.** Highest value-to-effort ratio of the five candidates reviewed this
run: it fixes a real, currently-stale hardcoded constant used in live financial math, with a
trivial integration (one national weekly scalar, no neighborhood joins, no new geography
handling, same free-key pattern already proven out for Census).
