# FHFA House Price Index (HPI)

**Candidate file:** `research/candidates/fhfa-house-price-index.json`
**Recommendation: recommend**

## What it is

The Federal Housing Finance Agency's repeat-sales home price index, published quarterly at the
state and MSA level and annually at the county level (the "Developmental Index"). History back to
1975 for the state series. Distributed as a single master CSV
(`https://www.fhfa.gov/hpi/download/monthly/hpi_master.csv` per FHFA's datasets page) with no API
key and no login.

Notably, this is the exact benchmark series the `research-sources` skill itself names for
quantitative evaluation ("correlation and lead/lag of the candidate series against FHFA tract HPI
growth and Zillow ZORI") — worth flagging that the skill's phrasing says "tract," but FHFA's finest
published geography is actually county, not tract. Tract-level HPI isn't a thing FHFA publishes.

## Why it could help

Today's price-appreciation signal (`zillow_research.py`) is Zillow's condo-tier ZHVI, mapped from
ZIP to NTA using where DOF condo sales actually land — a pipeline built specifically for NYC's
condo stock and NYC's own sales records. Per `CLAUDE.md`, this project's explicit goal is
generalizing beyond NYC to "any US neighborhood and property type." Zillow's condo-tier series
thins out or disappears in smaller metros; FHFA HPI, by contrast, covers every state and most
counties, because it's built from all conforming mortgage transactions nationwide, not scraped
listings.

Proposed use: not a replacement for Zillow ZHVI in NYC (where Zillow's monthly ZIP-level data is
finer-grained), but (a) a second independent series to sanity-check Zillow's numbers, and (b) the
guaranteed-available fallback appreciation series for `city_value_cagr_10y` /
`neighborhood_value_cagr_10y` whenever this screener is pointed at a metro where the condo-tier
Zillow series is thin or missing.

## Evaluation

- **Measures:** repeat-sales home price index (all transaction types, not condo-specific).
- **Granularity:** state/MSA quarterly; county only annual. This is the one real limitation —
  it can't replace a monthly ZIP-level series, only complement/backstop it.
- **Cost:** free, no key, no rate limit (it's a static file).
- **License:** US government work, public domain.
- **History:** 1975 (state), varies by MSA/county (many back to the 1980s-90s) — long enough for
  a meaningful backtest.

No quantitative correlation run this cycle (`app/research/evaluate_series.py` doesn't exist yet).
Once it does, this is the single highest-value candidate to run it against, since it's explicitly
the benchmark the evaluation step is meant to compare other candidates to — testing it against
itself isn't useful, but testing how well NYC-specific Zillow ZHVI tracks FHFA's independent
national series for the NYC MSA would be a good sanity check of the existing pipeline, separate
from this candidate's own merit.

## Recommendation

Implement. Of the four candidates reviewed this run, this is the simplest possible ingestion — no
credentials, no rate-limit handling, a single scheduled CSV pull — and it's the one source here
that most directly serves the "generalize past NYC" goal stated in the project's own `CLAUDE.md`.
