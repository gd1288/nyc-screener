"""Market factors that feed the valuation engine's Assumptions.

Every factor is defined once here with the `Assumptions` field it fills, and a function that tries
to back it with real data. When a factor has no real source, `market_estimate` returns `None` for
it rather than inventing a plausible-looking number — the engine then falls back to the
`Assumptions` dataclass default and records the factor as estimated. `app.cli research-gaps` reads
exactly that "no source" signal to write `research/gaps.json`, which is what the `research-analyst`
subagent checks first before searching. Wiring a source for a gap here (e.g. FRED MORTGAGE30US for
`interest_rate`) is a normal `add-data-source` task, not a special valuation-only path.
"""

from collections.abc import Callable
from dataclasses import dataclass

from app.scoring import investment as inv
from app.services import MarketContext, property_inputs
from app.valuation.property import AddressLookup


@dataclass
class PropertyProfile:
    """A property to value. Distinct from `Listing` (an active/sold marketplace row) — this can be
    any property, saved or hypothetical, and carries no listing lifecycle fields."""

    price: float
    property_type: str = "condo"
    address: str | None = None
    nta_code: str | None = None
    sqft: float | None = None
    bedrooms: float | None = None
    common_charges: float | None = None
    property_taxes: float | None = None
    rent_estimate: float | None = None

    @classmethod
    def from_address_lookup(cls, price: float, lookup: AddressLookup, **kw) -> "PropertyProfile":
        return cls(price=price, address=lookup.address, nta_code=lookup.nta_code, **kw)


@dataclass
class FactorEstimate:
    key: str
    label: str
    value: float
    p10: float
    p90: float
    source: str
    as_of: str | None


@dataclass
class FactorDef:
    key: str  # must match an `Assumptions` field name
    label: str
    estimate: Callable[[MarketContext, PropertyProfile], FactorEstimate | None]


def _area_for_metrics(ctx: MarketContext, profile: PropertyProfile) -> dict[str, float]:
    """The seam Phase 1 (US-ready areas) will change: today this reads `MarketContext.metrics`
    keyed by NTA code; once an area model exists, this becomes a CBSA/tract lookup and every
    `FactorDef.estimate` below keeps working unchanged."""
    return ctx.metrics.get(profile.nta_code or "", {})


def _estimate_appreciation(ctx: MarketContext, profile: PropertyProfile) -> FactorEstimate | None:
    m = _area_for_metrics(ctx, profile)
    has_neighborhood_signal = "zhvi_cagr_10y" in m
    if ctx.city_value_cagr_10y is None and not has_neighborhood_signal:
        return None
    # Reuse the same PropertyInputs construction the engine uses for the rest of the run (services.
    # property_inputs), rather than building a second one here — a second, slightly different
    # PropertyInputs is exactly how this factor's appreciation could quietly diverge from the
    # Opportunity Score's appreciation for the same property.
    value = inv.base_appreciation(property_inputs(profile, ctx))
    spread = inv.Assumptions().scenario_spread
    source = (
        "Zillow ZHVI 10y CAGR (neighborhood + citywide median), tilted by Growth Score"
        if has_neighborhood_signal
        else "Zillow ZHVI 10y CAGR (citywide median only — no neighborhood-specific data), tilted by Growth Score"
    )
    return FactorEstimate(
        key="appreciation_override",
        label="Long-run appreciation",
        value=value,
        p10=round(value - spread, 4),
        p90=round(value + spread, 4),
        source=source,
        as_of="trailing 10y",
    )


def _no_source(_key: str, _label: str) -> Callable[[MarketContext, PropertyProfile], None]:
    def estimate(_ctx: MarketContext, _profile: PropertyProfile) -> None:
        return None

    return estimate


FACTOR_DEFS: list[FactorDef] = [
    FactorDef("appreciation_override", "Long-run appreciation", _estimate_appreciation),
    FactorDef("interest_rate", "Mortgage rate", _no_source("interest_rate", "Mortgage rate")),
    FactorDef("rent_growth", "Rent growth", _no_source("rent_growth", "Rent growth")),
    FactorDef("vacancy_pct", "Vacancy rate", _no_source("vacancy_pct", "Vacancy rate")),
    FactorDef("expense_growth", "Expense growth", _no_source("expense_growth", "Expense growth")),
]


def market_estimate(ctx: MarketContext, profile: PropertyProfile) -> dict[str, FactorEstimate | None]:
    return {f.key: f.estimate(ctx, profile) for f in FACTOR_DEFS}
