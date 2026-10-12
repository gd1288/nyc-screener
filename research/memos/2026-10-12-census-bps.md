# Census Bureau Building Permits Survey (BPS)

**Date:** 2026-10-12 · **Verdict:** Provisional -- don't implement yet · **Gap:** US-wide
replacement for the NYC-only development pillar (`housing_database`, `rezonings` pull from NYC
DOB/DCP and have no equivalent outside NYC).

## What it is
A long-running Census Bureau survey of new residential construction permits, published monthly
(preliminary and revised) and annually, at national, state, CBSA, county, and permit-issuing-place
levels.

- **URL:** https://www.census.gov/construction/bps/
- **Granularity:** state / CBSA / county / place. **No tract or block-group level found.**
- **Coverage:** national.
- **Update frequency:** monthly, revised figures on the 18th workday of the month, plus annual
  totals.
- **History:** decades (the survey predates the 1970s in some form).
- **Access:** no official JSON API confirmed at `api.census.gov` for this dataset specifically.
  Official distribution is bulk text/CSV files under `www2.census.gov/econ/bps/` -- the same
  bulk-file pattern this project already uses in `zillow_research.py`, so a plain file fetch would
  work, no API key needed for this particular source (unlike `census_acs.py`, which does use the
  keyed Census API).
- **License:** US government work, public domain.

## Why it's not a clean fit today
The granularity doesn't match this project's current geographic grain. `backend/CLAUDE.md` requires
every Growth Score metric to be "a percentile within its comparison set" -- today that's all NYC
NTAs. BPS's finest level is county/place, and NYC is five counties. Forced into the `development`
pillar today, nearly every NTA in a borough would get the *same* BPS value, which is close to
useless as a ranking signal at NTA granularity (contrast with EPA's walkability index, which is
block-group level and actually discriminates between NTAs).

## Evaluation
Not run through `app/research/evaluate_series.py` (doesn't exist yet), and wouldn't be meaningful
yet regardless -- correlating a county-level series against this project's NTA-level FHFA/ZORI frame
doesn't test anything until the area-model/CBSA migration mentioned in `backend/CLAUDE.md` actually
exists.

## Recommendation
**Provisional.** The source itself is clean on every other axis (free, no login, public domain,
decades of history, monthly cadence) -- the only blocker is that this project's current geography is
finer than what BPS offers. Once the CBSA-level area model lands, re-evaluate this specific
candidate (it's one of the stronger national options at that point) rather than re-researching
development-pillar sources from scratch.
