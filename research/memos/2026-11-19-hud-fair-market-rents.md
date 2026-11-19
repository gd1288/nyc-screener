# HUD Fair Market Rents (FMR) API

**Recommendation: conditional - defer to the US-generalization backlog, not an NYC gap today**

## What it is
HUD's annual Fair Market Rent estimates (40th-percentile gross rent) by metro area/county, with
Small Area FMRs at ZIP-code granularity for certain large metros including New York. Free API with
a self-serve registration token, or bulk spreadsheet downloads.

## Why it could help
Covers every US metro and nonmetro county, unlike Zillow's ZORI (the project's current rent
source, `app/sources/zillow_research.py`), which only covers roughly the 100 largest metros. For
the project's stated goal of generalizing past NYC to "any US neighborhood," HUD FMR is the
natural rent-data fallback for everywhere Zillow doesn't reach.

## Evaluation against the project's bar
- **Free, no trial**: yes, with a free registration token (same auth pattern as
  `CENSUS_API_KEY`/`RENTCAST_API_KEY` already handled via `requires` on existing sources).
- **License**: public-domain HUD data; ToS mainly bars implying HUD endorsement, not
  commercial/product use - full terms text wasn't fetched live this run, worth a quick confirm
  before implementation.
- **Granularity**: metro/county by default, ZIP-level ("Small Area FMR") for NYC specifically -
  finer than the project's NTA geography where it applies.
- **History**: annual back to the 1980s, though the current-year snapshot matters most since it's
  a rent-level estimate rather than a growth series.

## Recommendation detail
For NYC today this is close to redundant - Zillow ZORI already covers all five boroughs and
already feeds `zori_cagr_3y` and the rent-yield side of the `valuation` pillar. Adding HUD FMR now
would mean maintaining two rent sources for zero incremental NYC coverage. Its value is entirely
in the "any US neighborhood" future state: file this on the backlog for whenever the area-model
migration actually starts covering metros Zillow doesn't, and build it then as the rent-data
fallback path rather than now.
