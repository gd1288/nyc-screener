# HUD: Fair Market Rents (FMR)

**Recommendation: Conditional — lower priority this run.**

## What it is
HUD's administrative estimate of gross rent at roughly the 40th percentile of the local rental
market, by bedroom count, published annually by county/metro area. Used to set Section 8
payment standards. Static history and current-year files at
`https://www.huduser.gov/portal/datasets/fmr.html`, no login required for the file downloads
(HUD's separate FMR *API* does require creating an account — intentionally avoided by proposing
the static-file path instead).

## Why it could help
A second, administrative rent-level benchmark by county, complementing `zillow_research`'s
ZORI — most useful as a fallback in smaller markets where Zillow's rent index has thin or no
coverage.

## Evaluation
- **Coverage/granularity**: national, county/metro level.
- **Update frequency**: annual.
- **History**: a standing "FMR History 1983-Present" file is published; the all-bedroom
  breakout for that history file was only confirmed on an archived version of the HUD page
  during this search, not the current live page — worth re-checking if implemented.
- **Cost / access**: free; the static files need no account (the FMR API does, so use the
  files, not the API).
- **License**: federal agency publication, no reuse restriction found.
- **Quantitative correlation**: not run — no evaluation tooling exists yet in this repo.

## Recommendation
Conditional. Free and nationally comprehensive, fitting the generalization goal, but annual
cadence is coarser than everything else evaluated this run, and in the markets this screener
already serves well, Zillow ZORI covers the same ground — so the marginal value is concentrated
in exactly the smaller/thinner markets this project hasn't prioritized expanding into yet.
Worth building if/when that expansion happens; not a near-term priority today.
