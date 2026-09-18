---
name: add-data-source
description: Add a new data source adapter to the screener (backend/app/sources/). Use whenever the user wants to plug in a new free dataset — Census, Socrata/open-data, a CSV/API feed — as a neighborhood metric, sales/listings feed, or boundary source. Covers the adapter contract, coverage tagging, probe wiring, fixture tests, license check, and sources.yaml registration.
---

# Adding a data source

Follow this checklist in order. Each step exists because skipping it caused a real bug earlier in
this project (see the "why" notes) — don't shortcut them.

## 0. Before writing code
- Check it's actually free and has no restrictive ToS (no login wall, no "non-commercial only"
  clause that would block this being a real product later). Note the license/ToS URL in the
  adapter's docstring.
- Check `backend/sources.yaml` and `research/registry.json` (once Phase 4 exists) for an existing
  or previously-rejected source covering the same signal — don't duplicate.
- Decide `kind`: `boundaries`, `neighborhood` (writes `NeighborhoodMetric` rows), `sales`,
  `listings`, or `sold_check`.
- Decide coverage: is this NYC-only (a Socrata NYC Open Data dataset), NY State
  (`data.ny.gov`), or national (Census, FHFA, EPA, etc.)? National sources should be written
  against the area model (Phase 1's `areas` table) once it exists, not hard-coded to NTAs — check
  whether that migration has landed before choosing which key to write against.

## 1. Write the adapter
Subclass `Source` in `app/sources/base.py`:
```python
class MyNewSource(Source):
    kind = "neighborhood"
    requires = ["some_api_key"]        # settings keys that must be non-empty, or the source is
                                        # skipped (not errored) via SourceSkipped — see below
    description = "One line: what this is and its dataset ID, e.g. 'NYC Open Data abcd-1234'"
    probe_socrata = ("data.cityofnewyork.us", "abcd-1234")   # see step 3 — do this now, not later

    def run(self, ctx: SourceContext) -> int:
        ...
        return self.write_metrics(ctx, metrics, as_of)  # for kind="neighborhood"
```
- If a required setting is missing, `raise SourceSkipped("why")` — this records `status="skipped"`
  in `source_runs`, not `"error"`, so `app.cli diagnose` and `session-health.sh` don't treat a
  not-yet-configured source as broken.
- For paged open-data queries, reuse `app/sources/socrata.py`'s `query`/`nyc`/`nys` helpers rather
  than hand-rolling pagination — a naive query hit Socrata's default 20,000-row limit before
  reaching the target rows once already in this project (see ACRIS in git history); the existing
  helper pages correctly.
- If the metric needs point-in-polygon rollup to neighborhoods, reuse
  `app/geo.NeighborhoodIndex` (via `ctx.geo`) rather than reimplementing that geometry.

## 1a. Large national files: use DuckDB, don't load whole
If the source is a large national bulk file (FHFA tract HPI's ~90MB CSV, Census LODES, ZIP Business
Patterns, and similar Phase 1 national sources), query it with DuckDB's `read_csv_auto` filtered by
a state/county SQL clause — never `pandas.read_csv` the whole thing into memory. As of 2026-09-17
`duckdb` is **not yet a backend dependency** — add it (`uv add duckdb`) the first time this pattern
is actually needed, don't assume it's already there. NYC-only sources that are already small (a
single Socrata dataset) don't need it. Verify the filtered load stays well under memory limits for
a full-size run, not just a small local sample — a filter that works on a NY-only slice can still
blow up if accidentally applied to the unfiltered national file.

## 2. Scoring direction, if this feeds a score
If the metric feeds `app/scoring/neighborhood.py`, set `higher_is_better` correctly on its
`MetricDef` — getting this backwards silently inverts the percentile and nothing will look
obviously wrong (crime and distance-to-transit are `higher_is_better=False`).

## 3. Wire a probe (required, not optional)
Every source must implement a real, side-effect-free reachability check, used by
`app.cli probe-sources` for the weekly uptime workflow:
- Backed by one Socrata dataset → set `probe_socrata = (domain, dataset_id)`; the base class's
  default `probe()` does a `$limit=1` GET for you.
- A plain file/API URL → set `probe_url = "..."` (prefer a URL the adapter's own `run()` already
  depends on, so the probe tests something real).
- Reads a local file (like `PlannedCatalysts`/`catalysts.yaml`), needs to skip a check that would
  itself spend a budget (like `RentCastListings`), or has some other reason no generic check
  applies → override `probe(self, ctx) -> tuple[bool | None, str]` directly and say why in a
  comment. `ok=None` means "not probed", which `probe-sources` reports but doesn't count as a
  failure — use it, don't fake a `True`.
- Verify it for real: `cd backend && uv run python -m app.cli probe-sources` and confirm your new
  source shows `.` (ok), not `?` (unprobed) or `!` (failing).

## 4. Register it
Add an entry to `backend/sources.yaml`: `adapter`, `schedule` (cron, NYC time; omit for
manual-only), and `options`. Keep sources that must run first (boundaries) above ones that depend
on them.

## 5. Test
Follow `backend/tests/test_core.py`'s style: adapters are tested against **recorded fixtures**,
never live HTTP (mock `ctx.http` or the socrata helper). Add at least one fixture test covering a
normal response and one covering a plausible failure (empty result, a missing field).

## 6. Verify
```
cd backend
uv run ruff check .
uv run pytest -q
uv run python -m app.cli sources          # confirms it loads and shows in the list
uv run python -m app.cli refresh <name>   # one real run — check records written, no error
uv run python -m app.cli probe-sources    # confirms the probe (step 3) actually works
```
Only after all four pass, use the `ship` skill.
