---
name: Data source
about: Add, fix, or investigate a data source adapter
title: ""
labels: data-source
---

## Source
Name (if it exists) or the dataset/API being proposed. Link to the docs/ToS.

## Kind
- [ ] New source (use the `add-data-source` skill)
- [ ] Broken existing source (use the `debug` skill / debugger agent — check `app.cli diagnose` first)
- [ ] Research candidate (came from the `research-sources` skill — link the memo in `research/memos/`)

## Coverage
NYC-only / NY State / national. If national, does it fit the area model (tracts), or does it need
a new rollup?

## License / cost
Confirm free, no login wall, no clause blocking product use.

## Acceptance criteria
- [ ] Adapter has a real `probe()` (see the `add-data-source` skill, step 3) and
      `uv run python -m app.cli probe-sources` shows it reachable
- [ ] Fixture test added (recorded response, not live HTTP)
- [ ] `sources.yaml` entry with a sensible schedule
- [ ] `uv run python -m app.cli refresh <name>` succeeds once for real

## Verify by
`uv run python -m app.cli sources`, `... refresh <name>`, `... probe-sources` — paste the output.

## `/goal`
`<the /goal quality-gate condition for this issue — checks that must pass, and a turn cap>`
