# UI guide: Real Estate Tool artifact

The one place that says how the artifact UI is built and what was added when. Read it before any UI
change; update it in the same commit as the change. Rules about main vs staging live in `CLAUDE.md`.
Backend and agent changes are recorded elsewhere (see "Where each kind of change is recorded").

## Files
- `docs/artifact/staging.html`: all new UI work (URL in `.claude/artifacts.json`).
- `docs/artifact/real-estate-tool.html`: approved main copy. Locked; never edit or publish without approval.

## Structure of staging.html (single file: CSS, HTML, JS)
- **Design tokens**: CSS variables at the top (`--s1..s7` spacing, `--t-*` type, `--r1..r3` radius,
  warm neutrals plus one accent, `--up/--risk/--warn` semantics). Light, plus dark via
  `prefers-color-scheme` and `[data-theme]`. Use tokens only; no new raw colours or font sizes.
- **Tabs**: `ov` Overview, `cf` Cash flow, `st` Stress test, `as` Assumptions. Panels are
  `#p-ov #p-cf #p-st #p-as`; tab clicks set `TAB` and call `bar()`.
- **State**: `S` (live inputs), `D` (defaults), `AMD` (amended keys), `B` (base model result),
  `NSEL/DIAL/EVS` (selected scenario, condition dials, events), `CY` (cash-flow year), `SCS` (all 18
  scenario results), `TOR` (per-input IRR sensitivity), `UNB` (share of IRR spread from unbacked inputs).
- **Render flow**: `go()` recomputes everything after any input change; smaller handlers
  (`resolved()`, `bridge()`, `goal()`, tab click) call `bar()` so the bar never goes stale.
- **Engine**: `model(o)` is the in-page prototype calculation. The backend is the real engine (see
  `docs/DECISIONS.md`); do not add new finance logic here without a parity plan.

## Components
| Component | Where | Notes |
|---|---|---|
| Result bar `#rbar` / `bar()` | sticky under the tabs, all tabs | One element, content chosen by `TAB`. Add a tab or a cell by editing the matching branch in `bar()`. |
| Read this first `#tk` / `takeaways()` | Overview, top | 3 plain-language cards (return source, stress result, what to firm up), tone g/w/r. |
| Cash flow insight `#cfi` | Cash flow, under chart | Tightest DSCR year, principal/interest crossover, cash-only payback. |
| Scenario summary `#wsum` / `wsummary()` | Stress test, top | Counts scenarios below the 1.25x floor and below target. |
| Reset to base `#wreset` | Stress test header | Visible only when not on Base case. |
| Scenario card DSCR line `.dq` | each of the 18 cards | Red below 1.25x. |
| Tornado `#tor` / `tornado()` | Stress test | Top 8 inputs, low/high IRR vs base, "unbacked" chips. |

Bar contents per tab: Overview = IRR, equity multiple, min DSCR, break-even occupancy, verdict chip.
Cash flow = selected year NOI, cash flow, DSCR, cumulative cash as % of equity. Stress = scenario name,
IRR, equity multiple, min DSCR, each vs base. Assumptions = IRR vs original inputs, target gap,
unbacked share of uncertainty.

## Locked (never change without the user's approval)
Four tabs and their order; the 18 scenarios; Conditions, Events, resolved assumptions, IRR range and
diff table on Stress test. Additions only.

## How to add a UI feature (checklist)
1. Build it in staging only, additively. Reuse tokens and existing classes.
2. Make it update from the data (`go()` or the relevant handler), not hard-coded.
3. Test in the preview: every tab, one scenario click, 400px width, no console errors.
4. Republish staging (read the live copy first if the publish is refused).
5. Same commit: add a row to Components above and a line to the Changelog, and a dated entry in
   `docs/DECISIONS.md` if it changes a rule. Do not edit `NEXT.md` except its open-work list.

## Where each kind of change is recorded
| Change | Recorded in |
|---|---|
| UI (components, layout, tokens) | this file (`docs/UI.md`) |
| Rules and decisions of any kind | `docs/DECISIONS.md` (dated), `CLAUDE.md` for standing rules |
| Current goal and open work | `docs/NEXT.md` |
| What is built | `app.cli status` via `docs/phases.yaml` |
| Backend and data sources | code, `docs/ARCHITECTURE.md`, `docs/phases.yaml` |
| Agents | `.claude/agents/README.md`, `.claude/agent-boundaries.json` |
| Valuation criteria | `research/criteria.yaml` |
| Personal preferences | auto-memory (`~/.claude/projects/.../memory/`) |

## Changelog
- 2026-09-18: sticky result bar (Stress test), then extended to all four tabs; Read this first,
  cash flow insight line, scenario summary, reset to base, per-card DSCR, tornado chart.
  Proposed, not built: grouped scenarios, risk colours on dials, URL-shareable scenario, Excel export hook.
