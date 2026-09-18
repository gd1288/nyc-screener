"""Per-condo investment model: purchase costs, cash flow, projected returns, and the Opportunity Score.

All inputs marked `estimated` are fallbacks used when the listing doesn't say; the UI flags them.
Tax rates reflect NYC/NYS rules for residential condos as of 2026; review them in `purchase_costs`.
"""

from dataclasses import asdict, dataclass, field

import numpy as np

MANSION_TAX_BRACKETS = [  # (price at or above, rate) - NYS mansion tax, NYC progressive schedule
    (25_000_000, 0.039),
    (20_000_000, 0.035),
    (15_000_000, 0.0325),
    (10_000_000, 0.0225),
    (5_000_000, 0.015),
    (3_000_000, 0.0125),
    (2_000_000, 0.01),
    (1_000_000, 0.01),
]
BEDROOM_RENT_FACTOR = {0: 0.75, 1: 0.9, 2: 1.2, 3: 1.55, 4: 1.9}  # vs. the neighborhood's typical (ZORI) rent


@dataclass
class Assumptions:
    down_payment_pct: float = 0.25
    interest_rate: float = 0.065
    loan_years: int = 30
    vacancy_pct: float = 0.05
    management_pct: float = 0.05
    maintenance_monthly: float = 100.0
    insurance_monthly: float = 60.0  # HO-6 condo policy
    rent_growth: float = 0.03
    expense_growth: float = 0.03
    exit_cost_pct: float = 0.08  # broker + NYC RPTT + NYS transfer tax when selling
    new_development: bool = False  # buyer usually pays sponsor transfer taxes
    appreciation_override: float | None = None  # replaces the base-case appreciation rate
    scenario_spread: float = 0.02


@dataclass
class PropertyInputs:
    price: float
    sqft: float | None = None
    bedrooms: float | None = None
    common_charges: float | None = None  # monthly
    property_taxes: float | None = None  # monthly
    rent_estimate: float | None = None  # monthly
    neighborhood_rent: float | None = None  # ZORI typical rent
    neighborhood_value_cagr_10y: float | None = None
    city_value_cagr_10y: float | None = None
    growth_score: float | None = None
    estimated: list[str] = field(default_factory=list)


def mansion_tax_rate(price: float) -> float:
    for threshold, rate in MANSION_TAX_BRACKETS:
        if price >= threshold:
            return rate
    return 0.0


def purchase_costs(price: float, loan: float, a: Assumptions) -> dict[str, float]:
    costs = {
        "mansion_tax": price * mansion_tax_rate(price),
        "mortgage_recording_tax": loan * (0.01925 if loan >= 500_000 else 0.018) if loan > 0 else 0.0,
        "title_insurance": price * 0.0045,
        "attorney_and_bank_fees": 5_000.0 if loan > 0 else 3_000.0,
    }
    if a.new_development:
        costs["nyc_transfer_tax"] = price * (0.01425 if price > 500_000 else 0.01)
        costs["nys_transfer_tax"] = price * (0.0065 if price >= 3_000_000 else 0.004)
    costs["total"] = sum(costs.values())
    return costs


def monthly_payment(principal: float, annual_rate: float, years: int) -> float:
    if principal <= 0:
        return 0.0
    r, n = annual_rate / 12, years * 12
    return principal / n if r == 0 else principal * r / (1 - (1 + r) ** -n)


def loan_balance(principal: float, annual_rate: float, years: int, months_paid: int) -> float:
    if principal <= 0:
        return 0.0
    r, pmt = annual_rate / 12, monthly_payment(principal, annual_rate, years)
    if r == 0:
        return max(principal - pmt * months_paid, 0.0)
    return max(principal * (1 + r) ** months_paid - pmt * ((1 + r) ** months_paid - 1) / r, 0.0)


