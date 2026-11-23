# FRED: 30-Year Fixed Rate Mortgage Average (MORTGAGE30US)

**Recommendation: Approve — highest priority this run.**

## What it is
Freddie Mac's Primary Mortgage Market Survey national average 30-year fixed mortgage rate,
published weekly by FRED (Federal Reserve Bank of St. Louis) since 1971. Free, no-login CSV
export: `https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US`.

## Why it could help
`backend/app/scoring/investment.py` hardcodes the financing cost used in every per-property
return projection:

```python
interest_rate: float = 0.065
```

That default never updates — every projection for every property silently uses a 6.5% rate
regardless of when the screener is actually run, which is both the wrong rate in any period
that isn't currently "around 6.5%" and invisible to anyone downstream reading the output.
This series is the standard public reference for exactly that number, updated weekly, with no
cost or access friction.

## Evaluation
- **Coverage/granularity**: national, single series (the rate itself isn't geography-specific,
  which matches how it's used — one assumption shared across all properties).
- **Update frequency**: weekly.
- **History**: 1971–present, far more than enough for any backtest use.
- **Cost / access**: free; the plain CSV export needs no API key or account. (FRED's
  programmatic API does require a free key for higher-volume use, but that's a different
  access path than the one proposed, and isn't needed here.)
- **License**: cite Freddie Mac + FRED/St. Louis Fed on reuse; no paywall, no commercial-use
  restriction found.
- **Caveat**: Freddie Mac changed its survey methodology on 2022-11-17, so the series isn't
  strictly comparable across that date if it's ever used historically rather than as a live
  "current rate" input — not a concern for the proposed use (always read the latest value).
- **Quantitative correlation**: not run — `app/research/evaluate_series.py` (Phase 4) doesn't
  exist yet in this repo, and this candidate isn't the kind of growth-predictor series that
  tool is meant to score anyway (it's a financing input, not a neighborhood growth signal).

## Recommendation
Approve. This doesn't add a new scoring pillar or any new judgment calls — it replaces a
frozen constant with the real number it's supposed to approximate, using a data source that's
about as low-risk as they come (federal reference series, decades of history, free, no login).
