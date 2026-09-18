# ship changelog

## (undated, pre-tony-stark baseline)
Original version from Phase 0: a 6-step checklist (checks → review → valuation eval →
commit → push/PR → report). Predates the ten-part convention — kept as-is rather than
force-migrated (see 2026-09-17 note below).

## 2026-09-17 — improvement
Step 3 ("Valuation eval, if touched") previously inlined a direct call to
`uv run python -m app.valuation.eval` and only *suggested* considering `valuation-reviewer`.
Replaced that inline logic with a call to the new `valuation-eval-gate` skill, which owns the
eval-vs-baseline comparison, the generalized multi-region backtest check, the "is this a real
regression" judgment call, and the firm (not just suggested) hand-off to `valuation-reviewer` on a
real regression. Avoids two files independently guessing at `app.valuation.eval`'s interface once
Phase 2a lands. Also broadened the trigger from `backend/app/scoring/investment.py` specifically to
all of `backend/app/scoring/`, matching `valuation-eval-gate`'s own scope.

**Structural check note**: same as `add-data-source` — this file predates the ten-part structure
(a 6-step checklist, not the ten required sections). Not migrated here; flagged as a candidate
follow-up alongside `add-data-source`, `research-sources`, and `debug`.
