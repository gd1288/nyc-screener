# FHFA House Price Index (HPI) -- research memo

**Date:** 2026-10-15 | **Candidate file:** `research/candidates/fhfa-house-price-index.json` | **Recommendation: RECOMMEND**

## What it is
A repeat-sales house price index published by the Federal Housing Finance Agency. The quarterly/
monthly "Master HPI" file is confirmed at national, census-division, state, and metro-area level,
built from Fannie Mae/Freddie Mac-securitized mortgage transactions back to January 1975. FHFA also
publishes separate county, ZIP5, and census-tract files -- the tract file is explicitly labeled
developmental/experimental, and this run did not confirm the county/ZIP5 files' exact cadence or
history depth (the FHFA download page itself wasn't fetched directly).

## Why it could help
This project already ingests Zillow's ZHVI (`zillow_research.py`) as its neighborhood appreciation
signal, but Zillow's coverage thins out fast outside major metros -- a real tension with this
project's stated goal of generalizing to any US neighborhood. FHFA HPI's national/state/MSA series
has the deepest history (50 years) of anything considered this run, which makes it a plausible
second appreciation input and -- more importantly -- a candidate backtest benchmark: the
`research-sources` skill's own evaluation step names "FHFA tract HPI growth" as the thing a new
candidate series should be checked against, implying the project expects some FHFA series to exist
in the pipeline eventually. (Whether that ends up being the tract file specifically, or the more
reliable county/MSA file, needs its own look -- see caveats below.)

## Evaluation
- **Cost / access:** free, direct CSV/JSON/XML/SQL bulk download from fhfa.gov, no API key, no
  account, no rate limit encountered.
- **License:** federal public dataset; no restrictive ToS found (contrast with FRED, see that
  rejection memo).
- **Granularity:** national/state/MSA confirmed via the Master HPI file. County and ZIP5 appear to
  be separate files -- not confirmed directly against the FHFA datasets page this run. Census-tract
  file is explicitly labeled developmental/experimental by FHFA -- don't present it as authoritative
  without a caveat, and don't assume it shares the Master file's quarterly cadence.
- **History:** back to 1975 at the national/state/MSA level, far deeper than Zillow's ZHVI or any
  other candidate this run; county-level history depth not confirmed.
- **Quantitative correlation:** not run -- `app/research/evaluate_series.py` doesn't exist yet in
  this repo (Phase 4, per the skill), so this evaluation is qualitative only.

## Recommendation
Recommend. Clears every bar (free, keyless, no restrictive license found, national, deep history at
the national/state/MSA level) and fills a real coverage gap relative to Zillow. Before
implementation, fetch fhfa.gov/data/hpi/datasets directly to pin down which file gives county-level
data and at what cadence -- this memo's county/ZIP5 claims are inferred from search snippets, not
verified against the page itself. Suggested next step if approved: either add it as a second
appreciation series in neighborhood scoring, or build it as the backtest ground truth the skill
already assumes exists.
