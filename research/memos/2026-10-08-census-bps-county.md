# Census Building Permits Survey — county-level

**Candidate file:** `research/candidates/census-bps-county.json`
**Recommendation: weak — needs a second, deeper look before implementing**

## What it is
The Census Bureau's Building Permits Survey (BPS): counts and valuation of new privately-owned
housing units authorized by permit, collected monthly/annually from ~20,000 local permitting
jurisdictions nationwide, summarized at national/regional/state/MSA/county levels.

## Why it looked promising
The `development` pillar in `neighborhood.py` (`pipeline_units_pct`, `new_units_5y_pct`,
`rezoned_area_pct`) is backed entirely by NYC-only sources (`HousingDatabase`, `Rezonings` in
`app/sources/development.py`). A national permits series would be the natural analog for
generalizing this pillar beyond NYC, matching the project's stated US-wide goal.

## What this pass found (and couldn't confirm)
- Only roughly half of surveyed jurisdictions report **monthly**; the rest report annually — so a
  county-level *monthly* series has real, structural gaps, and final annual figures don't
  necessarily reconcile with the monthly totals.
- The Census timeseries API (`api.census.gov/data/timeseries/eits/bps`) appears to cover BPS data,
  but this research pass could not confirm whether it exposes **county-level** geography (vs. just
  national/regional/state) — official API documentation wasn't reachable in the searches run.
  Several of the county-level file references found were from older Census documentation whose
  current validity wasn't verified, and one FAQ pointed to calling/emailing the Census Residential
  Construction Branch for some geography/format combinations, which is not a clean self-serve path.
- No login or payment wall anywhere; it's a public-domain federal series either way.

## Recommendation
Weak — don't implement on the strength of this pass. The idea is sound and the licensing is a
non-issue, but the actual programmatic access path at county granularity needs confirming (check
whether `timeseries/eits/bps` truly supports `for=county` geography, or whether the only reliable
route is downloading the annual county ASCII/CSV releases directly from
`census.gov/construction/bps/`). Worth revisiting with a focused follow-up rather than carrying
forward now.
