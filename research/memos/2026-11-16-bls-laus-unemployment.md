# BLS Local Area Unemployment Statistics (LAUS)

**Recommendation: defer — don't implement yet** (rank #3 of 3 this run)

## What it is

BLS's monthly county/MSA/city unemployment-rate and labor-force estimates, covering roughly 7,600
areas nationally. Part of the standard federal labor-statistics program (same family as the
payroll/CPI releases).

## Why it looked promising

No employment or labor-market signal exists anywhere in this codebase today — a grep for
`unemployment`/`LAUS`/`employment` across `backend/` turned up nothing. Local job-market strength
is a textbook housing-demand driver, so this looked like a real coverage gap worth checking.

## Why it doesn't clear the bar right now

For NYC specifically, LAUS's finest standard granularity is **county**, and NYC's 5 counties are
exactly the 5 boroughs. Across this project's ~200 neighborhoods (NTAs), that means every
neighborhood in the same borough would get the *identical* value for this metric — only 5 distinct
numbers spread across 200 neighborhoods.

`backend/CLAUDE.md`'s scoring invariants are explicit: every metric becomes a percentile within its
comparison set (today, all NYC neighborhoods). A 5-value metric percentiled across 200 neighborhoods
carries almost no information at NYC's current granularity — it would separate Manhattan from Staten
Island and nothing else.

This isn't a problem with the data; it's a mismatch with the current comparison-set granularity.
Once the area-model migration moves comparison sets to CBSA (so neighborhoods are compared within
their own metro, and county-level data becomes meaningful as a way to compare *across* metros rather
than within one), this would be a much stronger candidate.

## Evaluation (for the record)

- **Granularity:** county/MSA/city, monthly.
- **Cost:** free. BLS's Public Data API works unauthenticated at low volume; v2 (needed for the
  request volume a recurring multi-county pull implies) needs a free registration key — same shape
  as Census/FRED, not a new kind of friction. A bulk flat-file download also exists for recent
  months without any key.
- **License:** federal statistical data, ordinarily public domain; not independently re-confirmed
  this run (bls.gov wasn't fetched directly — see note below), but this is the same low-risk
  category as Census, which the project already treats as clean.
- **History:** monthly county data generally available back to roughly 1990.
- **Correlation:** not computed (`evaluate_series.py` doesn't exist).

## Verdict

Defer. Say so plainly rather than talking it up: the data itself is fine, free, and well-documented,
but at NYC's current neighborhood-level granularity it would add a metric with almost no
discriminating power. Revisit after the CBSA area-model migration, where county-level data is a
natural fit.

## Network note

`bls.gov`/`api.bls.gov` were not fetched directly this run (not attempted, given the other two
candidates already hit network-policy blocks on their primary hosts — see those memos). License and
API details above rely on search-engine snippets of third-party and BLS-adjacent pages, not a direct
primary-source read.
