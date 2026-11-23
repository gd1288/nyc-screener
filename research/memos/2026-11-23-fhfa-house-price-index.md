# FHFA House Price Index (HPI)

**Recommendation: Conditional — revisit once backtest tooling exists.**

## What it is
A repeat-sales home-price appreciation index built from conforming-mortgage transactions,
published quarterly by the Federal Housing Finance Agency at national/state/MSA/county/tract
levels. Free static downloads at `https://www.fhfa.gov/data/hpi/datasets`, no login.

## Why it could help
Two possible roles: (a) a second appreciation series to backfill `zillow_research`'s ZHVI in
counties where Zillow's coverage is thin, or (b) the backtest *benchmark* this project's own
`.claude/skills/research-sources/SKILL.md` procedure already names — "correlation and lead/lag
of the candidate series against FHFA tract HPI growth" — once `app/research/evaluate_series.py`
(Phase 4) is built.

## Evaluation
- **Coverage/granularity**: national, down to county (tract-level exists for some products).
- **Update frequency**: quarterly (some products monthly).
- **History**: national back to 1975; state/MSA generally 1980s on; county/tract vintages
  vary and can be shorter.
- **Cost / access**: free, static downloads, no login.
- **License**: described by FHFA as "publicly available"; the HPI name itself is a registered
  trademark (branding protection, not a reuse restriction). Could not fully verify FHFA's
  terms-of-use page directly — `fred.stlouisfed.org`-style direct fetches to fhfa.gov were not
  reachable from this session's network policy, so this is based on search-indexed FHFA FAQ
  content rather than a direct read of the live ToS page. Worth a final check before shipping.
- **Quantitative correlation**: not run — the evaluation tooling this would feed doesn't exist
  in this repo yet.

## Recommendation
Conditional, not rejected. As a live growth-score input it's largely redundant with the
already-wired `zillow_research` source in markets this screener currently covers well. Its
clearer near-term value is as the backtest benchmark the project's own research procedure
already anticipates — so the natural trigger to revisit this is "once
`app/research/evaluate_series.py` exists," or sooner if a specific county is found where
Zillow's appreciation coverage is too sparse to drive the Growth Score.