def irr(cash_flows: list[float]) -> float | None:
    """Annual IRR by bisection (cash flows are yearly, t=0 first)."""

    def npv(rate):
        return sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows))

    lo, hi = -0.99, 1.0
    if npv(lo) * npv(hi) > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def estimate_rent(p: PropertyInputs) -> tuple[float | None, str]:
    if p.rent_estimate:
        return p.rent_estimate, "listing"
    if p.neighborhood_rent:
        beds = int(min(max(p.bedrooms or 1, 0), 4))
        return p.neighborhood_rent * BEDROOM_RENT_FACTOR[beds], "neighborhood typical rent x bedroom factor"
    return None, "unavailable"


def base_appreciation(p: PropertyInputs) -> float:
    """Long-run growth: city trend, half-weighted toward the neighborhood's own trend, tilted by growth score."""
    city = p.city_value_cagr_10y if p.city_value_cagr_10y is not None else 0.02
    rate = city
    if p.neighborhood_value_cagr_10y is not None:
        rate += 0.5 * (p.neighborhood_value_cagr_10y - city)
    if p.growth_score is not None:
        rate += (p.growth_score - 50) / 50 * 0.01  # score of 100 adds 1pp/yr, 0 subtracts 1pp
    return float(np.clip(rate, -0.02, 0.08))


def analyze(p: PropertyInputs, a: Assumptions | None = None) -> dict:
    a = a or Assumptions()
    estimated = list(p.estimated)
    common = p.common_charges
    if common is None:
        common = (p.sqft * 1.10) if p.sqft else p.price * 0.0008
        estimated.append("common_charges")
    taxes = p.property_taxes
    if taxes is None:
        taxes = p.price * 0.009 / 12
        estimated.append("property_taxes")
    rent, rent_basis = estimate_rent(p)
    if rent_basis != "listing":
        estimated.append("rent")

    loan = p.price * (1 - a.down_payment_pct)
    costs = purchase_costs(p.price, loan, a)
    cash_invested = p.price * a.down_payment_pct + costs["total"]
    mortgage = monthly_payment(loan, a.interest_rate, a.loan_years)

    rent = rent or 0.0
    effective_rent = rent * (1 - a.vacancy_pct)
    opex = common + taxes + a.insurance_monthly + a.maintenance_monthly + rent * a.management_pct
    noi_monthly = effective_rent - opex
    cash_flow_monthly = noi_monthly - mortgage

    base = a.appreciation_override if a.appreciation_override is not None else base_appreciation(p)
    scenarios = {"bear": base - a.scenario_spread, "base": base, "bull": base + a.scenario_spread}
    projections = {
        name: {str(h): _project(p.price, loan, cash_invested, rent, opex, mortgage, rate, h, a) for h in (10, 20)}
        for name, rate in scenarios.items()
    }
    return {
        "assumptions": asdict(a),
        "estimated_fields": sorted(set(estimated)),
        "rent_basis": rent_basis,
        # Unrounded resolved inputs. `monthly` below is rounded for display, which is fine on screen
        # but not as a basis for rebuilding this projection elsewhere: the Excel export drives its
        # live formulas off these, and rounding rent to the dollar first puts year-20 NOI ~$10 out.
        # Exposed rather than recomputed so the workbook can't quietly disagree with the engine.
        "exact": {
            "rent": rent,
            "common_charges": common,
            "property_taxes": taxes,
            "opex_monthly": opex,
            "loan_amount": loan,
            "cash_invested": cash_invested,
            "monthly_payment": mortgage,
        },
        "purchase_costs": {k: round(v) for k, v in costs.items()},
        "cash_invested": round(cash_invested),
        "loan_amount": round(loan),
        "monthly": {
            "rent": round(rent),
            "vacancy": round(rent - effective_rent),
            "common_charges": round(common),
            "property_taxes": round(taxes),
            "insurance": round(a.insurance_monthly),
            "maintenance": round(a.maintenance_monthly),
            "management": round(rent * a.management_pct),
            "noi": round(noi_monthly),
            "mortgage": round(mortgage),
            "cash_flow": round(cash_flow_monthly),
        },
        "gross_yield": rent * 12 / p.price if rent else None,
        "cap_rate": noi_monthly * 12 / p.price if rent else None,
        "cash_on_cash": cash_flow_monthly * 12 / cash_invested if rent and cash_invested else None,
        "appreciation": {k: round(v, 4) for k, v in scenarios.items()},
        "projections": projections,
    }


