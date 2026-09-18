# Decisions log

Dated, one entry per decision that changes the plan, structure, or working rules. Newest first.
Add an entry (and update `docs/NEXT.md`) in the same session any such change is made. Facts about
what is built are NOT recorded here; run `app.cli status`.

## 2026-09-18
- **UI knowledge lives in `docs/UI.md`.** Structure, components, checklist and changelog for the
  artifact; CLAUDE.md points to it. Why: UI facts were spread over a memory note, NEXT.md and this log,
  and auto-memory is per-machine, so a new session could miss them. Git-tracked docs reach every
  session and worktree.
- **Result bar is one sticky element for all four tabs,** content chosen by `TAB` in `bar()`. Added to
  staging with Read this first, cash flow insight, scenario summary, reset, per-card DSCR, tornado.
- **Backend is the only calculation engine.** The artifact's in-page `model()` is a prototype (it also
  uses flat 25%/23.8% sale-tax rates, unlike `taxes.py`); the app calls the backend. A parity test
  will compare them. Why: two engines silently diverge.
- **Product form: extend the existing Next.js app, local only, audience is the user.** No hosting,
  auth or database migration for now. Artifacts (staging -> main) are design references for it.
- **Fonts: keep Geist in the app;** port only colors and spacing as tokens. Why: simplest, fewest tokens.
- **Ordered plan recorded in docs/NEXT.md;** viable-product definition is its step 7.
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
