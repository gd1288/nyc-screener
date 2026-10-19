# FRED — 30-Year Fixed Mortgage Rate (MORTGAGE30US) — research memo

**Date:** 2026-10-19 · **Candidate file:** `research/candidates/fred-mortgage30us.json` · **Recommendation: recommend (conditional)**

## What it is
Freddie Mac's Primary Mortgage Market Survey 30-year fixed mortgage rate, published weekly and
distributed via the Federal Reserve's FRED API (series `MORTGAGE30US`). History back to 1971;
methodology changed Nov 2022 (survey now based on lender applications rather than the old
phone-survey method) — worth a comment in any ingestion code, not a bug.

## Why it could help
`backend/app/scoring/investment.py` defines:
```python
interest_rate: float = 0.065
```
as a hardcoded default on the `Assumptions` dataclass. Every cap-rate, cash-on-cash, and
amortization number the valuation math produces rests on that single number, which someone has to
remember to update by hand as real rates move. A weekly live series removes that maintenance
burden and keeps every projection honest to current financing conditions.

## Evaluation
- **Geography:** national only — one series, no regional breakout. That's fine here since it's a
  macro input to the investment math, not a neighborhood-level metric.
- **Update frequency:** weekly.
- **Cost/access:** FRED's API is free with instant self-service key signup (no approval wait). A
  single weekly series needs at most one request per refresh cycle, so whatever the exact rate
  limit is, it isn't material here — I didn't confirm the actual requests-per-minute ceiling
  against FRED's own docs this run, and an earlier draft of this memo stated a specific number
  that wasn't actually sourced from anything; dropped it rather than ship an invented figure.
- **License:** this is the one candidate in this run with a genuinely open question, and it's
  actually two separate questions. First, FRED's general FAQ language mentions "personal,
  non-commercial use" in places, while the separate API Terms of Use explicitly contemplate
  building applications on the API — these likely don't conflict (FRED-powered commercial fintech
  tools are common), but need a direct read. Second, and distinct: `MORTGAGE30US` is Freddie
  Mac's PMMS data redistributed via FRED, not an original Fed series, so Freddie Mac's own
  attribution/copyright terms may apply on top of FRED's API terms — that's a separate check, not
  covered by clearing FRED's terms alone. I could not fetch fred.stlouisfed.org directly this run
  (sandbox DNS/proxy issue), so both are flagged rather than cleared, per the project's license
  hard rule.

## Caveats / what to re-check before implementing
- **Read the FRED API Terms of Use in full** (fred.stlouisfed.org/docs/api/terms_of_use.html)
  before writing an adapter — don't take the search-snippet summary above as a clearance.
- **Separately check Freddie Mac's attribution/copyright terms** for PMMS data, since this series
  isn't an original Fed product.
- This doesn't fit the usual `neighborhood_metric` shape (`kind: neighborhood`) — it's a single
  national scalar that `investment.py`'s `Assumptions` should read as a live default, so it may
  need a small "macro settings" refresh path rather than a standard `Source` subclass with NTA
  percentile scoring.

## Recommendation
**Recommend, conditional** on confirming the commercial-use terms directly against FRED's own
page before implementation. If that clears, this is a small, high-value fix: a hardcoded
assumption becomes a live, free, weekly-updating number with almost no ongoing maintenance.
