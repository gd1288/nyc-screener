# FHFA House Price Index (county / census-tract)

**Date:** 2026-10-26 · **Candidate file:** `research/candidates/fhfa-house-price-index.json`

## What it is
FHFA's repeat-sales House Price Index, built from Fannie Mae/Freddie Mac mortgage data. The "Master"
file covers national/state/MSA quarterly; the "HPI@BDL" local files go down to county (`.xlsx`) and
census tract (`.csv`) annually. Free, U.S. government data, no login found for the download pages
themselves.

## Why it could help
Two distinct uses, and it's important not to conflate them:
1. **Second outcome series for the backtest.** `app/scoring/backtest.py` currently uses Zillow ZHVI
   (NYC ZIP-level, condo-tier only) as both the price series and the backtest outcome. FHFA tract HPI
   is a methodologically different, nationally-available series that could cross-check that backtest
   rather than relying on one vendor's model.
2. **National momentum input.** CLAUDE.md states the project's goal as "generalizing to any US
   neighborhood and property type." Zillow's condo-tier ZHVI only exists for a handful of dense
   metros; FHFA HPI, built from mortgage data, is available for essentially any US county or tract.

Note the circularity risk explicitly: the research-sources skill itself names "FHFA tract HPI growth"
as the *benchmark* other candidates should be evaluated against (step 4). That makes this one
foundational infrastructure, not a predictor to backtest against itself.

## Evaluation
Not run. `app/research/evaluate_series.py` doesn't exist in this repo yet (it's the Phase-4 tool the
skill describes), and this series is the intended benchmark for evaluating *other* candidates, not a
predictor to be scored the same way.

## Verification caveat
fhfa.gov returned `403 connect_rejected` from this session's egress proxy on every attempt (the same
block applied to all five candidate hosts this run, not FHFA specifically). Facts above come from
WebSearch summaries of FHFA's FAQ/download pages, not a direct fetch. **Confirm before implementing:**
the tract file's actual backdated history length (the master/county series go back to the 1970s/1996;
the tract-level file was released later and its depth wasn't confirmed here) and the exact current
file URLs, which FHFA has renamed before.

## Recommendation: **Recommend**
Clears the bar as useful national infrastructure the project doesn't have today, but frame it
correctly: it's a benchmark/second-opinion series and a path to national coverage, not a new scored
predictor pillar by itself. Worth building alongside (or just ahead of) `evaluate_series.py`, since
that tool needs exactly this series to do its job.
