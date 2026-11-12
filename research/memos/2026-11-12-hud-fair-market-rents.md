# HUD Fair Market Rents (FMR) API

**Recommendation: recommend, conditional on Small Area FMR (SAFMR) coverage for NYC.**

## What it is
HUD's annual Fair Market Rent estimates (by bedroom count, studio through 4BR) — the government
benchmark used to set Section 8 voucher payment standards. Published per HUD Metro FMR Area (not
per county within a metro) and, for many large metros, also as Small Area FMR (SAFMR) at
ZIP-code level. Available via a free API (`huduser.gov/hudapi/public`, free bearer token) and bulk
downloads.

## Important granularity correction
Plain county-level/metro-area FMR is **not useful for this project's NYC scoring**: all five
boroughs (each its own county) sit inside a single "New York, NY HUD Metro FMR Area" together
with Putnam, Rockland, and Westchester counties. That means ordinary FMR gives one number across
every NYC NTA — and `score_frame` in `neighborhood.py` scores NTAs *relative to each other*, so a
metric that's identical for all ~200 NTAs carries zero signal. The version actually worth building
is **SAFMR at ZIP level**, which does vary within a metro.

## Why it could still help
The project's rent-growth and rent-yield metrics (`zori_cagr_3y`, `gross_rent_yield`) currently
depend on Zillow's ZORI, a private, metro-coverage-limited series. If SAFMR is published for NYC
ZIPs (needs confirming — see open questions), it's a free, no-trial, government rent series with
genuine intra-metro variation — a solid independent complement to ZORI, and it generalizes
nationally wherever SAFMRs exist.

## Evaluation
- **Cost**: free; registration-gated (free token) but no trial/paid tier found.
- **License**: governed by `huduser.gov/portal/dataset/api-terms-of-service.html`. A third-party
  mirror labels it "Public Domain"; terms reportedly require a non-endorsement notice when used in
  an app ("uses the HUD User Data API ... not endorsed or certified by HUD User"). No
  commercial-use restriction found. **Read the official ToS page directly before shipping** — this
  pass only checked mirrored summaries.
- **Granularity**: county/metro-area FMR gives one value for all of NYC — not usable for
  NTA-level scoring. SAFMR (ZIP-level) is the granularity that would actually differentiate NYC
  neighborhoods; must confirm it's published for this metro before implementing.
- **Update frequency**: annual, per federal fiscal year — a background/validation series, not
  something to poll often.
- **History**: multiple past fiscal years exposed; exact depth via the API wasn't confirmed this
  pass (only mirrors, not the official docs, were checked).
- **Quantitative evaluation**: not run — `app/research/evaluate_series.py` doesn't exist yet in
  this repo (Phase 4 not built). Correlation against ZORI/FHFA HPI should be the first thing done
  once that tool exists, before this is implemented.

## Open questions
- Confirm SAFMRs are actually published for NYC-metro ZIPs — this is the crux; if not, downgrade
  to don't-recommend, since plain FMR has no NYC neighborhood signal.
- How many fiscal years of history the API actually exposes vs. only bulk archives.
- Confirm the ToS wording directly from HUD, not third-party mirrors.

Candidate JSON: `research/candidates/hud-fair-market-rents.json`
