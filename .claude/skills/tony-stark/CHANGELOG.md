# tony-stark changelog

## 2026-09-17 — v0.1.0 (created)
Initial version. Built after confirming no real `tony-stark` skill existed yet (the one entry in
the available-skills listing at the time was a session-scoped stub auto-materialized from the raw
request text, not authored content — see Gotchas in SKILL.md).

Decisions locked in during creation (per user answers, not invented):
- Distinct from the installed `skill-creator` plugin skill rather than wrapping it — tony-stark
  owns the ten-part structure and conversation-extraction mode; `skill-creator`'s eval/benchmark
  machinery stays out of scope here.
- Solo-project governance: user is owner/reviewer/authorized writer with no separate approval
  gate beyond an explicit yes on a shown draft.
- Source of truth, version history, and recovery copy are all git — no parallel tracking system.
- Audit receipt = this CHANGELOG.md (per skill produced) plus the user's own git commit.
