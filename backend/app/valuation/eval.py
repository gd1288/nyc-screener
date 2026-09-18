"""Does the comparable-sales value estimate actually predict what a property sells for?

Walk-forward backtest over closed DOF sales: for each sale in the evaluation window, estimate its
value using only sales that closed *strictly before* it, then score the error. The headline number
is the median absolute percentage error, and `research/evals/baseline.json` records it so a change
to `comps.py` or the data that feeds it has to beat what was already there.

The strict `<` is the whole validity of the number. A comp set that includes the target sale (or
anything after it) produces a flattering median that is indistinguishable from a correct one, which
is why `tests/test_valuation_eval.py::test_comp_set_never_includes_the_target_sale_or_later` asserts
it directly rather than trusting the query to stay right.

Only the building-median path is graded. `comps.from_neighborhood_ppsf` prices against what is being
*asked* today, so it cannot be replayed as of a 2024 sale date — including it would leak the present
into every historical prediction.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from statistics import median

from sqlalchemy.orm import Session

from app.models import Sale
from app.services import building_address_key
from app.valuation import comps

BASELINE_PATH = Path(__file__).resolve().parents[3] / "research" / "evals" / "baseline.json"
EVAL_MONTHS = 24
COMPS_YEARS = 3
DAYS_PER_MONTH = 30.44
# Rules that change the predictions must change this, so a baseline written under the old rules is
# visibly stale rather than silently compared against.
COMPS_RULES_VERSION = 1


@dataclass
class EvalResult:
    median_abs_pct_error: float | None
    n_scored: int
    n_candidates: int
    coverage: float
    config: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        return asdict(self)


def _comp_key(building_key: str, address: str) -> tuple[str, str]:
    """Same two-part building match the screener uses: tax block groups a condo's units, and the
    normalised street address separates two condos that share a block."""
    return building_key, building_address_key(address)


def run_eval(
    session: Session,
    as_of: date | None = None,
    months: int = EVAL_MONTHS,
    comps_years: int = COMPS_YEARS,
) -> EvalResult:
    as_of = as_of or date.today()
    window_start = as_of - timedelta(days=int(DAYS_PER_MONTH * months))
    pool_start = window_start - timedelta(days=365 * comps_years)

    rows = session.query(Sale.building_key, Sale.address, Sale.sale_date, Sale.price).filter(
        Sale.sale_date >= pool_start, Sale.sale_date < as_of, Sale.price > 0
    )
    by_building: dict[tuple[str, str], list[tuple[date, float]]] = {}
    targets: list[tuple[tuple[str, str], date, float]] = []
    for building_key, address, sale_date, price in rows:
        key = _comp_key(building_key, address)
        by_building.setdefault(key, []).append((sale_date, price))
        if sale_date >= window_start:
            targets.append((key, sale_date, price))

    errors = []
    for key, sale_date, price in targets:
        earliest = sale_date - timedelta(days=365 * comps_years)
        # Strict `<`: a same-day sale is not information you had when pricing this one, and it is
        # also what excludes the target's own row from its comp set.
        prices = [p for d, p in by_building[key] if earliest <= d < sale_date]
        estimate = comps.from_building_sales(prices)
        if estimate is not None:
            errors.append(abs(estimate.value - price) / price)

    return EvalResult(
        median_abs_pct_error=round(median(errors), 6) if errors else None,
        n_scored=len(errors),
        n_candidates=len(targets),
        coverage=round(len(errors) / len(targets), 4) if targets else 0.0,
        config={
            "as_of": as_of.isoformat(),
            "eval_months": months,
            "comps_years": comps_years,
            "min_building_comps": comps.MIN_BUILDING_COMPS,
            "comps_rules_version": COMPS_RULES_VERSION,
        },
    )


def load_baseline(path: Path = BASELINE_PATH) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def write_baseline(result: EvalResult, path: Path = BASELINE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_json(), indent=2) + "\n")


def check_against_baseline(result: EvalResult, baseline: dict | None, tolerance: float = 0.005) -> tuple[bool, str]:
    """Whether `result` is allowed to ship. Tolerance absorbs the drift from the sales table simply
    having moved on since the baseline was written — it is not a licence to degrade the model."""
    if baseline is None:
        return True, "No baseline yet — run with --write-baseline to record one."
    if result.median_abs_pct_error is None:
        return False, "Eval produced no scored sales; refusing to compare against the baseline."
    previous = baseline.get("median_abs_pct_error")
    if previous is None:
        return True, "Baseline has no recorded error; treating this run as the new reference."
    if baseline.get("config", {}).get("comps_rules_version") != COMPS_RULES_VERSION:
        return True, (
            f"Baseline was written under comps rules v{baseline.get('config', {}).get('comps_rules_version')}, "
            f"now v{COMPS_RULES_VERSION} — record a new baseline."
        )
    delta = result.median_abs_pct_error - previous
    if delta > tolerance:
        return False, f"Median error regressed: {previous:.4f} -> {result.median_abs_pct_error:.4f} (+{delta:.4f})"
    return True, f"Median error {result.median_abs_pct_error:.4f} vs baseline {previous:.4f} ({delta:+.4f})"
