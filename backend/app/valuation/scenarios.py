"""Scenario comparison, sensitivity ("tornado"), a two-factor data table, and Monte Carlo.

Every function here is a thin loop over `engine.run()` - none of them touch cash-flow math
directly. That's deliberate: a second numeric implementation here is exactly how this module could
quietly disagree with the Opportunity Score for the same property (see engine.py's own docstring).

Custom scenarios aren't persisted yet (same as Quick Mode's sliders) - see the module-level note in
frontend/src/app/valuation/page.tsx for why, and what persisting them would take.
"""

from dataclasses import dataclass

import numpy as np

from app.services import MarketContext
from app.valuation import engine
from app.valuation.factors import PropertyProfile, market_estimate

ASSUMPTION_FIELDS = engine.ASSUMPTION_FIELDS
MAX_MONTE_CARLO_RUNS = 2000

SENSITIVITY_SWINGS = {  # absolute +/- swing around the baseline, used only when the factor has no
    "interest_rate": 0.015,  # real P10/P90 range from market_estimate to swing within instead
    "rent_growth": 0.02,
    "appreciation_override": 0.02,
    "vacancy_pct": 0.05,
    "expense_growth": 0.02,
    "down_payment_pct": 0.10,
}
SENSITIVITY_LABELS = {
    "interest_rate": "Mortgage rate",
    "rent_growth": "Rent growth",
    "appreciation_override": "Appreciation",
    "vacancy_pct": "Vacancy rate",
    "expense_growth": "Expense growth",
    "down_payment_pct": "Down payment %",
}
# Hard domain limits for a swung/sampled factor. Without these, baseline +/- swing runs off the end
# of what the number can physically mean - a 5% down-payment baseline swings to -5% (a 105% LTV loan
# with negative cash invested, which then reports a *spectacular* IRR and tops the tornado), vacancy
# swings below zero (collecting more than 100% of gross rent), and rates go near-zero.
FACTOR_BOUNDS = {
    "interest_rate": (0.005, 0.25),
    "rent_growth": (-0.10, 0.20),
    "appreciation_override": (-0.20, 0.20),
    "vacancy_pct": (0.0, 0.60),
    "expense_growth": (-0.10, 0.20),
    "down_payment_pct": (0.01, 1.0),
    "exit_cost_pct": (0.0, 0.30),
    "management_pct": (0.0, 0.30),
}


def _clamp(factor: str, value: float) -> float:
    lo, hi = FACTOR_BOUNDS.get(factor, (float("-inf"), float("inf")))
    return min(max(value, lo), hi)


def _swing_range(
    factor: str, baseline: dict[str, float], estimates: dict, swing: float | None = None
) -> tuple[float, float]:
    """The low/high a factor is swung (or sampled) between.

    When a real source backs the factor, its P10/P90 gives the *width*, but the range is re-centred
    on the caller's baseline: the sliders are the scenario the user is actually looking at, and a
    range anchored to the raw market estimate would otherwise bracket a base case that isn't on
    screen (and, for Monte Carlo, silently ignore the slider entirely).
    """
    est = estimates.get(factor)
    base = baseline[factor]
    if est is not None:
        offset = base - est.value
        lo, hi = est.p10 + offset, est.p90 + offset
    else:
        width = swing if swing is not None else SENSITIVITY_SWINGS.get(factor, 0.02)
        lo, hi = base - width, base + width
    return _clamp(factor, lo), _clamp(factor, hi)


PRESETS: list[dict] = [
    {"name": "Bear", "deltas": {"appreciation_override": -0.02}},
    {"name": "Base", "deltas": {}},
    {"name": "Bull", "deltas": {"appreciation_override": 0.02}},
    {"name": "Higher rates", "deltas": {"interest_rate": 0.015}},
    {"name": "Recession", "deltas": {"rent_growth": -0.02, "vacancy_pct": 0.05, "appreciation_override": -0.02}},
]


