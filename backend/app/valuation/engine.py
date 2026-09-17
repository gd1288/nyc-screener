"""Runs a property through the investment model, filling in market factors and reporting which
ones came from real data vs. an unbacked default.

Deliberately thin: all cash-flow math lives in `app.scoring.investment` (reused by the screener's
Opportunity Score too), so a valuation run and a listing's Opportunity Score can never disagree
about the same numbers — see `tests/test_valuation.py::test_engine_matches_investment_analyze`.
"""

from dataclasses import asdict, fields

from app.scoring import investment as inv
from app.services import MarketContext, property_inputs
from app.valuation.factors import FactorEstimate, PropertyProfile, market_estimate

ASSUMPTION_FIELDS = {f.name for f in fields(inv.Assumptions)}


def run(profile: PropertyProfile, ctx: MarketContext, overrides: dict[str, float] | None = None) -> dict:
    estimates = market_estimate(ctx, profile)
    assumptions = inv.Assumptions()
    estimated_factors: list[str] = []
    for key, est in estimates.items():
        if key not in ASSUMPTION_FIELDS:
            continue
        if est is None:
            estimated_factors.append(key)
        else:
            setattr(assumptions, key, est.value)
    for key, value in (overrides or {}).items():
        if key in ASSUMPTION_FIELDS:
            setattr(assumptions, key, value)
            estimated_factors = [k for k in estimated_factors if k != key]  # user-provided, no longer a gap

    analysis = inv.analyze(property_inputs(profile, ctx), assumptions)
    analysis["factors"] = {k: (asdict(v) if isinstance(v, FactorEstimate) else None) for k, v in estimates.items()}
    analysis["estimated_factors"] = sorted(estimated_factors)
    return analysis
