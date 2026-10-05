# BLS Local Area Unemployment Statistics (LAUS) — county unemployment rate

**Candidate file:** `research/candidates/bls-laus-county-unemployment.json`
**Recommendation: weak recommend — validate before implementing**

## What it is

BLS's county-level unemployment/employment/labor-force series, covering 7,500+ areas nationwide.
Monthly cadence; county-level data is **not seasonally adjusted** (only state-and-above gets
seasonal adjustment). Flat-file downloads (e.g. `bls.gov/lau/laucnty24.xlsx`) need no credential;
the Public Data API v2 needs a free key for the better quota.

Confirmed API limits (verified directly, not just inferred): unregistered access gets 25
queries/day and 25 series/query covering 10 years; a free registered key raises that to 500
queries/day, 50 series/query, and 20 years per query.

## Why it could help

Nothing currently in `scoring/neighborhood.py` tracks a local economic/employment trend. Census
ACS (`census_acs.py`) covers income, education, and population, but those are slow-moving 5-year
comparisons, not a monthly leading indicator. County unemployment trend is a genuinely new kind of
signal, not a duplicate of anything already ingested.

## Evaluation

- **Measures:** unemployment rate, labor force, employment counts, by county.
- **Granularity:** county (and state, metro, sub-state place).
- **Cost:** free; a registered key is free and immediate via
  https://data.bls.gov/registrationEngine/.
- **License:** US government work, public domain.
- **History:** generally 1990-present for county series — enough for a meaningful backtest.
- **Rate limit:** the real implementation cost here. A full monthly sweep of ~3,000 US counties
  needs batching (up to 50 series per request) spread across multiple calls — more moving parts
  than the other three candidates, which are each a single series or a single flat-file pull.

No quantitative correlation run this cycle — `app/research/evaluate_series.py` doesn't exist yet.
This is the one candidate of the four where that gap matters most: unlike mortgage rates (a known
cost input) or HPI/permits (established appreciation/supply signals), "does county unemployment
trend actually lead or correlate with condo price appreciation" is an open empirical question, not
something to take on faith because it sounds intuitively useful.

## Recommendation

Hold for now relative to the other three. Not rejected — the data is real, free, and fills a
genuine gap — but it's the weakest-justified of the four candidates reviewed this run, and it
carries the most implementation overhead (seasonal-adjustment smoothing needed at the county
level, plus batched API calls for a nationwide sweep). Once
`app/research/evaluate_series.py` exists, this is the candidate to run through it first, before
committing adapter-building effort: confirm it has measurable lead/lag against FHFA HPI growth or
Zillow ZORI before implementing, per the procedure's own instruction not to talk up a
"sounds-useful" source that hasn't shown correlation.
