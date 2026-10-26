# FRED MORTGAGE30US — 30-Year Fixed Mortgage Rate

**Date:** 2026-10-26 · **Candidate file:** `research/candidates/fred-mortgage30us.json`

## What it is
FRED series `MORTGAGE30US`: the national average 30-year fixed mortgage rate from Freddie Mac's
Primary Mortgage Market Survey, published weekly since April 1971. Free, U.S. government/Fed-hosted
data; a plain CSV endpoint is reported to work without an API key, and a full key is free and instant
if the JSON/XML API is preferred.

## Why it could help
`backend/app/scoring/investment.py:21` hardcodes `interest_rate: float = 0.065` as the default
financing assumption used in every mortgage payment, loan-balance and IRR calculation in the
Opportunity Score. It has no "as of" date and will silently drift stale as real rates move. A tiny
weekly pull of one CSV value would let that assumption track reality (or at minimum be displayed with
a real timestamp instead of a bare constant).

## Evaluation
Not applicable in the backtest sense: this is a single national value, not a neighborhood-level
series, so it can't be percentile-ranked or lead/lag-correlated against FHFA HPI or Zillow ZORI the
way a neighborhood predictor would be. `app/research/evaluate_series.py` (skill step 4) also doesn't
exist in this repo yet. The case for this candidate is "fixes a known stale constant," not "predicts
appreciation."

## Verification caveat
Could not fetch fred.stlouisfed.org directly in this session — the egress proxy returned
`403 connect_rejected` for every candidate host tried (fred.stlouisfed.org, fhfa.gov, bls.gov,
huduser.gov, data.gov), so this is a session-level network restriction, not evidence against FRED
specifically. Facts here come from WebSearch summaries of third-party pages, not a direct read of
FRED's own API docs. **Confirm before implementing:** whether the keyless CSV endpoint
(`fredgraph.csv?id=MORTGAGE30US`) is still reliable for routine automated pulls, or whether a free key
is actually required.

## Recommendation: **Recommend**
Smallest, lowest-risk, highest-certainty candidate in this batch — exactly because its scope is
narrow. Implementation is a weekly cron reading one value into an `AppSetting`-style store, not a
`NeighborhoodMetric`. Low cost, concrete payoff, no co-op/coverage ambiguity to sort out.
