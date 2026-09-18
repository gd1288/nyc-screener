# Adding an agent to this project

An agent is four small pieces. Copy an existing one (`criteria-proposer` is the read-only template,
`research-analyst` the one with web access) and fill in this checklist.

1. **Agent file** `.claude/agents/<name>.md`: `name`, a one-line `description` that says when to use it,
   `model` (sonnet by default; haiku for pure triage; opus only for valuation math review),
   `tools` (the fewest that work; no Bash unless needed), `memory: project`.
2. **Boundaries** in `.claude/agent-boundaries.json`, keyed by the same `name`: `allow_write_paths`
   and/or `deny_write_paths`, `deny_bash_patterns`, and a `reason`. `hooks/guard.sh` enforces it; no
   shell editing.
3. **Skill** `.claude/skills/<verb>-<noun>/SKILL.md` with `context: fork` and `agent: <name>`, so the
   agent's noisy work never enters the main session. The skill also says what the main session
   does afterwards (validate, summarise, ask for approval).
4. **Register it**: add the files to a phase in `docs/phases.yaml`, add a line to this list, and a
   dated entry in `docs/DECISIONS.md`.

Rules every agent follows: hard caps (searches, rows, files); read small files (ledger, gaps,
registry), not history; write results to files and reply in ~10 lines; never decide approvals, never
publish artifacts, never touch the main artifact.

## Current agents
| Agent | Job | Writes | Entry point |
|---|---|---|---|
| research-analyst | Find and evaluate free data sources | `research/` (not `backend/app/sources/`) | `/research-sources` |
| criteria-proposer | Propose new valuation criteria and staging UI ideas | `research/` (not registry/evals) | `/propose-criteria` |
| valuation-reviewer | Read-only review of valuation math | nothing | used before merging valuation changes |
| debugger | Investigate and fix failures | code | `/debug` |
