# FRED MORTGAGE30US (30-Year Fixed Mortgage Rate)

**Candidate file:** `research/candidates/fred-mortgage30us.json`
**Verdict: recommend_with_caveat** (license needs human verification before implementation)

## What it is
A weekly national average 30-year fixed mortgage rate, sourced from Freddie Mac's Primary
Mortgage Market Survey (PMMS) and mirrored on FRED (Federal Reserve Bank of St. Louis) as series
`MORTGAGE30US`, back to April 1971. FRED access requires a free API key (same signup pattern as
this project's existing `CENSUS_API_KEY`), 120 calls/minute.

## Why it could help
`backend/app/scoring/investment.py`'s `Assumptions.interest_rate` defaults to a **hardcoded 0.065**
with no live-data path — every per-property return projection (mortgage payment, cash flow, NPV,
cap rate) runs off that stale constant unless a user manually overrides it per analysis. A single
weekly-updated national scalar would let that default track the actual prevailing rate. This is a
cheap, single-value series with no geographic-mapping problem (it's national), unlike every other
candidate in this batch.

## Evaluation
- **Coverage/granularity:** national only — a single series, no disaggregation. That's fine for
  this use case (a financing-cost assumption, not a neighborhood metric).
- **History:** back to 1971 — more than adequate.
- **Cost:** free API key, generous rate limit. No concern there.
- **License — the actual issue:** every search on FRED's API terms of use surfaced "personal,
  non-commercial use" language for the free tier, with commercial/product use requiring separate
  contact with the FRED team. I could **not** verify this against the primary source directly —
  `fred.stlouisfed.org` is blocked by this environment's network egress policy, so I only have
  secondary summaries, not the actual clause text. The underlying data source, Freddie Mac's PMMS
  archive, states data "may be used with proper attribution" but I found no confirmation of a
  documented bulk CSV/API endpoint or explicit language blessing redistribution inside a product's
  own API responses.
- **Correlation:** not applicable — like the FEMA candidate, this is an input parameter (financing
  cost), not a growth signal to correlate against HPI/ZORI.

## Recommendation
This is the one candidate in the batch where the *data* case is strong (real gap, cheap, national,
long history) but the *license* case is unresolved rather than clean. Recommend approving only
conditionally: before any `add-data-source` implementation, a human should actually read
`fred.stlouisfed.org/docs/api/terms_of_use.html` (or email the FRED team, contact info is on that
page) to confirm whether serving this value back to the app's users — not just using it
internally to compute a default — is covered by the free-tier terms. If it isn't, Freddie Mac's
own PMMS archive is the fallback primary source, but its redistribution terms need the same kind
of direct verification. Do not implement from this memo alone.
