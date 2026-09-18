# Plan: Formulas (formula inspector + Formulas tab) for the staging artifact

Status: planned 2026-09-18, not started. Owner window: any new window; read "Paste this first" below.

## What the user asked for
A "Formulas" section in the staging UI. Hover any numeric value, press an info button, and see (1) the formula,
(2) how that calculation fits into the larger valuation equation. The user also asked for a better design if there
is one, to plan it together first.

## Paste this first (prompt for a new context window)
```
You are continuing the nyc-screener project (real estate valuation and screener). Nothing is remembered from other
windows except what is in the repo, so read these before doing anything, in this order:
1. CLAUDE.md (rules; main artifact is LOCKED, all UI work goes to STAGING only)
2. docs/NEXT.md (current goal, ordered plan, open work)
3. docs/UI.md, especially "Picking this up in a new window" (how to edit, test, publish staging)
4. docs/DECISIONS.md and docs/ARCHITECTURE.md (why things are the way they are: the backend is the ONLY calculation
   engine; the artifact's in-page model() is a prototype)
5. docs/plans/formulas-tab.md (this plan; follow its phases in order, ask the user at the decision points marked ASK)
6. docs/DATA_LICENSES.md only if you touch data sources.

Your task: build the Formulas feature on the staging artifact (docs/artifact/staging.html) per the plan. Rules:
additive changes only; never touch the main artifact (a hook will prompt you if you try); staging URL and file are in
.claude/artifacts.json; test with docs/artifact/checks/staging_sweep.js and a 400px-wide iframe; run pytest, ruff and
`uv run python -m app.cli status` from backend/ before committing; update docs/UI.md (Components + Changelog) and
docs/DECISIONS.md in the same commit; commit with the Co-Authored-By line; never edit inside the generated
LISTINGS/MARKET blocks by hand; never put keys in files or logs. Report what you verified, not just what you built.
Start with Phase 0 of the plan and stop at the first ASK for the user.
```
Recommended setup: Sonnet for the UI build; use the `valuation-reviewer` agent (Opus) to check every formula's math.
Only one window should edit `staging.html` at a time; if another window is active, use a worktree
(`git worktree add ../nyc-formulas -b feature/formulas`) and merge, and expect to resolve conflicts in that one file.

## Better design than "hover + info button" (recommended)
Hover alone fails on touch screens and keyboards, and a tooltip is too small for a formula plus how it connects.
So:
1. **One formula registry, authored once.** Each formula: `id`, name, the formula in words and symbols, its inputs
   (each an id of another formula or a raw assumption), what it feeds, a worked example that substitutes the live
   numbers, provenance (market-backed / derived / unbacked, reusing the existing chips), and a code reference
   (`backend/app/valuation/...` function). **Author it in the backend** (`app/valuation/formulas.py`) so the
   artifact and the future Next.js app share it, and embed it in the artifact through `scripts/embed_screener.py`
   (same pattern as the LISTINGS and MARKET blocks). A parity test keeps the registry's formulas equal to what the
   engine computes.
2. **An ⓘ marker on every number** (a small button after the value, keyboard-focusable). Hover shows the existing
   short tooltip; **press (click / Enter / tap) opens a Formula inspector side panel**, so it works everywhere.
3. **The inspector panel** shows: the formula; "with your numbers" (live substitution); a **valuation chain
   strip** (Rent > EGI > NOI > Cash flow > Exit value > IRR) with this step highlighted, so "how it fits the larger
   equation" is a picture, not a paragraph; "what moves it" (inputs, each clickable to jump to its own formula); the
   data provenance chip; and the code reference.
4. **A Formulas tab (fifth, at the end so the four locked tabs and their order are unchanged)** with: a searchable
   list grouped by stage (Acquisition, Income, Debt, Cash flow, Exit, Tax, Returns, Risk, Scenarios, Screener,
   Market), and the full **valuation map** (dependency diagram of the whole equation). Selecting a formula opens the
   same inspector.
5. **Coverage enforced by test.** Every visible numeric value carries `data-f="<formula id>"`; the sweep script
   fails if a number has no formula, or an id is missing from the registry, so the feature cannot silently rot as the
   UI changes.
6. **Only real formulas.** Where the artifact's prototype differs from the backend engine (for example flat sale-tax
   rates vs `taxes.py`), the inspector says so, with a "differs from backend" flag, instead of hiding it.

