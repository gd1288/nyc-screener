# add-data-source changelog

## (undated, pre-tony-stark baseline)
Original version from Phase 0: a 7-step checklist (0–6) for adding a source adapter. Predates the
ten-part convention — kept as-is rather than force-migrated (see 2026-09-17 note below).

## 2026-09-17 — improvement
Added a new "1a. Large national files: use DuckDB, don't load whole" section, covering the
Phase-1 pattern (FHFA tract HPI, LODES, ZIP Business Patterns) of querying big bulk files with
`read_csv_auto` filtered by state/county SQL instead of loading them whole. Previously this file
only distinguished NYC/NY-State/national coverage, with no guidance on *how* to handle a large
national file once written against it. First draft of this section wrongly claimed `duckdb` was
already a backend dependency — checked `backend/pyproject.toml` for real, found it isn't yet, and
corrected the wording to say to add it when first needed instead.

**Structural check note**: `structural_check.py` reports this file doesn't follow the ten-part
structure — correct, it predates that convention (it's a numbered checklist, 0 through 6, not the
ten required sections). This edit didn't attempt to migrate the whole file to the new structure,
since that's a much bigger change than the one asked for. Flagged to the user as a candidate
follow-up (migrate Phase-0 skills — `add-data-source`, `research-sources`, `ship`, `debug` — to the
ten-part structure), not done here without a separate yes.
