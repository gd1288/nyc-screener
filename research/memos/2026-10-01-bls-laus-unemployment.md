# BLS Local Area Unemployment Statistics (LAUS)

**Candidate file:** `research/candidates/bls-laus-unemployment.json`
**Recommend:** Conditional (not now; revisit at US-generalization phase)

## What it is
BLS's county/metro-level unemployment rate, labor force, and employment counts, published
monthly for ~7,500 areas nationwide. Flat files (no API key needed) live under:

```
https://download.bls.gov/pub/time.series/la/
```

A separate BLS Public Data API also exists but needs a free registration key beyond a low daily
query threshold -- the flat files avoid that.

## Why it could help (and why not yet)
Employment growth is a textbook demand-side driver of housing demand, so this is a reasonable
candidate in principle. But LAUS's finest useful geography here is **county**, and NYC is 5
counties (one per borough). That means this source could only ever contribute 5 distinct values
across the entire NYC screener -- it can't discriminate between NTAs, which is the unit the
Growth Score actually ranks. It's not useless, it's just not resolution-matched to how this
project currently scores neighborhoods.

## Evaluation
- **Coverage/granularity:** national; county / metro / some sub-county cities. For NYC that's
  borough-level only.
- **Update frequency:** monthly.
- **History:** flat files split across multi-year ranges; combined coverage spans the 1990s to
  present (exact earliest year not independently confirmed this run -- see caveat below).
- **Cost/license:** free, public-domain federal data, no login for the flat files.
- **Existing overlap:** none -- the screener has no employment/labor-market source today.
- **Quantitative correlation:** not run (`evaluate_series.py` doesn't exist yet in this repo, and
  a 5-value county series isn't a meaningful input to a tool built to score per-neighborhood
  correlation anyway).

## Verification caveat
`download.bls.gov` is blocked by this sandbox's outbound network policy -- could not fetch the
actual directory listing or confirm today's file-naming scheme (some older third-party write-ups
reference files split by 5-year windows that may have since been reorganized). Everything above
is corroborated by search snippets and BLS's own documented LAUS methodology, not a live fetch.

## Recommendation
**Conditional, not now.** The resolution mismatch (5 boroughs vs. dozens of NTAs) makes this a
poor fit for the screener as currently scoped to NYC. Its real value shows up once the project
scores metros outside NYC, where county-level unemployment is a standard, well-validated growth
input and there's no finer-grained alternative readily available. Keep in the backlog for that
phase; don't implement in isolation now.
