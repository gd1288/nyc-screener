# EPA National Walkability Index -- research memo

**Date:** 2026-10-15 | **Candidate file:** `research/candidates/epa-walkability-index.json` | **Recommendation: RECOMMEND (lower priority)**

## What it is
A national walkability score for every US Census block group, built by EPA from four variables in
its Smart Location Database (2019 block-group vintage, 2021 release). Direct ZIP download, no key.

## Why it could help
The project's only mobility/access signal is `subway_access` (`transit.py`), which is explicitly
NYC-subway-specific and cannot generalize to any other US market -- a direct gap relative to the
project's stated goal. EPA's walkability index is a national, block-group-granularity substitute or
complement that would work anywhere in the US.

## Evaluation
- **Cost / access:** free, direct ZIP download (`edg.epa.gov/EPADataCommons/public/OA/WalkabilityIndex.zip`),
  no key, no account.
- **License:** federal government work, effectively public domain (data.gov doesn't state an
  explicit license but marks it a U.S. Government Work).
- **Granularity:** census block group -- finer than anything else considered this run.
- **Update frequency / history:** this is the weak point. It's a single current vintage (2019-based,
  2021 release); an older 2010-based version exists but is superseded. There's no real time series,
  so it can't feed a trend signal or a backtest the way FHFA HPI or BLS LAUS can.
- **Quantitative correlation:** not run (no evaluation tooling yet; also not meaningful for a
  static, non-time-series dataset).

## Recommendation
Recommend as a one-time livability-factor baseline (replacing/complementing the NYC-only
`subway_access` factor outside NYC), not as a growth-score trend input. Lowest priority of the four
recommended candidates this run, specifically useful only for the US-generalization goal rather than
for improving NYC scoring itself.
