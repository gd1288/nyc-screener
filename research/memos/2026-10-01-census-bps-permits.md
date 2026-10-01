# Census Bureau Building Permits Survey (BPS)

**Candidate file:** `research/candidates/census-bps-permits.json`
**Recommend:** No (for now)

## What it is
Census's monthly/annual count of new privately-owned residential building permits authorized, by
units-in-structure, down to county/CBSA/place level. Free ASCII/comma-delimited files, no key:

```
https://www.census.gov/construction/bps/
```

## Why it doesn't clear the bar right now
This would normally be a reasonable supply-side growth signal, but `backend/app/sources/
development.py`'s `HousingDatabase` source already ingests NYC DCP's own Housing Database --
completed units by year plus filed/approved/permitted pipeline counts -- at **2020 NTA**
granularity, which is finer than BPS's county/CBSA level and specific to NYC's own permitting
process. For the project's only currently-scored market, adding BPS today would just be a
coarser, redundant version of a signal the screener already has at better resolution.

## Evaluation
- **Coverage/granularity:** national; county / CBSA / place. For NYC, county = the 5 boroughs,
  strictly coarser than the NTA-level data `HousingDatabase` already provides.
- **Update frequency:** monthly, plus an annual cumulative release.
- **History:** county/place files back to 1980 per Census's own description.
- **Cost/license:** free, public-domain federal data, no login.
- **Existing overlap:** significant -- see above. `HousingDatabase`
  (`backend/app/sources/development.py`) already covers this ground for NYC.
- **Quantitative correlation:** not run (no `evaluate_series.py` in this repo yet).

## Verification caveat
`census.gov` is blocked by this sandbox's outbound network policy -- could not fetch the actual
file index or confirm current file paths. Corroborated via search results pointing at Census's
own `census.gov/permits` page and its documented ASCII offerings.

## Recommendation
**Don't recommend now.** The one market this project currently scores already has a better
version of this signal. BPS's real value is as the supply-side counterpart to BLS LAUS (see that
candidate's memo) once the screener generalizes to metros outside NYC, where there's no DCP-style
NTA-level alternative. Revisit together with BLS LAUS when a second metro is actually being
onboarded, not before.
