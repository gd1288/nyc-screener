# research-sources changelog

## (undated, pre-tony-stark baseline)
Original version: a self-contained forked skill (no dedicated subagent) with the full
search/evaluate/write-up procedure inline, including Phase-4-aware handling of
`research/registry.json` and `research/gaps.json` (gracefully skipped if those files don't exist
yet). Predates the ten-part convention.

## 2026-09-17 — restructured to delegate to research-analyst
Moved the full procedure (hard caps, 6-step method, stop condition, reporting) into the new
`research-analyst` subagent (`.claude/agents/research-analyst.md`), and slimmed this file to a thin
delegator — same shape as `debug` → `debugger`. Reason: a subagent's `tools:` list is an actual
permission boundary ("never implement a source" is now enforced by omitting `Edit` and by a
`.claude/hooks/guard.sh` rule keyed on `agent_type`), not just an instruction a forked skill context
was trusted to follow. Nothing about the actual research procedure changed — verified the moved
content is unchanged, only relocated.

**Structural check note**: still predates the ten-part structure (not migrated here — see the same
note on `add-data-source`/`ship`).
