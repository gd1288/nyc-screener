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


class UnknownOverrideError(ValueError):
    def __init__(self, keys: set[str]):
        self.keys = keys
        super().__init__(f"Unknown Assumptions field(s): {sorted(keys)}")


def run(profile: PropertyProfile, ctx: MarketContext, overrides: dict[str, float] | None = None) -> dict:
    overrides = overrides or {}
    if unknown := set(overrides) - ASSUMPTION_FIELDS:
        raise UnknownOverrideError(unknown)

    estimates = market_estimate(ctx, profile)
    assumptions = inv.Assumptions()
    # "Estimated" tracks which factors have no real data source at all - a property of the factor
    # for this profile, not of what value the caller happened to plug in this run. An override
    # replaces the *value* used but doesn't make the factor any more backed by real data, so it
    # stays in this list even when overridden (that's what lets the UI and `research-gaps` agree on
    # which factors are gaps).
    estimated_factors = sorted(k for k, est in estimates.items() if est is None and k in ASSUMPTION_FIELDS)
    for key, est in estimates.items():
        if key in ASSUMPTION_FIELDS and est is not None:
            setattr(assumptions, key, est.value)
    for key, value in overrides.items():
        setattr(assumptions, key, value)

    analysis = inv.analyze(property_inputs(profile, ctx), assumptions)
    analysis["factors"] = {k: (asdict(v) if isinstance(v, FactorEstimate) else None) for k, v in estimates.items()}
    analysis["estimated_factors"] = estimated_factors
    return analysis
