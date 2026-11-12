# FEMA National Flood Hazard Layer (NFHL)

**Recommendation: don't recommend (for now).**

## What it is
FEMA's current effective flood zone designations (100-year/500-year floodplain, etc.) as vector
polygons, nationwide. A hazard-zone snapshot, not a time series.

## Why it was considered
The project already has a flood-risk signal — `future_floodplain`
(`backend/app/sources/livability.py`), pulled from NYC Open Data dataset `27ya-gqtm`, a *2050s
climate-projection* layer specific to NYC. NFHL would add (a) current, not projected, flood zones,
and (b) national coverage, which the existing source doesn't have.

## Why it doesn't clear the bar right now
- **Cost/access**: FEMA's own documentation says FIRMs/FIS/NFHL geodatabases are free to download,
  but bulk *nationwide* access is the well-documented pain point — the Flood Map Service Center
  serves by state/county rather than one bulk endpoint, which is exactly why paid resellers
  (LightBox, nationalflooddata.com) exist. The cleanest free routes found are unofficial
  community scripts pulling per-state, not an official bulk feed.
- **Effort vs. this batch**: every other adapter in `app/sources/` hits one documented endpoint
  (a Socrata dataset, a single bulk CSV/API). NFHL would need per-state/county fetching and
  geometry handling closer to a new subsystem than a typical adapter — a meaningfully heavier lift
  than the other three candidates from this run.
- **Marginal value today**: the project is still NYC-only in practice (most sources are
  NYC-specific), so the "national" advantage isn't realized yet; it would mostly matter once the
  screener actually expands past NYC.
- **License**: data.gov describes it as intended for public access and use, but the authoritative
  FEMA licensing page wasn't located this pass — would need confirming before shipping anyway.

## Verdict
Shelve for now. Revisit if/when the screener expands past NYC and a maintainer is willing to
budget the extra per-state ingestion work, or if a cleaner single bulk endpoint turns up.

Candidate JSON: `research/candidates/fema-nfhl-flood-zones.json`
