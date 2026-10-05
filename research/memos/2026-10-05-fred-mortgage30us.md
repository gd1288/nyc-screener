# FRED: 30-Year Fixed Rate Mortgage Average (MORTGAGE30US)

**Candidate file:** `research/candidates/fred-mortgage30us.json`
**Recommendation: recommend**

## What it is

A weekly national series from the St. Louis Fed's FRED database, sourced from Freddie Mac's
Primary Mortgage Market Survey. Series ID `MORTGAGE30US`. History back to 1971-04-02, so there's
decades of coverage for any historical backtest that wants to condition on prevailing rates.

## Why it could help

`backend/app/scoring/investment.py`'s `Assumptions` dataclass hardcodes
`interest_rate: float = 0.065` as the mortgage rate used throughout every per-property cash-flow
and IRR projection. The module docstring and the field itself invite review but nothing refreshes
it — it's a snapshot assumption that silently goes stale as actual rates move. A scheduled weekly
pull of this one series would let that default track reality instead of being hand-edited
whenever someone notices it's off.

This is a different shape of "data source" than the rest of `app/sources/`: it's a single
national number, not a per-neighborhood metric. It doesn't fit the `kind: neighborhood` contract
(`write_metrics` expects a geography key) as-is — it would need either a new `kind` (e.g.
`kind: assumption` or `kind: global`) or just a small dedicated settings-cache table. That's an
implementation design question for whoever picks this up via `add-data-source`, not a reason to
reject the candidate.

## Evaluation

- **Measures:** national average 30-year fixed mortgage rate, weekly, not seasonally adjusted.
- **Granularity:** national only — not geography-sliced, which is fine since it's meant to drive
  one shared assumption, not a per-neighborhood metric.
- **Cost:** free, no trial/tier distinction.
- **License:** FRED redistributes Freddie Mac PMMS data under FRED's own terms of use, which
  permit commercial and product reuse with attribution — no clause blocking this project's use.
- **Access:** requires a free registered API key
  (https://fredaccount.stlouisfed.org/apikeys) — same credential pattern already used for
  `census_api_key` (`CensusAcs`) and the RentCast key, so no new kind of secret-handling is
  introduced, just one more `requires: [...]` entry.
- **History:** 1971-present, more than enough for any backtest window this project uses.

No quantitative correlation run — `app/research/evaluate_series.py` doesn't exist yet in this
codebase (Phase 4, per the research-sources skill), so this evaluation is qualitative only. That
said, correlation against FHFA HPI/ZORI isn't really the right test for this candidate anyway: it
isn't proposed as a growth predictor, it's proposed as a cash-flow assumption input. Its "does it
work" test is closer to "does it match the rate a buyer would actually get quoted today," which a
quick spot-check against Freddie Mac's own published PMMS number would confirm at implementation
time.

## Recommendation

Implement. It's the lowest-effort candidate of the four reviewed this run (one series, one HTTP
call, weekly cadence, no geo-joins) and it directly fixes a gap that's already visible in the code
— a mortgage-rate assumption that was presumably accurate when written and has no mechanism to
stay that way.