def _resolve_baseline(profile: PropertyProfile, ctx: MarketContext, overrides: dict[str, float]) -> dict[str, float]:
    """A fully-numeric baseline for every Assumptions field - resolved via one real engine.run() so
    it reflects market data plus the caller's own overrides. Unlike the raw `assumptions` dict,
    `appreciation_override` here is never None (analyze() always resolves it to a concrete rate,
    via base_appreciation() when nothing overrides it - that resolved number, not the possibly-null
    field, is what "Bear"/"Bull" deltas should be relative to)."""
    base = engine.run(profile, ctx, overrides)
    resolved = dict(base["assumptions"])
    resolved["appreciation_override"] = base["appreciation"]["base"]
    return resolved


@dataclass
class ScenarioResult:
    name: str
    assumptions: dict[str, float]
    cap_rate: float | None
    cash_on_cash: float | None
    monthly_cash_flow: float
    irr_10: float | None
    irr_20: float | None
    equity_multiple_10: float | None
    equity_multiple_20: float | None
    payback_year_10: int | None
    estimated_factors: list[str]


def compare(
    profile: PropertyProfile, ctx: MarketContext, overrides: dict[str, float], scenarios: list[dict] | None = None
) -> list[ScenarioResult]:
    baseline = _resolve_baseline(profile, ctx, overrides)
    results = []
    for s in scenarios if scenarios is not None else PRESETS:
        if unknown := set(s.get("deltas", {})) - ASSUMPTION_FIELDS:
            raise engine.UnknownOverrideError(unknown)
        assumptions = {**baseline, **{k: baseline[k] + d for k, d in s.get("deltas", {}).items()}}
        run = engine.run(profile, ctx, assumptions)
        p10, p20 = run["projections"]["base"]["10"], run["projections"]["base"]["20"]
        results.append(
            ScenarioResult(
                name=s["name"],
                assumptions=assumptions,
                cap_rate=run["cap_rate"],
                cash_on_cash=run["cash_on_cash"],
                monthly_cash_flow=run["monthly"]["cash_flow"],
                irr_10=p10["irr"],
                irr_20=p20["irr"],
                equity_multiple_10=p10["equity_multiple"],
                equity_multiple_20=p20["equity_multiple"],
                payback_year_10=p10["payback_year"],
                estimated_factors=run["estimated_factors"],
            )
        )
    return results


def sensitivity(
    profile: PropertyProfile, ctx: MarketContext, overrides: dict[str, float], horizon: str = "10"
) -> list[dict]:
    baseline = _resolve_baseline(profile, ctx, overrides)
    estimates = market_estimate(ctx, profile)
    base_irr = engine.run(profile, ctx, baseline)["projections"]["base"][horizon]["irr"]
    rows = []
    for factor, swing in SENSITIVITY_SWINGS.items():
        est = estimates.get(factor)
        lo_val, hi_val = _swing_range(factor, baseline, estimates, swing)
        lo_irr = engine.run(profile, ctx, {**baseline, factor: lo_val})["projections"]["base"][horizon]["irr"]
        hi_irr = engine.run(profile, ctx, {**baseline, factor: hi_val})["projections"]["base"][horizon]["irr"]
        # A factor whose end of the range has no solvable IRR is still reported, with nulls, rather
        # than dropped - silently returning a one-bar tornado reads as "nothing else matters".
        undefined = lo_irr is None or hi_irr is None
        rows.append(
            {
                "factor": factor,
                "label": SENSITIVITY_LABELS.get(factor, factor),
                "low_value": round(lo_val, 4),
                "high_value": round(hi_val, 4),
                "low_irr": lo_irr,
                "high_irr": hi_irr,
                "base_irr": base_irr,
                "backed_by_source": est is not None,
                "undefined": undefined,
                "swing": None if undefined else round(abs(hi_irr - lo_irr), 4),
            }
        )
    rows.sort(key=lambda r: (r["swing"] is not None, r["swing"] or 0), reverse=True)
    return rows


