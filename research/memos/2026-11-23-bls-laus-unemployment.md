# BLS: Local Area Unemployment Statistics (LAUS)

**Recommendation: Conditional — not a near-term priority.**

## What it is
Bureau of Labor Statistics monthly labor force, employment, and unemployment-rate estimates
for ~8,300 areas (every US county, metro area, and state). Bulk flat files at
`https://download.bls.gov/pub/time.series/la/`, free, no account for this bulk-download path.

## Why it could help
A local unemployment rate / labor-market trend is a textbook neighborhood-growth signal
investors care about, and it's available for any US county — fitting the project's
generalization goal.

## Evaluation
- **Coverage/granularity**: national, county level.
- **Update frequency**: monthly.
- **History**: varies by area; many county series back to the early-to-mid 1990s.
- **Cost / access**: free; the bulk `time.series` flat files need no account. (A free API key
  is only required for BLS's API v2, a separate, higher-volume access path not needed here.)
- **License**: federal statistical publication, public domain.
- **Friction #1 — format**: the bulk files are fixed-width/pipe-delimited BLS "time.series"
  format, not CSV — meaningfully more adapter work than a plain CSV/JSON source.
- **Friction #2 — gaps**: during this run's search, a state labor-department page noted BLS
  canceled its October 2025 unemployment publication due to a government shutdown. The series
  can have unscheduled gaps a consuming pipeline needs to tolerate.
- **Overlap**: Census ACS (`census_acs.py`, already a wired-up source) already carries some
  labor-force/income data, so this isn't a wholly novel signal, just a higher-frequency one.
- **Quantitative correlation**: not run — `evaluate_series.py` doesn't exist yet in this repo.

## Recommendation
Conditional. Worth building once a dedicated labor-market pillar is prioritized for the Growth
Score, but it carries more adapter effort (non-CSV format, tolerating publication gaps) than
this run's top two candidates for a less novel signal given existing ACS coverage.
