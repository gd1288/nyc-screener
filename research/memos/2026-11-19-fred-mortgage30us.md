# FRED 30-Year Fixed Rate Mortgage Average (MORTGAGE30US)

**Recommendation: conditional - confirm Freddie Mac's redistribution terms before building**

## What it is
Freddie Mac's weekly Primary Mortgage Market Survey series, redistributed by the St. Louis Fed as
`MORTGAGE30US` on FRED. National average rate for a 30-year fixed conforming mortgage, prime
borrowers, published every Thursday. History runs back to April 1971. It excludes jumbo, FHA, VA,
and ARM loans.

## Why it could help
`backend/app/scoring/investment.py:21` sets the investment math's interest-rate assumption as a
dataclass default:

```python
interest_rate: float = 0.065
```

This feeds `monthly_payment`, `loan_balance`, and every downstream cash-flow/IRR projection shown
to a user (presumably overridable, since it's a plain default, not a constant). Nothing currently
refreshes it from reality. `MORTGAGE30US` is the standard free series for exactly this number -
one cached search snapshot this run showed it at roughly 7.40% for the week of Oct 15 2026 vs. the
6.5% default (~0.9pp gap), though that figure is from a search cache, not a live fetch this
session's network proxy blocked (`CONNECT tunnel failed, 403` on `fred.stlouisfed.org`) - confirm
the live value before relying on it.

## Access
- Keyless: `https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US`, no registration.
- Keyed (if a JSON API is preferred for consistency with other sources): free instant key at
  `fred.stlouisfed.org/docs/api/api_key.html`, then `api.stlouisfed.org/fred/series/observations`
  with `series_id=MORTGAGE30US&file_type=json`. Rate limit 120 req/60s per key.

## Evaluation against the project's bar
- **Free, no trial**: yes, both paths.
- **License - the actual open question**: this is *not* a plain government series. It's Freddie
  Mac's PMMS data, redistributed via FRED. Freddie Mac's Content Use Policy generally bars selling,
  republishing, or retransmitting site content without prior written consent, but carves out an
  exception for publishing "automatically updated data" like PMMS without that consent, under a
  limited royalty-free license "subject to... the terms and conditions for syndication" - those
  syndication terms weren't surfaced in this search. It's unclear whether that exception covers
  ingesting the series into a commercial product's data pipeline (vs. embedding a live widget on a
  page). **Confirm this before implementing** - check Freddie Mac's syndication terms directly, or
  fall back to FRED's own (separately permissive) API terms with clear PMMS attribution.
- **Granularity**: national only - not a neighborhood metric, so it doesn't plug into the Growth
  Score pillars. It's a macro input to the valuation/investment engine instead.
- **History**: 50+ years - no concern.
- **Scope caveat**: conforming, prime-borrower loans only; excludes jumbo/FHA/VA/ARM. A meaningful
  share of NYC condo purchases exceed the conforming loan limit, so treat this as a reasonable
  default/benchmark, not a precise rate for every loan this product models.
- **Correlation/backtest**: not applicable - this isn't a neighborhood-level growth predictor to
  correlate against FHFA HPI/ZORI, it's a financing-cost input.

## Recommendation detail
Still the strongest candidate found this run on cost/benefit - a concrete stale default, lowest
integration cost of anything evaluated (one national scalar, no geography join, no NTA crosswalk).
But it's marked conditional, not a flat recommend, because the PMMS redistribution terms for use
inside a commercial product genuinely need confirming first, and the jumbo-loan exclusion should
be disclosed wherever the rate is shown. If the license checks out, implement as a small fetch
that updates an `AppSetting` (or a new lightweight non-neighborhood source kind) consumed as the
default `Assumptions.interest_rate`, keeping `0.065` only as an offline fallback.
