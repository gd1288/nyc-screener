# FRED MORTGAGE30US — 30-Year Fixed Rate Mortgage Average

**Recommendation: recommend** (rank #1 of 3 this run)

## What it is

A weekly US-average 30-year fixed mortgage rate, published by Freddie Mac's Primary Mortgage
Market Survey and distributed via the St. Louis Fed's FRED service (series `MORTGAGE30US`).
History back to April 1971. One national number per week — no geographic breakdown.

## Why it could help

`backend/app/scoring/investment.py:21` hardcodes the financing assumption every property's
cash-flow projection is built on:

```python
interest_rate: float = 0.065
```

That default silently drifts out of date as real rates move, and currently has to be noticed and
hand-edited. A weekly-refreshed live series would let this default track reality automatically,
while still letting a user override it per scenario (the `Assumptions` dataclass already supports
overrides).

This isn't a new predictive signal for the Growth Score — it's a fix for a stale constant that
affects every single investment-math number the app surfaces. Implementation is small: one scalar
series, no per-neighborhood join, no new geocoding.

## Evaluation

- **Geographic granularity:** national, no breakdown — by design, since mortgage rates aren't
  neighborhood-specific. This also means it would NOT be implemented as a standard `kind:
  neighborhood` `Source` (which exists to populate per-neighborhood `NeighborhoodMetric` percentiles
  — see `backend/CLAUDE.md`'s scoring invariants). It needs a different, simpler mechanism: a small
  stored "current assumptions" value the investment scoring reads, refreshed on its own schedule.
  That's a design call for whoever implements this, not resolved here.
- **Cost:** free. The plain CSV endpoint (`fredgraph.csv?id=MORTGAGE30US`) needs no key per
  secondhand sources. The structured FRED API needs a free registration key — the same shape this
  project already accepts for Census (`requires = ["census_api_key"]`), so this isn't a new kind of
  friction.
- **License:** not cleanly confirmed. `fred.stlouisfed.org` is outside this session's allowed
  network hosts, so primary terms couldn't be read directly this run (see Network note below).
  Secondhand: FRED tags the series "Copyrighted: Citation Required" (attribution needed, not a
  paywall/login). Freddie Mac's general Content Use Policy requires written consent to republish
  site content, but explicitly carves out automatically-updated series like PMMS data, granting "a
  limited, non-exclusive, non-transferable, royalty-free license" to republish it without separate
  consent — subject to syndication terms that weren't retrieved. Net read: looks usable with
  attribution, but this project's bar ("no clause blocking commercial/product use") isn't cleanly
  confirmed from secondhand sources alone. **Before implementing, read Freddie Mac's Content Use
  Policy and FRED's Terms of Use directly.**
- **History:** 1971–present, the longest of anything evaluated this run.
- **Correlation:** not applicable / not computed. `app/research/evaluate_series.py` doesn't exist
  yet, and this candidate is an assumption input (what rate to assume on a new loan), not a
  neighborhood-growth predictor to be benchmarked against FHFA/ZORI.

## Verdict

Recommend. Low risk, directly closes a concrete, already-identified gap (the hardcoded 6.5%
assumption), minimal implementation surface. The one real gate before shipping is confirming
redistribution terms with a direct read of Freddie Mac's/FRED's own pages, which needs
`fred.stlouisfed.org` reachable from wherever that read happens.

## Network note

This research session's environment does not allow outbound requests to `fred.stlouisfed.org` or
`www.fhfa.gov` (both resolved as blocked by network policy, confirmed via `WebFetch`). All facts
above about FRED/Freddie Mac came from third-party search snippets, not a primary-source read, and
are flagged as such. Implementing this source will need `fred.stlouisfed.org` added to the
environment's allowed hosts.
