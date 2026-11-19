# Census Bureau Building Permits Survey (BPS)

**Recommendation: conditional - defer to the US-generalization backlog, not an NYC gap today**

## What it is
Census's monthly Building Permits Survey: new privately-owned residential construction permits by
state, CBSA/metro, county, and ~9,000 individual permit-issuing places. No documented JSON/REST API
was found under `api.census.gov` - the closest match in the Economic Indicators Time Series API
(`timeseries/eits/resconst`) is a different product (New Residential Construction starts/completions,
not BPS permits). The real free access path is bulk flat files at `www2.census.gov/econ/bps/`, or
HUD's SOCDS Building Permits database (query UI + export, monthly back to Jan 1997).

## Why it could help
The project's `development` pillar (`backend/app/sources/development.py`) is built entirely from
NYC-specific sources: the DCP Housing Database and MIH rezonings, both NYC Socrata endpoints with
no equivalent outside the city. BPS is the natural national substitute, since every US county and
most permit-issuing places report to it monthly.

## Evaluation against the project's bar
- **Free, no key**: yes, flat files, no registration wall.
- **License**: public-domain federal data, no restriction found.
- **Granularity**: county or individual permit-issuing place - finer than NTA in principle.
- **History**: SOCDS place-level data back to January 1997; Census's own state/metro files go back
  further. Ample for a backtest.
- **Implementation cost**: higher than a typical adapter here - no clean JSON query, just
  fixed-width/CSV bulk files to parse and reduce to county or place level, then apportion to
  neighborhoods.

## Recommendation detail
This is the single most important source for making the `development` pillar work at all outside
NYC, but it shouldn't be built to improve NYC's score right now: the existing DCP Housing Database
is richer for NYC specifically (it breaks out filed/approved/permitted pipeline stages, which BPS
doesn't) and already works. Treat BPS as the pillar's documented path to national coverage, to
build when the area-model migration actually starts onboarding non-NYC metros - not before.
