---
name: debug
description: Investigate and fix a specific bug, test failure, broken data-source run, or unexpected app behavior. Use when the user runs /debug or describes a symptom ("why is X broken", "this test is failing", "the neighborhoods page looks wrong"). Delegates the investigation to the debugger subagent in a forked context so the main session's context isn't spent on debug-log noise.
context: fork
agent: debugger
background: false
---

# /debug

Hand the reported symptom to the `debugger` subagent exactly as given — don't pre-diagnose or
narrow it yourself first, since the subagent's whole job is that investigation and it has its own
procedure (see `.claude/agents/debugger.md`) starting from `uv run python -m app.cli diagnose`.

If the user gave no symptom (bare `/debug`), run `cd backend && uv run python -m app.cli diagnose`
yourself first (it's cheap — reads cached state, no checks run) to find one: a source with
`last_status: error`, or `tests_ok: false` from the last stop-gate check. Pass whichever concrete
symptom that surfaces to the subagent. If `diagnose` reports everything healthy and the user
didn't name a symptom, say so and ask what they're seeing instead of inventing a problem to
investigate.

Report back the subagent's findings (root cause, fix, checks re-run) — don't just relay "fixed",
relay what was actually broken and why, so the compacted context this skill exists to save doesn't
also erase the useful information.
