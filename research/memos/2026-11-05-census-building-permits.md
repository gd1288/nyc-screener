# Census Building Permits Survey — national development pillar

**Don't recommend yet — history too short.**

## What it is
The Census Bureau's monthly Building Permits Survey: new residential unit permits by census
division, state, metro (CBSA), county, and permit-issuing place.

## Why it looked promising
The development pillar (`pipeline_units_pct`, `new_units_5y_pct`, `rezoned_area_pct`) is built
entirely from NYC DOB data (`app/sources/development.py`) and NYC rezoning records — the most
NYC-locked pillar in the whole scoring model, and a clear gap against the "any US neighborhood"
goal.

## Evaluation
- **Coverage/granularity**: national, county and metro.
- **Update frequency**: monthly.
- **History — the problem**: per Census's own announcement, complete monthly county/metro
  coverage only started in **2022** (earlier years were state-level/sampled only). This project's
  own metric (`new_units_5y_pct`) needs a 5-year trend and the pillar as a whole implicitly wants a
  multi-year pipeline view — 2022-onward isn't enough history to build that confidently yet.
- **Cost/license**: free, public domain, no key. I could not confirm an official modern Census API
  for county-level BPS in my searches (unlike ACS, which has a documented API this project already
  uses) — the practical route looks like static file downloads, or HUD's older SOCDS portal
  (place-level back to 1997, but a rougher interface).

## Recommendation
Revisit in a year or two once 2022+ coverage has accumulated enough years to support a real trend
metric, or if someone wants to pair it with HUD's longer SOCDS mirror despite its rougher
interface. Not worth building against today given the short official-coverage window.
