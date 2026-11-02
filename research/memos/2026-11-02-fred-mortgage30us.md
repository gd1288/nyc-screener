# FRED MORTGAGE30US (Freddie Mac PMMS 30-yr fixed mortgage rate)

**Recommendation: do-not-recommend — blocked on licensing, don't implement**

## What it is
The weekly US average 30-year fixed mortgage rate from Freddie Mac's Primary Mortgage Market Survey,
redistributed via the St. Louis Fed's FRED platform. Source:
https://fred.stlouisfed.org/series/MORTGAGE30US . History back to April 1971; direct CSV via
`fredgraph.csv?id=MORTGAGE30US`, or the FRED API with a free key.

## Why it could help
`backend/app/scoring/investment.py`'s `Assumptions.interest_rate` defaults to a hardcoded `0.065`
with no data source behind it — not even a periodically-updated manual number. A live series would
let that default track actual market rates, and the 1971+ history would let a future backtest vary
financing cost by purchase date instead of applying today's assumption to every historical scenario.

## Evaluation
- **Coverage/granularity**: national only — financing rate doesn't vary by neighborhood, so this
  isn't a per-area metric like the project's other sources.
- **Update frequency**: weekly (Thursdays).
- **History**: back to 1971 — far more than any backtest horizon here needs.
- **Cost**: the FRED API key is free (instant self-service signup).
- **License — the actual issue**: this is Freddie Mac's copyrighted survey data, not a federal
  public-domain series (Freddie Mac is a GSE, not a federal agency). FRED's own Terms of Use
  (fred.stlouisfed.org/legal, fred.stlouisfed.org/docs/api/terms_of_use.html) state the service is
  for "non-commercial, educational, and personal uses" and that other uses — explicitly including
  commercial — "are subject to additional restrictions" / require the copyright holder's written
  permission. That runs directly into this project's license screen: "no clause blocking
  commercial/product use."
- **Correlation**: not evaluated — this is a financing-cost input, not a growth-score predictor, so
  FHFA HPI / ZORI correlation isn't the relevant check.

## Recommendation
The data is exactly what's missing, and the mechanics (free key, long history, simple CSV) are easy.
But FRED's ToS reads as restricting use beyond personal/educational/non-commercial without the
copyright holder's written permission, and this run's search budget didn't stretch to reading the
full ToS text directly (only secondary summaries) or to finding a cleaner federal-only alternative
for 30-year mortgage rates specifically (the Federal Reserve Board's own H.15 series covers Treasury
and prime-loan rates, not conventional mortgage rates). **Do not implement** until someone either
(a) reads the full FRED API Terms of Use and confirms this project's use qualifies, or gets written
permission, or (b) finds a genuinely public-domain substitute. This is the clearest example this run
of "sounds useful but fails the license check as written" — flagged as `do-not-recommend` rather than
softened to get a higher recommended-candidate count.

## Access note
`fred.stlouisfed.org` is not reachable from this session's network policy (DNS resolution failed on
fetch), so even the ToS text itself was only read via web-search summaries, never first-hand. Allow
that host before trying to settle the license question directly.