## Deep dive pages (added 2026-09-18 at the user's request)
The user wants to press the info marker for a quick answer, and also **click through to the Formulas tab for a deeper dive on
any value**. So the inspector panel gets an "Open deep dive" link, and the Formulas tab has one page per formula:
- **Formula and derivation:** the formula in words and symbols, and why it has that shape.
- **With your numbers:** live substitution, one step per line, using the property currently loaded.
- **Where it sits:** the valuation chain with this step highlighted, what feeds it (each input clickable) and what it feeds.
- **Sensitivity:** how far this value, and the return, move when each input changes by 10%: a small tornado for this formula.
- **Provenance and caveats:** market-backed / derived / unbacked chips, edge cases (for example a negative NOI, or an IRR that
  cannot be computed), and whether the artifact's prototype differs from the backend.
- **Code reference:** the backend function that owns it.
The list view stays searchable and grouped by stage; the deep dive is reached from a row, from the inspector, or from any
number's info marker. The Purchase page (`docs/plans/purchase-analysis.md`) reuses the same markers.

## Formula inventory (start here; verify each against `model()` in staging.html and the backend)
- Acquisition: price, transaction costs (txnPct x price), loan (price x (1 - down %)), equity invested (down
  payment + costs).
- Debt: monthly payment (amortization), annual debt service, loan balance after k months, interest and principal split.
- Income: potential gross rent with growth, vacancy allowance, other income, effective gross income (EGI), management
  fee, operating expenses with growth, property taxes with growth, net operating income (NOI).
- Cash flow: before-tax cash flow (NOI - debt service), DSCR, break-even occupancy, cash-on-cash, operating
  expense ratio.
- Exit: forward NOI, exit value (forward NOI / exit cap), selling costs, loan balance at exit, equity reversion.
- Tax: depreciation (27.5-year, land excluded), recapture, capital gains, after-sale tax (flag: simplified vs taxes.py).
- Returns: levered IRR, unlevered IRR, equity multiple, total profit and its four parts (operating cash flow,
  principal paydown, appreciation, transaction costs), NPV and payback (backend deal mode).
- Risk and scenarios: scenario adjustments (`sabs`), tornado span, unbacked share of uncertainty, goal-seek, reality
  check (exit-value cut vs New York's worst real price fall).
- Screener: gross yield, cap rate, cash-on-cash, growth score, opportunity score, price per sq ft, comps ratio.
- Market: mortgage rate, Treasury, spread, five-year range.

## Phases
0. **Read and inventory.** Read the files above. List every numeric element in staging.html (`grep` for the render
   functions: `hero`, `wf`, `gauges`, `flags`, `hold`, `lev`, `cf`, `bridge`, `pf`, `worlds`, `resolved`, `fac`, `tornado`,
   `takeaways`, `bar`, the terms strip, the screener table, the market strip). Count them.
   **ASK the user:** confirm the design above (inspector + fifth tab + backend-authored registry) or change it.
1. **Registry in the backend.** Add `backend/app/valuation/formulas.py` with the metadata and a test asserting each
   formula's worked example equals the engine's output on a fixed property. Have `embed_screener.py` embed it between
   `/*FORMULAS-START*/ ... /*FORMULAS-END*/` markers (add the markers to staging.html).
   **ASK the user:** which formulas matter most first (suggest Returns and Exit), and how much math notation they want.
2. **Inspector UI.** ⓘ marker, side panel, valuation-chain strip, provenance chips, jump links. Start with the hero,
   result bar and Overview, then extend. Tokens and existing classes only; dark mode; 400px; keyboard and Escape.
3. **Formulas tab and valuation map.** Search, grouping, dependency diagram. Add the tab last in order.
4. **Coverage test.** Extend `docs/artifact/checks/staging_sweep.js`: every numeric element has `data-f`, every id
   resolves, no orphan formulas.
5. **Publish to staging only,** update `docs/UI.md`, `docs/DECISIONS.md`, `docs/phases.yaml` checks, commit, tag
   (`staging-vN-YYYY-MM-DD`, never re-tag with `-f`).
6. **Later:** port the registry and inspector to the Next.js app; it should read the same backend metadata.

## Risks and guardrails
- Formula text that is wrong is worse than none: run every formula through the `valuation-reviewer` agent and the
  parity test before publishing.
- The locked layout: adding a fifth tab changes the tab strip; the plan keeps the first four in order and asks the
  user before adding it to main (promotion is separate and needs their explicit approval).
- Token cost: keep the registry compact (short strings, no duplicated prose); build in small steps, one stage of
  formulas at a time.
