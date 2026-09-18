"""Runs a property through the investment model, filling in market factors and reporting which
ones came from real data vs. an unbacked default.

Deliberately thin: all cash-flow math lives in `app.scoring.investment` (reused by the screener's
Opportunity Score too), so a valuation run and a listing's Opportunity Score can never disagree
about the same numbers — see `tests/test_valuation.py::test_engine_matches_investment_analyze`.

Two modes. `"quick"` (the default) is exactly the screener's model. `"deal"` runs that same model
first - so factors, resolved assumptions and every quick-mode key are still returned unchanged -
then adds `analysis["deal"]`: the full staged pro forma from `app.valuation.proforma` (per-year
rows, exit cap rate, taxes, NPV, ratios) built from the *resolved* rent, costs and assumptions. Deal
mode is opt-in so the screener's scores cannot move.
"""

from dataclasses import asdict, dataclass, field, fields, replace

from app.scoring import investment as inv
from app.services import MarketContext, property_inputs
from app.valuation import proforma, taxes
from app.valuation.factors import FactorEstimate, PropertyProfile, market_estimate

ASSUMPTION_FIELDS = {f.name for f in fields(inv.Assumptions)}
MODES = ("quick", "deal")

# Deal-only inputs a scenario may set, and the tax-rate fields `taxes.with_overrides` accepts.
DEAL_FIELDS = {"hold_years", "exit_cap_rate", "exit_cap_spread", "tax_growth", "discount_rate", "other_income_monthly"}
TAX_RATE_FIELDS = {
    "ordinary_rate",
    "recapture_rate",
    "niit_rate",
    "state_income_rate",
    "local_income_rate",
    "state_capital_gain_rate",
}
DEAL_SET_FIELDS = DEAL_FIELDS | TAX_RATE_FIELDS


class UnknownOverrideError(ValueError):
    def __init__(self, keys: set[str]):
        self.keys = keys
        super().__init__(f"Unknown Assumptions field(s): {sorted(keys)}")


@dataclass
class DealOptions:
    """Inputs only the deal-grade pro forma uses. All optional; `tax=None` gives before-tax returns."""

    hold_years: int = 10
    exit_cap_rate: float | None = None
    exit_cap_spread: float | None = None  # exit cap = going-in cap + spread
    tax_growth: float | None = None  # property-tax escalation; None -> expense_growth
    discount_rate: float = 0.08
    other_income_monthly: float = 0.0
    tax: proforma.TaxInputs | None = None
    tax_rate_overrides: dict[str, float] = field(default_factory=dict)

    def with_set(self, changes: dict[str, float]) -> "DealOptions":
        """A copy with `changes` applied. Unknown keys raise; setting a tax rate without tax inputs
        raises too, because it would silently change nothing."""
        if unknown := set(changes) - DEAL_SET_FIELDS:
            raise UnknownOverrideError(unknown)
        rates = {k: v for k, v in changes.items() if k in TAX_RATE_FIELDS}
        plain = {k: v for k, v in changes.items() if k in DEAL_FIELDS}
        if rates and self.tax is None:
            raise ValueError(f"Tax rate(s) {sorted(rates)} set but no tax inputs were given")
        if "hold_years" in plain:
            plain["hold_years"] = int(plain["hold_years"])
        return replace(self, tax_rate_overrides={**self.tax_rate_overrides, **rates}, **plain)


def _proforma_inputs(profile: PropertyProfile, analysis: dict, deal: DealOptions) -> proforma.ProFormaInputs:
    a, ex = analysis["assumptions"], analysis["exact"]
    tax = deal.tax
    if tax is not None and deal.tax_rate_overrides:
        j = tax.jurisdiction if isinstance(tax.jurisdiction, taxes.Jurisdiction) else taxes.jurisdiction(tax.jurisdiction)
        tax = replace(tax, jurisdiction=taxes.with_overrides(j, **deal.tax_rate_overrides))  # re-checks ceilings
    return proforma.ProFormaInputs(
        price=profile.price,
        monthly_rent=ex["rent"],
        hold_years=deal.hold_years,
        common_charges=ex["common_charges"],
        property_taxes=ex["property_taxes"],
        insurance_monthly=a["insurance_monthly"],
        maintenance_monthly=a["maintenance_monthly"],
        other_income_monthly=deal.other_income_monthly,
        vacancy_pct=a["vacancy_pct"],
        management_pct=a["management_pct"],
        down_payment_pct=a["down_payment_pct"],
        interest_rate=a["interest_rate"],
        loan_years=a["loan_years"],
        new_development=a["new_development"],
        rent_growth=a["rent_growth"],
        expense_growth=a["expense_growth"],
        tax_growth=deal.tax_growth,
        appreciation=analysis["appreciation"]["base"],
        exit_cap_rate=deal.exit_cap_rate,
        exit_cap_spread=deal.exit_cap_spread,
        exit_cost_pct=a["exit_cost_pct"],
        tax=tax,
        discount_rate=deal.discount_rate,
    )


def _headline(result: proforma.ProFormaResult) -> dict:
    """The few numbers a comparison needs. `irr` is after-tax when tax inputs were given, else
    before-tax, so a scenario table never mixes the two without saying which."""
    taxed = result.after_tax_flows is not None
    y1 = result.years[0]
    return {
        "after_tax": taxed,
        "irr": result.irr_after_tax if taxed else result.irr_before_tax,
        "irr_before_tax": result.irr_before_tax,
        "irr_after_tax": result.irr_after_tax,
        "equity_multiple": result.equity_multiple_after_tax if taxed else result.equity_multiple_before_tax,
        "npv": result.npv_after_tax if taxed else result.npv_before_tax,
        "payback_years": result.payback_years_after_tax if taxed else result.payback_years_before_tax,
        "dcr_year1": y1.dcr,
        "break_even_ratio_year1": y1.break_even_ratio,
        "exit_cap_rate": result.exit_cap_rate,
    }


def run(
    profile: PropertyProfile,
    ctx: MarketContext,
    overrides: dict[str, float] | None = None,
    mode: str = "quick",
    deal: DealOptions | None = None,
) -> dict:
    if mode not in MODES:
        raise ValueError(f"Unknown mode {mode!r}; expected one of {MODES}")
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
    if mode == "deal":
        result = proforma.project(_proforma_inputs(profile, analysis, deal or DealOptions()))
        analysis["deal"] = {"headline": _headline(result), "proforma": result.to_dict()}
    return analysis
