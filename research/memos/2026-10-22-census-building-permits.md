# Census Building Permits Survey (BPS)

**Recommendation: do not recommend (for now)**

## What it is
Census's monthly count and valuation of new privately-owned housing units authorized by building
permits, at national/state/MSA/county/place level. Since a January 2022 methodology change
(cutoff sampling), county-level estimates are complete rather than partial. Preliminary national
figures release around the 12th workday of the month; county detail follows in the revised
release around the 17th–18th workday.

## Why I looked at it
Every existing growth signal in `backend/app/sources/development.py` and `transit.py`
(rezonings, housing_database, subway_access, planned_catalysts) is demand-side or
infrastructure-side. Permit volume is the one direct supply-side counterweight: a neighborhood
flooding with new permitted units might mean more competing inventory 2–3 years out, which could
cut against — not with — a "growth" read built purely from demand signals.

## Evaluation
- **Access method — the actual blocker**: I could not confirm a documented, clean REST API for
  county-level BPS in the two searches I spent on this. Census's `api.census.gov/data/timeseries/
  eits` catalog covers national economic indicators (`bfs`, `m3`, `ftd`, etc.) but a `bps` entry
  didn't surface there. County-level BPS data appears to live in the separate
  `census.gov/construction/bps` bulk-file system (monthly text/CSV releases), which means an
  adapter would need to parse fixed-format file releases rather than call a JSON API — meaningfully
  more work than the other candidates in this batch.
- **Sign ambiguity**: unlike mortgage rate or appreciation benchmarks, it's genuinely unclear
  whether more permits should move the Growth Score up or down without the quantitative
  evaluation tooling to check it empirically.
- **Overlap — checked directly, not assumed**: read `backend/app/sources/development.py`.
  `HousingDatabase` already pulls NYC DCP's Housing Database (Socrata `kyz5-72x5`), which is
  itself built from DOB job filings, and writes `pipeline_units_pct` from filed+approved+permitted
  units per NTA plus `new_units_5y_pct` completions. That's the same underlying concept BPS
  measures — real, confirmed overlap for NYC, not a guess. The one place BPS would add something
  new is outside NYC, where no DCP-equivalent exists, per this project's stated goal of
  generalizing to any US neighborhood/property type.
- **Cost/license**: free, no account, US government data.

## Recommendation
Do not recommend for NYC — it would duplicate `HousingDatabase`'s existing permit-pipeline
metrics. The access path is also a real problem for a future national rollout: "parse monthly
fixed-format federal file releases" is a bigger lift than this batch's other candidates, for a
signal whose direction (more permits = good or bad for the score?) isn't even established. Revisit
specifically when/if this project's area-model migration reaches non-NYC regions, and once
`evaluate_series.py` exists to test the sign and magnitude empirically — not as a near-term NYC
addition.
