# FRED MORTGAGE30US — Freddie Mac 30-Year Fixed Mortgage Rate

**Candidate file:** `research/candidates/fred-mortgage30us.json`
**Recommendation: recommend**

## What it is
Freddie Mac's Primary Mortgage Market Survey (PMMS) 30-year fixed rate, published weekly and
republished on FRED as series `MORTGAGE30US`. National, single value per week, back to 1971.

## Why it could help
`backend/app/scoring/investment.py:21` hardcodes:

```python
interest_rate: float = 0.065
```

Every per-property investment projection (`project_returns` and friends) uses this fixed default
unless a caller overrides it. There is no live source behind it. MORTGAGE30US is exactly the
missing piece: a free, no-key, weekly-updated, long-history national rate that could seed this
default (or feed a small `app/sources/` adapter that writes it as a setting/metric the frontend
can also surface, e.g. "rates as of <date>").

This is a national constant, not a per-neighborhood signal — it does not plug into
`neighborhood.py`'s percentile scoring and shouldn't be forced into a pillar.

## Access and cost
- `https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US` returns the series as CSV with
  no API key and no login.
- FRED's full REST API (more flexible querying, metadata) needs a free registered key — not needed
  for this use case since the CSV endpoint alone is sufficient for "fetch the latest weekly value."

## License
FRED carries "Copyright Freddie Mac. Reprinted with permission." Freddie Mac's Content Use Policy
grants a license to show *automatically-updated* PMMS data, but separately restricts selling or
republishing Freddie Mac content and the Freddie Mac name/logo in commercial contexts without
consent. Read plainly, that policy is aimed at copying their site/content wholesale, not at using a
single published rate as one input to our own amortization math — which is how effectively every
mortgage calculator online uses this series. Still, flag it for a human sanity check before
shipping, and plan to cite "Freddie Mac, 30-Year FRM via FRED" near wherever the rate surfaces in
the UI rather than presenting it as our own dataset.

## Evaluation
Not a backtest candidate (not a neighborhood metric). `app/research/evaluate_series.py` doesn't
exist yet regardless. The useful check here is simpler: does the fetched weekly value match FRED's
published number for a known recent week — that's an integration-test-level check once implemented,
not a correlation study.

## Recommendation
Recommend. Clear, concrete gap (a hardcoded 6.5% default with no update path), clean free access,
long history. The only open item is the Freddie Mac attribution/use question above — worth one
line of confirmation from whoever implements this, not a reason to shelve the idea.
