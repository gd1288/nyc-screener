# FRED MORTGAGE30US (30-Year Fixed Rate Mortgage Average)

**Recommendation: recommend-with-caveats**

## What it is
A weekly national average 30-year fixed mortgage rate (Freddie Mac PMMS, distributed via the St. Louis
Fed's FRED database), available back to 1971 through FRED's free API (instant free key on registration).

## Why it could help
`backend/app/scoring/investment.py:21` hardcodes `interest_rate: float = 0.065` as the default financing
assumption used in every property's amortization and cash-flow projection
(`monthly_payment`/`loan_balance` calls at lines 142 and 184). A live feed would let that default track
actual market rates instead of staying fixed at whatever it was set to when the code was written.

## Evaluation
- **Coverage/granularity:** single national series — no geographic breakdown, which is actually the
  right shape here since financing rates aren't neighborhood-specific.
- **Update frequency:** weekly.
- **Cost:** free; API key is free and instant.
- **License:** this is the main open question. FRED's general Terms of Use distinguish personal/
  educational use from "other" (including commercial) use of copyrighted series, and prohibit wholesale
  downloading of FRED content. Whether MORTGAGE30US specifically carries that stricter redistribution
  restriction, versus being one of the "quite a few series [that] are in the public domain" the terms
  also mention, was not confirmed in this run — needs a direct check of the MORTGAGE30US series page's
  own copyright/source notice before implementing.
- **Quantitative evaluation:** not applicable in the growth-score-backtest sense — this doesn't feed the
  neighborhood growth score, it feeds the investment-math default assumption, so `evaluate_series.py`'s
  FHFA HPI/ZORI correlation check isn't the relevant evaluation here.

## Caveats
- Single scalar, not a `NeighborhoodMetric` — this would plug into `investment.py`'s default
  `Assumptions`, not the usual `kind: neighborhood` adapter pattern the other sources follow, so it's a
  different shape of change than a typical `add-data-source` task.
- License needs a series-specific check, not just FRED's general ToS.
- A weekly refresh cadence is probably overkill for a default that's likely reviewed far less often;
  monthly or quarterly would capture most of the value at a fraction of the integration/maintenance
  cost.

## Bottom line
Recommend, but with the explicit caveat that (a) the license needs a per-series confirmation beyond
FRED's boilerplate terms, and (b) this is a smaller, differently-shaped win (one hardcoded constant)
than the other candidates in this batch, which each add a new per-neighborhood/county signal. Worth
doing if the team specifically wants to stop hardcoding the interest rate; not the top priority of this
batch otherwise.
