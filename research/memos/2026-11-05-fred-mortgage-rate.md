# FRED MORTGAGE30US — live 30-year fixed mortgage rate

**Recommend.**

## What it is
The weekly Freddie Mac Primary Mortgage Market Survey average, published by FRED (series
`MORTGAGE30US`), going back to April 1971. One number: the current average 30-year fixed rate.

## Why it could help
`backend/app/scoring/investment.py:21` hardcodes `interest_rate: float = 0.065` on the
`Assumptions` dataclass that every per-property projection (monthly payment, loan balance, cash
flow, IRR, the 10/20-year scenario table) is built from. That constant has no update path today.
A live rate feed would let every return number in the app reflect the actual current cost of a
mortgage instead of a number someone typed in once. It's also a clean building block for a future
rate-sensitivity scenario in the Monte Carlo valuation work mentioned in `backend/CLAUDE.md`.

## Evaluation
- **Coverage/granularity**: national, single series — appropriate, since mortgage rate isn't a
  neighborhood-level input.
- **Update frequency**: weekly.
- **History**: 1971–present (useful if a rate-sensitivity backtest is ever wanted).
- **Cost**: free. FRED API needs a free registered key (unlimited practical use for one series,
  no documented rate limit that matters here).
- **License**: FRED labels this series "Copyrighted: Citation Required" (it's Freddie Mac's data,
  FRED is just the distributor). That's fine for consuming the latest value with attribution —
  same posture the project already takes with Zillow Research data (also third-party licensed,
  consumed via `app/sources/zillow_research.py`). It would be a problem only if the project tried
  to republish the raw historical series as a downloadable dataset of its own, which isn't the use
  case here.
- **Quantitative evaluation**: not run — `app/research/evaluate_series.py` doesn't exist yet
  (Phase 4, per the research-sources skill). Nothing to correlate against FHFA/ZORI here anyway
  since this isn't a neighborhood growth signal, it's a financing-cost input.

## Recommendation
Implement. Narrowest-scope, highest-certainty win of this batch: one new small source feeding one
existing, already-wired constant, no new pillar/weight decisions needed. Suggest reviewing against
`app/sources/base.py`'s `Source` contract during `add-data-source` for how best to store/expose a
single scalar macro setting (it isn't a `NeighborhoodMetric`, a `Sale`, or a listing — may need a
small addition to the `kind` taxonomy, or just an `AppSetting` write).
