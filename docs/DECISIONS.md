# Decisions log

Dated, one entry per decision that changes the plan, structure, or working rules. Newest first.
Add an entry (and update `docs/NEXT.md`) in the same session any such change is made. Facts about
what is built are NOT recorded here; run `app.cli status`.

## 2026-09-18
- **claude-mem disabled** (user-level `~/.claude/settings.json`). Memory is now CLAUDE.md, NEXT.md,
  this log, `research/criteria.yaml`, `app.cli status`, and auto-memory. Why: it recorded claims
  that later proved false (it reported `proforma.py` as built) and stalled on quota.
- **Main artifact is locked; all new work goes to the staging artifact.** Enforced by
  `.claude/hooks/artifact-guard.sh` and `.claude/artifacts.json`. Promote with
  `scripts/promote_artifact.py`, then publish to main only on the user's explicit say-so. Why: a
  backend rebuild had silently replaced the approved Stress test UI.
- **Criteria ledger** (`research/criteria.yaml`, validated by `app.cli criteria`) links research to
  approval to valuation factor to UI. Only the user moves entries to approved/rejected/live.
- **Agent boundaries live in config** (`.claude/agent-boundaries.json`), not in shell code, so adding
  an agent is a checklist (`.claude/agents/README.md`), not a hook edit.
- **criteria-proposer agent added.** It may suggest UI changes only for the staging artifact.
- **Product direction:** an interactive UI for valuation and screening; a backend that keeps
  researching, proposes new criteria that refine the valuation, and those flow into the UI. This is
  the baseline; layers get added on top.
