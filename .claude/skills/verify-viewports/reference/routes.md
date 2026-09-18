# Current routes to check

Keep this list current as pages ship or move — `verify-viewports` reads it, not the other way
around. Last confirmed against `frontend/src/app/` on 2026-09-17.

| Route | Needs | Notes |
|---|---|---|
| `/` | nothing | Home/screener list — check it renders listings, not an empty state, against the dev DB. |
| `/listing/[id]` | a real listing id from the dev DB | Pick any non-co-op id (`likely_coop` listings are hidden by default — see root `CLAUDE.md`). |
| `/neighborhoods` | nothing | Neighborhood index. |
| `/neighborhoods/[code]` | a real NTA code | Check the map (`NeighborhoodMap.tsx`) actually renders, not just the surrounding page. |
| `/compare` | two real neighborhood codes | The compare-any-two-areas flow. |
| `/sold` | nothing | Sold listings view. |
| `/sources` | nothing | Data source health/status page. |
| `/add` | nothing | Manual listing entry form — check the form renders; don't submit it as part of a routine check (that would write to the dev DB). |

## Not yet built (add rows here once they ship)
- `/neighborhoods/[code]` generalizing to `/areas/[id]` (Phase 1).
- `/valuation` and `/valuation/[id]` (Phase 3).
- `/workbench` and its tabs (Phase 2b).
