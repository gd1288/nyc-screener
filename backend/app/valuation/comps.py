"""What comparable properties say a property is worth.

This is the only place that turns comparables into a *value*. `services.comps_ratio` (the screener's
Opportunity Score input) and `eval.py` (the accuracy gate) both call it, so the number the screener
prices a listing against and the number the eval grades can never drift apart — the same reason
`engine.py` delegates its cash-flow math to `scoring/investment.py` rather than restating it.

Deliberately pure: no database and no `app.services` import (which imports this module). Callers
assemble the comps; the as-of filtering that keeps a backtest honest lives with the query in
`eval.py`, not here.
"""

from dataclasses import dataclass
from statistics import median

MIN_SQFT = 200  # below this, a listing's stated sqft is usually a data-entry artifact, not a studio
MIN_BUILDING_COMPS = 3  # a median of one or two sales is a coincidence, not a comparable


@dataclass
class CompsEstimate:
    value: float
    basis: str
    n_comps: int | None


def from_neighborhood_ppsf(sqft: float | None, nta_ppsf: float | None) -> CompsEstimate | None:
    """Value implied by the neighborhood's $/sqft. Reflects what's being *asked* today, so it can't
    be replayed historically — `eval.py` deliberately can't use this path."""
    if sqft and sqft > MIN_SQFT and nta_ppsf:
        return CompsEstimate(value=sqft * nta_ppsf, basis="$/sqft vs active listings in neighborhood", n_comps=None)
    return None


def from_building_sales(prices: list[float]) -> CompsEstimate | None:
    """Value implied by recent closed sales in the same building."""
    if len(prices) < MIN_BUILDING_COMPS:
        return None
    return CompsEstimate(
        value=median(prices), basis=f"price vs {len(prices)} recent sales in building", n_comps=len(prices)
    )


def estimate_value(sqft: float | None, nta_ppsf: float | None, building_prices: list[float]) -> CompsEstimate | None:
    """Best available comparable value, preferring $/sqft over a building median.

    Order matters and is inherited from the screener: a $/sqft comparison adjusts for unit size,
    while a building median treats a studio and a penthouse as the same comp.
    """
    return from_neighborhood_ppsf(sqft, nta_ppsf) or from_building_sales(building_prices)
