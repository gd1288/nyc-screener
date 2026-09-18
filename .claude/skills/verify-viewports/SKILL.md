---
name: verify-viewports
description: Verify a nyc-screener frontend page at desktop (1280px) and mobile (400px) with no console errors, per frontend/CLAUDE.md's UI convention. Use for "/verify", "check this page at both widths", "does the UI look right", or after any frontend change to listing/neighborhood/valuation pages — before calling a UI change done.
---

# verify-viewports — dual-width UI check

## 1. Name
`verify-viewports`.

## 2. Description
Fires on `/verify`, "check this page at both widths", "does the UI look right", or as the last
step of any frontend change — this project's own conventions (`frontend/CLAUDE.md`) and several
`/goal` clauses in the approved workflow plan require verification at 1280px and 400px with no
console errors before a UI change counts as done.

## 3. Body / instructions
1. **Get the dev server running**: use the `run` skill if the servers aren't already up (it knows
   how to launch this project specifically), or `preview_start {name: "..."}` directly against
   `.claude/launch.json` if they are.
2. **Pick the route(s) and scenario** to check. If the user names a page, use it; otherwise infer
   the smallest set of routes touched by the current diff (`git status`/`git diff --stat`). See
   [reference/routes.md](reference/routes.md) for the current route list and what data each one
   needs to render meaningfully (e.g. a real listing ID, not a 404).
3. **Desktop pass**: `resize_window {preset: "desktop"}`, navigate to the route, `read_page` (or
   `get_page_text` for content-only checks), `read_console_messages {onlyErrors: true}`.
4. **Mobile pass**: `resize_window {preset: "mobile"}`, reload, repeat the same checks. A layout
   that only breaks at 400px (overflow, unreadable text, a control off-screen) is the whole point
   of this second pass — don't skip it because desktop looked fine.
5. **Reset the viewport** to `desktop` when done, per the Browser pane's own convention, so it
   doesn't leak into unrelated later work in this session.
6. **Report per route**: pass/fail, any console errors verbatim, and a screenshot only when
   something looks wrong or the user asked to see it (don't screenshot-spam a clean pass).

Expected output: a short pass/fail report per route/width, with the actual console error text
when something fails — not a restated claim that "it works."

## 4. Gotchas
- **A route needing a real ID 404s silently-ish** (renders an empty/error state, not a crash) —
  check `get_page_text` actually shows content, not just that the page loaded without a console
  error. Grab a real listing/neighborhood ID from the dev DB rather than guessing one.
- **HMR can mask a real break.** If the dev server has been running a while, do one hard reload
  (`navigate` to the same URL again) before trusting a "no console errors" result — a stale bundle
  can hide an error that a fresh load would show.
- **Mobile preset also emulates touch + a mobile UA** — a click-based interaction test should still
  work the same, but don't be surprised by a mobile-only layout branch reacting to the UA.

## 5. Guardrails
- Read-only against the dev server — never edit source files from inside this skill; report what's
  broken and stop (or hand off to `/debug` if the user wants it fixed).
- Never point this at a non-localhost / production-looking URL without the user naming it
  explicitly — this skill's whole job is local dev verification.
- If no dev server can be started (port conflict, build error), report the actual error rather than
  guessing the page would have been fine.

## 6. Embedded skills and callouts
- **`run`** (installed skill) — used in step 1 to get the server up; this skill doesn't duplicate
  that logic, it just consumes the result.
- [reference/routes.md](reference/routes.md) — the current route list and what scenario data each
  needs. Update this file when a new top-level page ships (e.g. Phase 3's `valuation/[id]`) rather
  than hard-coding routes into this SKILL.md.
- **`dataviz`** (installed skill) — not invoked here, but if a chart looks wrong during a check,
  that's the skill to reach for on the fix, not this one.

## 7. Memory allocation
The route list is the only thing that needs to stay current, and it lives in
[reference/routes.md](reference/routes.md) specifically so updating it doesn't mean editing this
core method. Nothing from a run persists beyond the chat report — there's no separate state file.

## 8. Frontmatter controls
Only `name` and `description`. No `context: fork` — reporting back into the main conversation
immediately (so the user can ask for a fix right after) is the point. No `agent:` — this uses the
Browser pane tools directly, not a specialized subagent. Not `background:`.

## 9. Sub-files, scripts and evals
- **Structural check**: shared linter —
  `python3 .claude/skills/tony-stark/scripts/structural_check.py .claude/skills/verify-viewports/SKILL.md`.
- **Live run**: a real check against a real running page in this repo (see
  [CHANGELOG.md](CHANGELOG.md)) — actual console output and actual screenshot, not a fixture.

## 10. Versioning and iteration
Logged in [CHANGELOG.md](CHANGELOG.md). Previous versions recoverable from git history on this
file.
