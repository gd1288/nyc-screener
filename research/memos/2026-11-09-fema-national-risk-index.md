# FEMA National Risk Index (NRI)

**Recommendation: recommend**

## What it is
FEMA's National Risk Index gives every US county and census tract a composite risk score across 18
natural hazards (flood, wildfire, hurricane, earthquake, heat wave, etc.), plus expected annual loss,
social vulnerability, and community resilience sub-scores. It's a free direct bulk download (CSV/table,
shapefile, geodatabase) straight from FEMA, no login or key.

## Why it could help
`backend/app/sources/livability.py`'s `future_floodplain` source is NYC Open Data only. Outside NYC the
project currently has zero hazard/climate-risk signal, even though flood/fire/heat risk is exactly the
kind of thing a US-wide investment screener should factor into its livability/risk pillar. NRI is the
closest free, authoritative, nationally-complete substitute, at a granularity (tract) the codebase
already has a pattern for crosswalking into neighborhood geography — the same weighted-aggregation
approach `zillow_research.py` uses to map ZIP data onto NTAs.

## Evaluation
- **Coverage/granularity:** national, county and census tract.
- **Update frequency:** periodic editions (not a monthly/annual time series) — FEMA has released a
  handful of updated versions since launch, archived at `hazards.fema.gov/nri/data-archive`.
- **Cost:** free.
- **License:** Data.gov tags the dataset's license as the standard US government-works notice
  (`usa.gov/government-works`), implying no copyright restriction — but a sibling FEMA/CRSI dataset on
  Data.gov carries a different (EPA Science Hub) license tag, so the specific NRI download's bundled
  metadata should be checked directly before implementation, not assumed from the dataset family.
- **Quantitative evaluation:** not run — `app/research/evaluate_series.py` doesn't exist yet, and in
  any case NRI is a structural risk score, not a time series, so a correlation/lead-lag check against
  FHFA HPI or Zillow ZORI isn't the right evaluation for this one. Its value is as a risk adjustment to
  the growth score, not a return predictor, and should be evaluated that way (e.g., does higher NRI risk
  correlate with worse realized appreciation or higher insurance/carrying costs) if/when that kind of
  evaluation harness exists.

## Caveats
- Confirm the license on the actual downloaded file's metadata, given the conflicting tag seen on the
  related CRSI dataset.
- Tract-level granularity is finer than NYC's current NTA geography; needs a tract→NTA crosswalk for
  NYC, and will matter more broadly once the CBSA/area-model migration mentioned in `backend/CLAUDE.md`
  lands.
- Don't expect this to behave like a growth predictor in a backtest sense — it's slow-changing and
  structural.

## Bottom line
Recommend as a candidate for the "any US neighborhood" risk/livability pillar. Free, complete
nationally, and fills a real currently-NYC-only gap. Main pre-implementation step is nailing down the
license on the specific file and building the tract→NTA crosswalk.
