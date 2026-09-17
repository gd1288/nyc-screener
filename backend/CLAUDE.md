# Backend conventions

## Adding a data source
Subclass `Source` in `app/sources/base.py`, implement `run(ctx)`, register it in `sources.yaml`
with a cron `schedule`. `kind` is one of `boundaries`, `neighborhood` (writes `NeighborhoodMetric`
rows via `self.write_metrics`), `sales`, `listings`, or `sold_check`. Set `requires` to the
settings keys it needs (e.g. `["rentcast_api_key"]`) so it's skipped, not errored, when absent.
Prefer the `add-data-source` skill for the full checklist (coverage tags, fixture tests, ToS check).

## Scoring invariants (`app/scoring/neighborhood.py`)
- Every metric becomes a **percentile within its comparison set** (today: all NYC neighborhoods;
  after the area-model migration: the area's CBSA) — never a raw value or a citywide/national
  percentile mixed across incomparable markets.
- A pillar with no data scores **neutral (50)**, and lowers `coverage` — never null-propagates to
  drop the whole score.
- Direction matters: set `higher_is_better=False` on a `MetricDef` for things like crime or distance
  to transit, or the percentile inverts silently.

## Valuation invariants (once `app/valuation/` exists)
- Reuse `scoring/investment.py`'s `monthly_payment`, `loan_balance`, `irr`, `mansion_tax_rate`,
  `purchase_costs` — don't reimplement amortization or NYC transfer-tax math.
- Every `FactorDef.market_estimate()` must return its P10/P90 range, source, and as-of date — the UI
  shows these, and Monte Carlo sampling needs the range.
- Any change to `app/valuation/engine.py` must not regress `app/valuation/eval.py`'s median error
  (see `research/evals/baseline.json`) — run it, don't just eyeball the numbers.

## Tests
Follow `tests/test_core.py`'s style: an in-memory SQLite session fixture, hand-worked numeric
fixtures for financial math (state the source of the expected number in a comment, e.g. "standard
amortization table"), and adapters tested against recorded fixtures, not live HTTP.