def _project(price, loan, cash_invested, rent, opex, mortgage, rate, years, a: Assumptions) -> dict:
    flows = [-cash_invested]
    path = []
    cumulative = 0.0
    cash_flow_positive_year = None
    payback_year = None
    for y in range(years):
        r = rent * 12 * (1 + a.rent_growth) ** y * (1 - a.vacancy_pct)
        e = opex * 12 * (1 + a.expense_growth) ** y
        # Debt service stops once the loan is paid off - a hold period can outlast the loan term.
        # Without this the projection keeps charging a full payment against a zero balance, which
        # corrupts IRR, cumulative cash flow and equity multiple (not just the displayed row).
        months_of_payments = min(12, max(a.loan_years * 12 - y * 12, 0))
        mortgage_annual = mortgage * months_of_payments
        noi_annual = r - e
        cf = noi_annual - mortgage_annual
        flows.append(cf)
        cumulative += cf
        value_y = price * (1 + rate) ** (y + 1)
        balance_y = loan_balance(loan, a.interest_rate, a.loan_years, (y + 1) * 12)
        if cash_flow_positive_year is None and cf > 0:
            cash_flow_positive_year = y + 1
        if payback_year is None and cumulative >= cash_invested:
            payback_year = y + 1
        path.append(
            {
                "year": y + 1,
                "noi": round(noi_annual),
                "mortgage": round(mortgage_annual),
                "cash_flow": round(cf),
                "cumulative_cash_flow": round(cumulative),
                "dscr": round(noi_annual / mortgage_annual, 2) if mortgage_annual else None,
                "property_value": round(value_y),
                "loan_balance": round(balance_y),
                "equity": round(value_y - balance_y),
                "sale_proceeds_if_exit_now": round(value_y * (1 - a.exit_cost_pct) - balance_y),
            }
        )
    value = price * (1 + rate) ** years
    balance = loan_balance(loan, a.interest_rate, a.loan_years, years * 12)
    sale_proceeds = value * (1 - a.exit_cost_pct) - balance
    flows[-1] += sale_proceeds
    total_cash_flow = sum(flows[1:]) - sale_proceeds
    result_irr = irr(flows)
    return {
        "value": round(value),
        "equity_at_exit": round(sale_proceeds),
        "cumulative_cash_flow": round(total_cash_flow),
        "profit": round(sum(flows)),
        "equity_multiple": round((sale_proceeds + total_cash_flow) / cash_invested, 2) if cash_invested else None,
        "irr": round(result_irr, 4) if result_irr is not None else None,
        "cash_flow_positive_year": cash_flow_positive_year,
        "payback_year": payback_year,
        "path": path,
    }


def value_score(price_ratio_to_comps: float | None) -> float | None:
    """50 = priced at comps; 100 = 25%+ below; 0 = 25%+ above."""
    if price_ratio_to_comps is None:
        return None
    return float(np.clip(50 + (1 - price_ratio_to_comps) * 200, 0, 100))


def yield_score(cap_rate: float | None) -> float | None:
    """0 at a 0% cap rate, 100 at 5%+ (strong for Manhattan/Brooklyn condos)."""
    if cap_rate is None:
        return None
    return float(np.clip(cap_rate / 0.05 * 100, 0, 100))


OPPORTUNITY_WEIGHTS = {"growth": 0.5, "value": 0.25, "yield": 0.25}


def opportunity_score(growth: float | None, value: float | None, yld: float | None) -> float | None:
    parts = {"growth": growth, "value": value, "yield": yld}
    available = {k: v for k, v in parts.items() if v is not None}
    if not available or growth is None:
        return None
    total_w = sum(OPPORTUNITY_WEIGHTS[k] for k in available)
    return round(sum(OPPORTUNITY_WEIGHTS[k] * v for k, v in available.items()) / total_w, 1)
