# FRED 30-Year Fixed Rate Mortgage Average (MORTGAGE30US)

**Recommendation: recommend, with a licensing caveat to resolve before implementing.**

## What it is
A weekly national average 30-year fixed mortgage rate, published by Freddie Mac's Primary
Mortgage Market Survey and distributed through the St. Louis Fed's FRED API. Series ID
`MORTGAGE30US`. Updated every week, no seasonal adjustment. History start date is unverified this
pass — two searches gave conflicting answers (1954 vs. 1971) — but either way it's decades of
weekly data, far more than needed for a "current rate" use case.

## Why it could help
`backend/app/scoring/investment.py` hardcodes `Assumptions.interest_rate = 0.065` as the default
mortgage rate used in every cash-flow and return projection. That default doesn't move with the
market — it was accurate at whatever point it was set and gets stale otherwise. Swapping it for a
live read of MORTGAGE30US means every projected deal uses today's actual financing cost, for any
property anywhere in the US, since it's a single national series with no per-market lookup needed.
This is one of the lowest-integration-cost, highest-leverage candidates evaluated this run: it
replaces one constant with one API call, no new scoring logic or schema needed beyond storing the
current rate.

## Evaluation
- **Cost**: free, no paid tier.
- **Auth**: requires a free FRED API key (instant self-serve signup). This adds a new secret to
  `.env`, parallel to the existing RentCast key.
- **Granularity**: national only — appropriate here since it's feeding a single assumption default,
  not a per-neighborhood metric.
- **History**: 1971–present, weekly. Far more than needed for a "current rate" use case.
- **License**: this is the one open item. FRED's terms permit personal/non-commercial/educational
  use freely; commercial use and redistribution of *raw series data as a competing feed* need
  closer reading (https://fred.stlouisfed.org/legal). This project's intended use — reading one
  current value to set a default assumption inside a tool, not republishing the historical series
  — is very likely fine, but CLAUDE.md's bar is "no clause blocking commercial/product use," and
  FRED's clause is nuanced rather than a flat allow. A human should read the actual terms page
  before implementing (this session could not fetch fred.stlouisfed.org directly — egress to that
  domain was blocked from this environment; the summary above comes from search-engine results,
  not a direct read).
- No `evaluate_series.py` correlation run — that tool doesn't exist yet in this repo, and a
  correlation check isn't really the right test for this candidate anyway (it's an assumption
  input, not a predictive signal being scored against appreciation).

## Bottom line
Recommend, contingent on a quick human read of FRED's ToS to confirm the "read one current value
into a private tool" use case is comfortably inside the non-commercial/ordinary-use lane. If clear,
this is a small, high-value fix for a currently-stale hardcoded assumption.