def data_table(
    profile: PropertyProfile,
    ctx: MarketContext,
    overrides: dict[str, float],
    x_factor: str,
    y_factor: str,
    x_values: list[float],
    y_values: list[float],
    horizon: str = "10",
) -> dict:
    if x_factor not in ASSUMPTION_FIELDS or y_factor not in ASSUMPTION_FIELDS:
        raise engine.UnknownOverrideError({x_factor, y_factor} - ASSUMPTION_FIELDS)
    baseline = _resolve_baseline(profile, ctx, overrides)
    grid = [
        [
            engine.run(profile, ctx, {**baseline, x_factor: x, y_factor: y})["projections"]["base"][horizon]["irr"]
            for x in x_values
        ]
        for y in y_values
    ]
    return {"x_factor": x_factor, "y_factor": y_factor, "x_values": x_values, "y_values": y_values, "irr_grid": grid}


def default_data_table_axis(
    profile: PropertyProfile, ctx: MarketContext, overrides: dict[str, float], factor: str, steps: int = 5
) -> list[float]:
    """A sensible default range for a data-table axis - the same re-centred, domain-clamped range
    `sensitivity()` swings within, so the grid always brackets the base case on screen."""
    baseline = _resolve_baseline(profile, ctx, overrides)
    lo, hi = _swing_range(factor, baseline, market_estimate(ctx, profile))
    if hi <= lo:  # a zero-width range would make every column identical
        return [round(lo, 4)]
    return [round(lo + (hi - lo) * i / (steps - 1), 4) for i in range(steps)]


def monte_carlo(
    profile: PropertyProfile,
    ctx: MarketContext,
    overrides: dict[str, float],
    n: int = 1000,
    seed: int | None = None,
    horizon: str = "10",
) -> dict:
    n = min(max(n, 100), MAX_MONTE_CARLO_RUNS)
    baseline = _resolve_baseline(profile, ctx, overrides)
    estimates = market_estimate(ctx, profile)
    randomized_factors = sorted(k for k, est in estimates.items() if est is not None and k in ASSUMPTION_FIELDS)
    rng = np.random.default_rng(seed)
    irrs = np.full(n, np.nan)
    # Sample each backed factor across its P10/P90 width, re-centred on the caller's baseline (so
    # the sliders actually move the distribution) and clamped to the factor's real domain.
    sample_ranges = {f: _swing_range(f, baseline, estimates) for f in randomized_factors}
    for i in range(n):
        sample = dict(baseline)
        for factor in randomized_factors:
            lo, hi = sample_ranges[factor]
            mode = min(max(baseline[factor], lo), hi)
            sample[factor] = lo if hi <= lo else float(rng.triangular(lo, mode, hi))
        result_irr = engine.run(profile, ctx, sample)["projections"]["base"][horizon]["irr"]
        if result_irr is not None:
            irrs[i] = result_irr
    valid = irrs[~np.isnan(irrs)]
    if len(valid) == 0:
        return {
            "n": n,
            "valid_n": 0,
            "randomized_factors": randomized_factors,
            "held_at_default": sorted(ASSUMPTION_FIELDS - set(randomized_factors)),
            "p10": None,
            "p50": None,
            "p90": None,
            "prob_loss": None,
            "histogram": [],
        }
    p10, p50, p90 = (round(float(v), 4) for v in np.percentile(valid, [10, 50, 90]))
    counts, edges = np.histogram(valid, bins=20)
    histogram = [
        {"bin_start": round(float(edges[i]), 4), "bin_end": round(float(edges[i + 1]), 4), "count": int(counts[i])}
        for i in range(len(counts))
    ]
    return {
        "n": n,
        "valid_n": int(len(valid)),
        "randomized_factors": randomized_factors,
        "held_at_default": sorted(ASSUMPTION_FIELDS - set(randomized_factors)),
        "p10": p10,
        "p50": p50,
        "p90": p90,
        "prob_loss": round(float((valid < 0).mean()), 4),
        "histogram": histogram,
    }
