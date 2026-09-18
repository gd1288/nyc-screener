# NYC Condo Screener

Screener + investment/valuation analysis for NYC condos, generalizing to any US neighborhood and
property type. Backend: FastAPI + SQLAlchemy + SQLite (`backend/`). Frontend: Next.js + Tailwind +
MapLibre + Recharts (`frontend/`).

## Commands
```
cd backend && uv run pytest              # backend tests
cd backend && uv run ruff check .        # lint (must be clean before ship)
cd backend && uv run alembic revision --autogenerate -m "..."   # after any models.py change
cd backend && uv run alembic upgrade head
cd backend && uv run python -m app.cli refresh [source ...]     # run data sources
cd backend && uv run python -m app.cli diagnose                 # health report
cd backend && uv run python -m app.cli status                   # what each phase has actually shipped
cd frontend && npx tsc --noEmit && npm run lint && npm run build
./start.sh                               # run both servers in this terminal (see .claude/launch.json)
./scripts/dev-open.sh                    # start both in the background (if not already up) + open the browser
./scripts/dev-stop.sh                    # stop both
```
Easiest way to just look at the site: double-click **"Open NYC Screener"** on the Desktop (runs
`dev-open.sh` and opens http://localhost:3000; safe to double-click again, it reuses whatever's
already running). **"Stop NYC Screener"** on the Desktop shuts both servers down.

## Architecture
- `backend/app/sources/`: one plug-in per data source (`base.py` defines the contract), wired
  in `sources.yaml`. `registry.py` runs them and logs to `source_runs`.
- `backend/app/scoring/`: `neighborhood.py` (Growth Score), `investment.py` (per-property returns),
  `backtest.py` (does the score predict future appreciation).
- `backend/app/pipeline/`: `listings.py` (lifecycle: new → price change → off market → sold/withdrawn),
  `geocode.py` (address → coords/BBL via free NYC GeoSearch, no key).
- `backend/app/api/routes.py` + `app/services.py`: REST layer joining listings, neighborhoods, scoring.
- `frontend/src/lib/api.ts` (`useApi` hook), `lib/format.ts`, `components/ui.tsx`: reuse these,
  don't redefine formatting or fetch helpers per page.

## Hard rules
- **RentCast**: only through `app/sources/rentcast.py`'s adapter — it enforces the request budget
  (31/month cap, 24h cooldown). Never call `api.rentcast.io` directly from a script or shell command.
- **Never scrape StreetEasy, Zillow, or other listing sites.** Free public data and RentCast only.
- **Never read, print, or commit `.env`.** It holds live API keys.
- **`sqlite3` queries against `backend/data/screener.db` must have `LIMIT`** — it has 100k+ rows in
  `sales`/`neighborhood_metrics`.
- **Schema changes go through Alembic**, not just editing `models.py` — see Commands above.
  `init_db()`'s `create_all` is dev-bootstrap only; migrations are the source of truth.
- Condos on an ordinary tax lot are `likely_coop` (`ownership_type()` in `pipeline/listings.py`) and
  hidden from the screener by default — see the co-op-filtering discussion if touching listing display.

## Roadmap and phase status
`docs/PLAN.md` is the approved multi-phase plan (intent). `docs/phases.yaml` lists each phase's
deliverables, and `app.cli status` checks them against the filesystem.

**Never state what phase something is in, or call a phase done, from memory, a summary, or a commit
message — run `app.cli status`.** Those all record a claim made at one moment; only the command
reads current disk. (This rule exists because Phase 2a was twice described as complete while
`export_xlsx.py` and `eval.py` had never been written.) Adding a deliverable means adding its check
to `docs/phases.yaml` in the same commit.

## Definition of done
Tests pass (`pytest`), types check (`tsc --noEmit`), ruff is clean, and you've shown evidence (test
output, or a screenshot/`/verify` for UI changes) — not just a claim that it works.

## Compaction
When compacting, always keep: which files were modified, the test/lint commands and their last
results, and any `/goal` condition currently active.
