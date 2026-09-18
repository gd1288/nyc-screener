# Plan: Efficient Claude workflow + Workbench + US-ready neighborhoods + valuation scenarios + agents

## Context
The NYC condo screener works: 13 sources, neighborhood growth scores, 246 live listings, investment model, web UI, 23 tests. You want a professional valuation and research product that keeps improving, built with Claude at maximum quality per token. That means:

1. A disciplined Claude workflow using the Claude features that pay for themselves.
2. A **Workbench** page in the app to plan, implement, test and debug new additions.
3. Neighborhood research that works for **any US neighborhood**, starting with NYC.
4. A **dynamic, easy Valuation Scenarios** interface for any property or land, with **Excel export**.
5. A research agent (cloud routine, or in-app on demand) that proposes new free data sources for your approval.
6. A debug agent.

## Efficiency decisions (after review)
- **Built-ins before add-ons.** Use `/code-review`, `/security-review`, `/verify`, `/doctor`, `/usage`, `/insights`, `/fewer-permission-prompts`, and the `skill-creator`, `dataviz` and `xlsx` skills already installed.
  - Install only 4 plugins: `pyright-lsp`, `typescript-lsp`, `context7`, `duckdb-skills`.
  - Plus `explanatory-output-style` while you learn.
- **Zero-token status instead of a session-start dump:**
  - A **status line** (local; uses no model tokens) and the Workbench header show health.
  - The SessionStart hook is **silent when healthy**, printing at most one line only when something is broken.
