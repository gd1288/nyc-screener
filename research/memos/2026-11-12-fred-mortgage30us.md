# FRED — 30-Year Fixed Rate Mortgage Average (MORTGAGE30US)

**Recommendation: recommend.**

## What it is
A weekly US-wide average 30-year fixed mortgage rate, published by Freddie Mac's Primary Mortgage
Market Survey and distributed through the Federal Reserve Bank of St. Louis's FRED API
(series `MORTGAGE30US`). History runs weekly back to 1971. Free, with a free API key (standard for
FRED), or a keyless CSV route (`fredgraph.csv`) for the same series.

## Why it could help
`backend/app/scoring/investment.py` defines:

```python
@dataclass
class Assumptions:
    interest_rate: float = 0.065
```

That constant feeds every `monthly_payment` / `loan_balance` / cash-flow projection in the
investment engine — it's the single biggest hardcoded assumption in the per-property valuation
math, and it goes stale the moment actual mortgage rates move. MORTGAGE30US would let that default
track reality instead. It's also genuinely national (not NYC-specific), which fits this project's
stated goal of generalizing beyond NYC.

## Evaluation
- **Cost**: free; API key required but no trial/paid tier. Third-party sources claim ~120
  requests/min, unconfirmed against FRED's own terms but irrelevant here — this is a single tiny
  series, not a bulk pull.
- **License**: FRED marks the series "Copyrighted: Citation Required" (source: Freddie Mac) —
  attribution needed, no commercial-use block found.
- **Granularity**: national only (no regional breakdown) — that's fine; it's meant to set a single
  shared assumption, not a per-neighborhood metric.
- **History**: weekly since 1971 — more than enough for any sensitivity backtest.
- **Quantitative evaluation**: not run. `app/research/evaluate_series.py` (Phase 4) doesn't exist
  yet in this repo, so this is a qualitative recommendation only — there's no correlation target
  to test a rate series against anyway (it's an assumption input, not a growth predictor).

## Implementation sketch (for whoever picks this up via `add-data-source`, not done here)
A thin adapter: one HTTP call to FRED's series-observations endpoint for `MORTGAGE30US`, store the
latest observation (and ideally full history, since it's cheap) somewhere `Assumptions` can read
it as a live default instead of `0.065`.

## Open questions
- Confirm FRED's actual rate limit against their own docs (only third-party numbers found).
- Decide: store full history (useful for a "what if rates were X" sensitivity view) or just latest
  value — likely both, since the series is tiny.

Candidate JSON: `research/candidates/fred-mortgage30us.json`
