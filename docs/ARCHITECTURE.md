# Architecture in two minutes

**Goal:** an easy, interactive tool to screen NYC/US properties and value them; a backend that keeps
researching, proposes new criteria that refine the valuation, and those changes reach the UI.

## Data flow
```
research agents -> research/criteria.yaml (ledger) -> user approves -> valuation factor
   -> backend engine (backend/app/valuation/) -> API (backend/app/api/) -> UI
```
The **backend is the only place math lives.** The UI displays results; it never recomputes them
(the artifact's in-page `model()` is a prototype and must be checked against the backend by a parity test).

## UI stages
| Stage | What | Where | Changed by |
|---|---|---|---|
| Staging artifact | design lab | `docs/artifact/staging.html` | any feature work |
| Main artifact | signed-off design spec | `docs/artifact/real-estate-tool.html` | promotion, with the user's explicit approval |
| The app | the product (local, Next.js) | `frontend/` | porting one approved section at a time |

## Memory map (what to read, in order)
`CLAUDE.md` (rules) -> `docs/NEXT.md` (goal, ordered plan) -> `docs/DECISIONS.md` (why) ->
`app.cli status` (what is actually built) -> `research/criteria.yaml` (research decisions).