- **Scheduled checks cost nothing unless something fails:**
  - The daily data-health check and weekly source-uptime check are **scripts** (the app's scheduler, and GitHub Actions cron).
  - Claude is called only on failure: a budget-capped headless `/debug` run, or `@claude` on the auto-opened issue.
  - A routine or scheduled Claude task would spend tokens every run even when nothing is wrong.
- **One headless runner** (`claude -p` with JSON output, allowed tools, budget cap, optional worktree and `/goal`) powers plan drafting, unattended implementation, research and debugging. Its costs are logged per run.
- **Workbench replaces** separate Research, Debug and decision-doc pages.
- **Order avoids rework:** geography generalizes before valuation. Valuation backend and Workbench then build **in parallel worktrees**.
- **Deferred:** paid-API runner, Claude PR-review app, browser error capture, national crime and sales comps.

---

## Part A — Feature setup and how you'll use each

| Feature | Setup (who) | How you use it |
|---|---|---|
| Plan mode + `opusplan` | `/model opusplan` (you, once) | Shift+Tab before multi-file work; Ctrl+G edits the plan |
| `/goal` quality gates | Nothing to set up; templates are in each phase below and in Workbench | `/goal <checks>` so Claude keeps working until tests and evals pass; auto mode for unattended runs |
| Hooks + status line | Claude writes `.claude/settings.json` and `.claude/hooks/*` | Automatic: format on edit, safety guards, test gate at stop; status line shows context %, cost and health |
| Subagents | Claude writes `.claude/agents/{debugger,valuation-reviewer}.md` | `/debug <symptom>`; "use valuation-reviewer on this diff" |
| Skills | Claude builds and **evals** them with `skill-creator` | `/add-data-source`, `/research-sources`, `/debug`, `/ship` |
| LSP, context7, duckdb plugins | `/plugin install …@claude-plugins-official` (you approve) | Automatic: precise code navigation, current library docs, SQL on big CSVs |
| Parallel worktrees | `.worktreeinclude` (copies `.env`) and per-worktree ports (Claude) | Desktop: new session → worktree option; or `claude -w <name>`; Workbench "Run unattended" uses one per issue |
| Remote Control + push | Desktop **Settings → Claude Code → Enable remote control by default**; install the Claude mobile app; `/config` → Push when actions required + Push when Claude decides (you) | Watch and steer long sessions from your phone; answer permission prompts remotely |
| Deep links | Nothing to set up (the handler registers after your first CLI prompt) | Workbench "Open in Claude Code" opens a terminal session in the repo with the prompt pre-filled; you press Enter |
| Claude memory | Claude saves standing decisions: free data only, RentCast cap 31/month, US-wide goal, approve-first research, token-efficiency priority | Future sessions don't re-ask |
| Playwright in CI | Claude adds `@playwright/test` specs and a seeded test DB | Runs on every PR at no Claude cost; failures show in Workbench → Test |
| Explanatory output style | `/plugin install explanatory-output-style@claude-plugins-official` | Claude explains its choices while you learn; uninstall later to save tokens |

**Daily habits:**
- One issue per session; `/clear` between issues.
- Esc stops Claude; Esc Esc rewinds.
- `/btw` for side questions.
- `/usage` weekly.
- After Phase 0, run `/fewer-permission-prompts` once.

---

## Phase 0 — Foundation (shipped as the first PR through the process)
**GitHub and CI**
- Commit pending work.
- `gh` to `~/.local/bin`; **you** run `gh auth login`.
- Private repo.
- `.github/workflows/ci.yml`:
  - ruff + pytest
  - `npm ci`, tsc, lint, build
  - Playwright smoke test against a seeded test DB (`backend/tests/fixtures/seed.py`)
- Branch protection.
- `.github/workflows/source-uptime.yml` (weekly cron): `uv run python -m app.cli probe-sources`. It pings every configured endpoint/dataset ID and opens or updates a `data-source-broken` issue via `gh` only on failure.
- Issue templates: `feature`, `bug`, `data-source`. Each has acceptance criteria, a "verify by" section and a `/goal` line.
- `.gitignore` gains `.claude/worktrees/`, `.claude/state/`.

**Migrations:** Alembic baseline (already a dependency); every later schema change is an autogenerated revision.

**Memory and instructions**
- Root `CLAUDE.md` (≤100 lines): commands, map, hard rules (RentCast via adapter only; no scraping; never read `.env`; `sqlite3` with `LIMIT`; Alembic), definition of done, compaction note.
- `backend/CLAUDE.md`: adapter contract, area/scoring and valuation invariants, tests.
- `frontend/CLAUDE.md`: keep `@AGENTS.md`; UI conventions; charts follow the `dataviz` skill; verify at 1280px and 400px.
- **Claude memory:** the standing decisions listed in Part A.

**`.claude/settings.json`**
- Permissions:
  - Allow: `uv run pytest|ruff|alembic|python -m app.cli*`, `npx tsc --noEmit`, `npm run lint|build|test:e2e`, `git status|diff|log|worktree*`, `gh pr|issue*`.
  - Deny: `Read(.env)`, `Read(backend/data/**)`, `Read(frontend/node_modules/**)`.
- `advisorModel: opus`.
- `statusLine` → `.claude/hooks/statusline.sh`: model · context % · session cost · health badge read from the cached `.claude/state/health.json`. **No model tokens.**
- Hooks (trimmed to failures only):
  - `guard.sh` (PreToolUse `Edit|Write|Bash`): block `.env`, lock files, `backend/data/`, `api.rentcast.io`, `rm` on data.
  - `format.sh` (PostToolUse `Edit|Write`): silent `ruff format` + `ruff check --fix`.
  - `stop-gate.sh` (Stop): pytest if `backend/` changed, tsc if `frontend/` changed. Writes a test status into `health.json`; blocks while failing.
  - `session-health.sh` (SessionStart): reads `health.json` only (no checks run). **Prints nothing when healthy**; otherwise one line, e.g. `Health: 2 sources failing since 09-16 — /debug`.

**Subagents**
- `debugger`: sonnet/high; Read/Grep/Glob/Bash/Edit; `memory: project`.
- `valuation-reviewer`: opus; read-only + pytest; reports correctness gaps only.

**Skills** (created and evaluated with `skill-creator`: trigger tests + output checks)
- `add-data-source`: coverage/granularity tags, rollup, `sources.yaml`, fixture test, license checklist, quota guard, `probe-sources` entry.
- `research-sources` (`context: fork`): procedure + `schema.json`.
- `debug` (`context: fork`, `agent: debugger`): uses the compact `app.cli diagnose` report.
- `ship` (`disable-model-invocation: true`): checks → `/code-review` → valuation eval if touched → commit/push → `gh pr create`.

**CLI commands**
- `app.cli diagnose [--json]`: health, last run and error per source, grouped log errors, test/tsc status; writes `health.json`.
- `app.cli probe-sources`
- The app scheduler runs `diagnose` daily at 7:00. **On failure only:** macOS notification + budget-capped headless `/debug` through the runner, which proposes a fix on a branch and never merges.

**Plugins:** `pyright-lsp`, `typescript-lsp`, `context7`, `duckdb-skills` (+ `explanatory-output-style`).

**`/goal` for Phase 0:** `uv run pytest exits 0, uv run ruff check is clean, npm run build and npm run test:e2e exit 0, CI workflow file validates, and git status shows only planned files — or stop after 30 turns`.

---

## Phase 1 — Neighborhood research, US-ready
**Area model** (Alembic + backfill)
- `areas`: kind `tract|zcta|nta|custom`, code, name, state, county FIPS, CBSA, geometry.
- `area_metrics`, `area_scores` (comparison set, pillars, coverage), `regions` (CBSA or counties; `watched` flag).
- Tracts are the universal unit. NYC NTAs are an overlay built from tracts (equivalency already used in `sources/census_acs.py`), so existing NYC pages keep working.

**Adapter contract** (`app/sources/base.py`)
- `coverage` (`national|state:NY|city:NYC`) + `granularity` + `fetch(region)`.
- Generic rollups: block group/ZCTA/point → tract → overlay. Point rollup reuses a generalized `geo.NeighborhoodIndex`.
- **On demand:** `POST /api/regions` loads a region; only watched regions refresh on schedule.

**National sources (verified free):**
- TIGERweb tracts
- Census Geocoder (address → tract)
- ACS 5-yr (generalize the existing adapter; add median gross rent + B25034 year built)
- **FHFA tract HPI** (CSV, ~90MB)
- Zillow ZHVI/ZORI by ZIP (generalize the county filter; ZCTA → tract weights)
- EPA National Walkability Index (block group)
- LODES WAC jobs (block)
- ZIP Business Patterns (Census API key)
- FEMA National Risk Index (tract)

Big files are queried with **DuckDB** (new `duckdb` dependency: `read_csv_auto` filtered by state/county SQL), never loaded whole. NYC overlays stay as they are.

**Scoring** reuses `app/scoring/neighborhood.py` keyed by area: percentiles within the comparison set (default CBSA); missing data neutral plus coverage. **Backtest generalized to FHFA tract HPI**, so every metro gets predictive evidence.

**UI**
- Region selector plus **Research a neighborhood** (any US address → tract; study area tract/radius/overlay).
- `neighborhoods/[code]` → `areas/[id]`.
- Compare any two areas.
- Map reuses `components/NeighborhoodMap.tsx`.

**`/goal`:** `pytest passes; alembic upgrade head works on a DB copy; the NYC FiDi-vs-Chelsea compare returns the same scores as before ±0.5; adding the Austin CBSA loads tracts and prints backtest correlations; no RentCast calls — or stop after 40 turns`.

---

## Phase 2a (worktree `valuation`) — Valuation engine + Excel export
New `backend/app/valuation/` package:
- **`property.py`:** `PropertyProfile` (condo / co-op / 1–4 family / multifamily / mixed-use / commercial / land). `lookup(address)`: Census Geocoder everywhere; in NYC also GeoSearch → PLUTO `64uk-42ks` (fields verified). Manual facts elsewhere.
- **`factors.py`:** `FactorDef` with bounds, distribution, whether it varies by year, and `market_estimate(area, profile)` returning value, P10/P90, source and as-of.
  - Factors: FRED `MORTGAGE30US` (keyless), rent growth, vacancy, expense/tax/insurance growth, abatement expiry, appreciation (reuses `investment.base_appreciation`), exit cap, NYC rent-stabilized increases, hold period, leverage, closing costs (`purchase_costs`), land development inputs.
- **`engine.py`:** one vectorized (NumPy) annual cash-flow core.
  - Reuses `monthly_payment`, `loan_balance`, `irr`, `mansion_tax_rate`, `purchase_costs` from `scoring/investment.py`.
  - Method configurations: rental DCF, owner-occupied, co-op, land residual.
  - Sales comparison: DOF comps with categories extended to 1–4 family, rentals, mixed-use, vacant land `05`/`31`; elsewhere user comps + FHFA/ZHVI index.
  - Reconciled range, NPV, IRR at 10 and 20 years, equity multiple, minimum DSCR, cash-on-cash.
- **`scenarios.py`:** scenarios/presets (bear, base, bull, "rates +1pt", "recession", "abatement ends", "rezoning upside"); `sensitivity()` (tornado); **two-factor data table** (e.g., exit cap × rent growth → IRR grid); `monte_carlo(n≤20k, seed)` with correlations.
- **`export_xlsx.py`** (openpyxl; follows the `xlsx` skill's conventions):
  - `Assumptions` sheet with named cells.
  - `Cash Flows` sheet with **live formulas** referencing assumptions, so the workbook recalculates in Excel.
  - `Scenarios`, `Sensitivity`, and `Monte Carlo` (percentiles + histogram data) sheets.
  - Formatted and freeze-paned.
- **API:** `GET /api/factors`, `POST /api/valuation/lookup`, CRUD `/api/valuation/properties`, `POST …/{id}/run`, `…/{id}/monte-carlo`, `…/{id}/data-table`, `GET …/{id}/export.xlsx`.
- **Tests:**
  - engine fixtures, co-op, land, Monte Carlo seed, tornado, data table
  - xlsx: formulas present, and base-scenario values evaluated with the `formulas` package match the engine within $1
- **Eval gate:** `app/valuation/eval.py` — median absolute % error on the last 24 months of NYC DOF sales, using data from before each sale; baseline stored; must not regress.
- **`/goal`:** `uv run pytest exits 0; app.valuation.eval median error ≤ research/evals/baseline.json; export.xlsx base-case values match engine; only valuation/, tests/, alembic/versions and routes changed — or stop after 50 turns`.

## Phase 2b (worktree `workbench`, in parallel) — Workbench: plan, implement, test, debug
- **Backend `app/dev/`** (enabled only with `DEV_TOOLS=1`; bound to 127.0.0.1 with a localhost Origin check; **allowlisted commands only**, no arbitrary shell):
  - **`runner.py`:** `claude -p` wrapper with `--output-format stream-json|json`, `--allowedTools`, `--permission-mode` (plan/auto), `--max-budget-usd`, optional `--worktree`, and optional `/goal`. Streams logs to the page; records `agent_runs` (kind, issue, cost, turns, duration, result).
  - **`github.py`:** `gh issue list/create/comment`, `gh pr list/checks` as JSON, cached 60s.
  - **`checks.py`:** runs ruff/pytest/tsc/lint/e2e/eval/backtest with trimmed output.
- **Frontend `src/app/workbench/`** (tabs):
  1. **Roadmap:** issue board (Backlog → Planned → In progress → In review → Done, from labels and PR state); **New addition** form creates an issue from a template.
  2. **Plan:** "Draft plan" runs the runner in plan mode with `--json-schema plan.schema.json` (files, steps, tests, risks, `/goal` condition) and a small budget. Saves `plans/issue-N.md` and comments on the issue. You edit in the page, then **Approve** (label `planned`).
  3. **Implement:**
     - **Open in Claude Code** (deep link `claude-cli://open?cwd=<repo>&q=<implement issue N per plans/issue-N.md in a worktree; /goal …>`), or
     - **Run unattended** (runner: worktree `issue-N`, auto mode, the plan's `/goal`, budget cap). Shows a live log, the worktree and branch, and cost.
  4. **Test:** per branch/PR, local check buttons, CI status (`gh pr checks`), Playwright report link, and eval/backtest trend charts (from `research/evals/*.json`, using `dataviz` standards).
  5. **Debug:** `diagnose` view (health, grouped errors, failing sources), **Copy debug report**, **Open /debug in Claude Code** (deep link with the symptom pre-filled), **Run debugger unattended** (budget-capped; proposes on a branch).
  6. **Agents & data:** research candidate queue (Approve/Reject → registry; Approve opens an "Implement source" issue), research PRs, data-health history, uptime issues, and the **usage table** (cost per run and kind, to keep efficiency visible).
- **`/goal`:** `pytest and e2e pass; Workbench tabs render with the seeded DB; runner dry-run (--max-budget-usd 0.05, a trivial prompt) records an agent_runs row; dev routes refuse non-localhost origins and non-allowlisted commands — or stop after 50 turns`.

## Phase 3 — Dynamic Valuation UI (after 2a merges)
- `src/app/valuation/page.tsx` (saved properties + new) and `valuation/[id]/page.tsx`.
- **Easy by default:**
  - **Quick mode** with 5 key sliders (price, rent, rate, appreciation, hold).
  - **Advanced mode** with all factors grouped (Financing / Income / Expenses / Market / Exit / Development).
  - Each slider is bounded by the historical range, with a "market" badge (source/as-of), reset and lock.
- **Dynamic:**
  - Results update ~150ms after each change.
  - **Scenario columns side by side** (clone, rename, differences highlighted against Base).
  - Preset chips.
  - Year-by-year path editor (small per-year table).
  - **Click a tornado bar to jump to that factor.**
  - Two-factor heatmap (data table).
  - Monte Carlo histogram (P10/P50/P90, probability of loss).
  - Cash flow by year.
  - Scenario state in the URL, so a link restores it.
- **Download Excel** button (`export.xlsx`).
- Entry points: Nav link, "Open in Valuation" on `listing/[id]` and area profiles.
- Charts follow the `dataviz` skill.
- Playwright specs: slider change updates the IRR, a scenario clone differs, the export downloads.
- **`/goal`:** `npm run build, lint and test:e2e pass; /verify at 1280px and 400px shows no console errors for a NYC condo, a NYC vacant lot and a manual non-NYC house; the xlsx opens with formulas — or stop after 40 turns`.

## Phase 4 — Research agent
- **Repo:** `research/registry.json` (dedupe memory; rejected sources skipped for 90 days), `research/gaps.json` (from `app.cli research-gaps`, including national gaps), `research/candidates/*.json` (schema), `research/memos/`.
- **Procedure** (the skill; hard caps):
  1. Registry + gaps.
  2. ≤8 searches.
  3. ≤5 candidates checked for cost, license, format, coverage, history.
  4. Deterministic `app/research/evaluate_series.py` (DuckDB; correlation and lead/lag against FHFA HPI growth and ZORI across regions).
  5. Candidate JSON + one-page memo.
- **Runners:**
  - **Cloud routine** (`/schedule` weekly; custom network allowlist; opens a `claude/research-<date>` PR).
  - **Workbench "Run research now"** (the runner; budget cap).
- Approvals in Workbench → Agents & data. Precision metric = approved ÷ proposed.
- **`/goal`:** `research-sources run with --max-budget-usd 1 writes schema-valid candidates; a second run skips registry entries; evaluate_series tests pass — or stop after 30 turns`.

## Deferred
- Paid-API runner and in-app chat (verified pricing: Sonnet 5 $2/$10 per million tokens; web search $10 per 1,000; fetch free; cache reads 0.1×; Batch 50% off).
- Claude PR-review app.
- Browser error capture.
- National crime and sales comps (research-agent targets).

## Token efficiency × quality rules
1. **Code before model:** checks, probes, health, statistics, schemas, budgets.
2. **Small context:** short CLAUDE.md files; skills on demand; 4 plugins; deny rules; LSP; forked skills and subagents for verbose work; one issue per session.
3. **Zero-token visibility:** status line, Workbench, silent-when-healthy SessionStart hook.
4. **Model routing:** `opusplan` for features; Sonnet for debug and research; Opus advisor only for long sessions; Opus reviewer only for valuation math. Change a route only if its eval holds.
5. **Bounded autonomy:** every headless run has `--max-budget-usd`, a turn clause in `/goal`, allowlisted tools, and a worktree.
6. **Memory prevents rework:** research registry, debugger memory, Claude memory, `/doctor` pruning.
7. **Quality gates:** hooks, CI (unit + Playwright), valuation eval, per-metro backtest, skill evals, adversarial review.

## Phases and your part
| Phase | Deliverable | You |
|---|---|---|
| 0 | Foundation + first PR | `gh auth login`; approve plugins; turn on Remote Control, mobile app, push |
| 1 | US-ready areas, 9 national sources, DuckDB, generalized scoring/backtest/UI | Pick a second test metro |
| 2a + 2b (parallel) | Valuation engine + Excel export · Workbench | Try Workbench on a small issue |
| 3 | Dynamic valuation UI | Value 2–3 real properties; download Excel |
| 4 | Research agent + routine | Confirm the routine allowlist |

## Verification
- **Phase 0:**
  - Stop gate blocks a failing edit.
  - `.env` edit and RentCast curl are blocked.
  - SessionStart prints nothing when `health.json` is healthy, and one line after a simulated failure.
  - Status line renders.
  - CI green, including the Playwright smoke test.
  - `probe-sources` against a fake broken ID opens an issue (in a test repo run).
  - Skill evals pass.
- **Phase 1:** NYC compare unchanged; Austin loads and scores; a non-NYC address resolves; backtest prints both metros; DuckDB-filtered FHFA load stays under 500MB RAM.
- **Phase 2a:** pytest (engine, data table, xlsx formula evaluation); eval ≤ baseline.
- **Phase 2b:**
  - A board built from real issues.
  - Draft plan produces `plans/issue-N.md` within budget.
  - "Run unattended" on a trivial issue creates a worktree, branch and PR with the cost logged.
  - Deep link opens a terminal with the prompt pre-filled.
  - Debug tab shows an injected failure.
- **Phase 3:** `/verify` at both widths; Playwright slider/scenario/export specs; the xlsx recalculates in Excel.
- **Phase 4:** schema-valid candidates; dedupe on rerun; the routine's "Run now" opens a PR; Approve creates an issue.
