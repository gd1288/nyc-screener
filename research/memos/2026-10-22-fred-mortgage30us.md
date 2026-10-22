# FRED MORTGAGE30US — 30-Year Fixed Mortgage Rate

**Recommendation: recommend**

## What it is
`MORTGAGE30US` on FRED (Federal Reserve Bank of St. Louis) republishes Freddie Mac's Primary
Mortgage Market Survey: the national average 30-year fixed mortgage commitment rate, weekly, back
to April 1971. Access is via FRED's REST API with a free registration key — no trial, no paywall.
Documented client rate limits exist but are far above what a weekly pull needs.

## Why it could help
`backend/app/scoring/investment.py` currently hardcodes:

```python
interest_rate: float = 0.065
```

as the default financing assumption for every per-property return calculation. That's a static
guess sitting in code, not data. It is exactly the kind of input this series was built for, and
it directly feeds `monthly_payment`, `loan_balance`, and the cash-flow projections downstream —
a change here touches every return number the app shows an investor, for the better.

## Evaluation
- **Coverage/granularity**: national, single series — no neighborhood or regional join needed,
  about as simple as a data source gets.
- **Cost**: free key, immediate on signup, no rate-limit risk for a weekly series.
- **License**: FRED's Terms of Use require attribution (cite FRED, preserve the Freddie Mac
  copyright notice, no implied endorsement). No commercial-use restriction found.
- **History**: 1971–present, far more than enough for any backtest window this project runs.
- **Quantitative evaluation**: not run — `app/research/evaluate_series.py` doesn't exist yet
  (Phase 4, per the research-sources skill). Not really applicable here anyway: this is a cost
  input to the investment model, not a growth-score predictor to correlate against appreciation.

## Recommendation
Strong recommend. Low effort (one series, no geo-matching), clear and immediate value (replaces a
hardcoded constant with live data), free, well-documented, government-adjacent source. This is the
easiest win in this batch.
