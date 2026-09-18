# verify-viewports changelog

## 2026-09-17 — v0.1.0 (created)
Initial version, built via `tony-stark` from a workflow-optimization suggestion. Overlap-checked
against the installed `run` skill (that skill launches the app generically; this one adds the
project-specific 1280px/400px-no-console-errors contract on top).

**Live run**: checked `/` against the already-running dev server at `localhost:3000` (the one
started via the desktop "Open NYC Screener" shortcut — reused it rather than starting a duplicate
on the occupied port).
- Desktop (1280px, default): page rendered real content (filter panel, "Loading listings…", map
  legend), zero console errors.
- Mobile (375x812): reloaded, same content, zero console errors.
- Viewport reset to desktop afterward per the skill's own guardrail.

Only `/` was exercised — the other routes in [reference/routes.md](reference/routes.md) haven't
been live-tested yet; do that the first time this skill is used against one of them and log
anything it catches as a gotcha.
