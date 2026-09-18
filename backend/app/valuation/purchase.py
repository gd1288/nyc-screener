"""Purchase plan: what buying and owning one property costs, itemised, for any way of using it.

Answers "if I bought this, what would I pay?": the cash needed at closing, every obligation in a typical month,
each year of ownership (up to the loan's life), and what selling at a chosen year would net. It models *how the
property is used* through `phases`: from a given year, a share of it is rented out (0 = you live in all of it,
1 = a tenant has all of it, 0.33 = you rent one bedroom of three). So "live in it", "rent it out", "live in one
room, rent the others" and "live in it, then rent it" are all the same calculation with different phases.

Pre-tax, and it does not model income tax, mortgage-interest deductions or capital gains: those depend on the
buyer. The closing costs come from `scoring/investment.purchase_costs`, so this page and the screener agree.
The artifact carries a line-for-line JavaScript mirror (`purchasePlan` in docs/artifact/staging.html) and
tests/test_purchase.py runs both on the same inputs.
"""

from dataclasses import dataclass, field

from app.scoring import investment as inv

MAX_YEARS = 40


@dataclass
class CustomCost:
    """A cost the buyer adds: utilities not in the defaults, a renovation, a special assessment, a parking space.
    `frequency` is 'monthly', 'annual' or 'once'. A 'once' cost in year 0 is paid at closing. Amounts do not grow."""

    name: str
    amount: float
    frequency: str = "monthly"
    start_year: int = 1
    end_year: int | None = None


@dataclass
class PurchaseInputs:
    price: float
    down_pct: float = 0.25
    rate: float = 0.065
    term_years: int = 30
    horizon_years: int = 10
    tax_annual: float = 0.0
    common_monthly: float = 0.0
    insurance_monthly: float = 60.0
    maintenance_monthly: float = 100.0
    utilities_monthly: float = 0.0  # what the owner pays while living in any part of the property
    rent_monthly: float = 0.0  # market rent for the WHOLE property
    phases: list[dict] = field(default_factory=lambda: [{"from_year": 1, "share_rented": 0.0}])
    vacancy_pct: float = 0.05
    management_pct: float = 0.0
    tax_growth: float = 0.03
    expense_growth: float = 0.03
    rent_growth: float = 0.03
    appreciation: float = 0.02
    selling_cost_pct: float = 0.08
    pmi_annual_pct: float = 0.005  # of the original loan, while the loan is over 80% of the price and down < 20%
    new_development: bool = False
    custom: list[CustomCost] = field(default_factory=list)


def _share(phases: list[dict], year: int) -> float:
    share = 0.0
    for p in sorted(phases, key=lambda x: x["from_year"]):
        if p["from_year"] <= year:
            share = p["share_rented"]
    return share


def _custom_in_year(custom: list[CustomCost], year: int) -> float:
    total = 0.0
    for c in custom:
        end = c.end_year if c.end_year is not None else MAX_YEARS
        if c.frequency == "once":
            total += c.amount if c.start_year == year else 0.0
        elif c.start_year <= year <= end:
            total += c.amount * (12 if c.frequency == "monthly" else 1)
    return total


def plan(i: PurchaseInputs) -> dict:
    loan = i.price * (1 - i.down_pct)
    n_months = i.term_years * 12
    pmt = inv.monthly_payment(loan, i.rate, i.term_years)
    closing = inv.purchase_costs(i.price, loan, inv.Assumptions(new_development=i.new_development))
    upfront_custom = _custom_in_year(i.custom, 0)
    cash_to_close = {
        "down_payment": i.price * i.down_pct,
        "closing_costs": closing,
        "your_upfront_costs": upfront_custom,
        "total": i.price * i.down_pct + closing["total"] + upfront_custom,
    }
    pmi_on = i.down_pct < 0.20 and loan > 0 and i.pmi_annual_pct > 0
    horizon = max(1, min(i.horizon_years, MAX_YEARS))
    n_years = min(max(horizon, i.term_years), MAX_YEARS)

    years, cum = [], 0.0
    for y in range(1, n_years + 1):
        bal_start = inv.loan_balance(loan, i.rate, i.term_years, 12 * (y - 1)) if 12 * (y - 1) < n_months else 0.0
        bal_end = inv.loan_balance(loan, i.rate, i.term_years, 12 * y) if 12 * (y - 1) < n_months else 0.0
        payment = 12 * pmt if 12 * (y - 1) < n_months else 0.0
        principal = bal_start - bal_end
        interest = payment - principal
        g_exp, g_tax, g_rent = (1 + i.expense_growth) ** (y - 1), (1 + i.tax_growth) ** (y - 1), (1 + i.rent_growth) ** (y - 1)
        share = _share(i.phases, y)
        rent_in = i.rent_monthly * 12 * g_rent * share * (1 - i.vacancy_pct)
        rent_avoided = i.rent_monthly * 12 * g_rent * (1 - share)  # what living in your part would cost to rent instead
        tax = i.tax_annual * g_tax
        common = i.common_monthly * 12 * g_exp
        insurance = i.insurance_monthly * 12 * g_exp
        maintenance = i.maintenance_monthly * 12 * g_exp
        utilities = i.utilities_monthly * 12 * g_exp if share < 1 else 0.0  # a tenant pays them once all of it is rented
        pmi = i.pmi_annual_pct * loan if pmi_on and bal_start > 0.8 * i.price else 0.0
        management = i.management_pct * rent_in
        custom = _custom_in_year(i.custom, y)
        total_out = payment + tax + common + insurance + maintenance + utilities + pmi + management + custom
        net_out = total_out - rent_in
        cum += net_out
        value = i.price * (1 + i.appreciation) ** y
        years.append({
            "year": y, "share_rented": share, "mortgage_payment": payment, "principal": principal, "interest": interest,
            "property_tax": tax, "common_charges": common, "insurance": insurance, "maintenance": maintenance,
            "utilities": utilities, "pmi": pmi, "management": management, "your_costs": custom,
            "total_out": total_out, "rent_in": rent_in, "rent_avoided": rent_avoided, "net_out": net_out, "cumulative_net_out": cum,
            "loan_balance": bal_end, "home_value": value, "equity": value - bal_end,
        })

    y1 = years[0]
    monthly = {k: v / 12 for k, v in y1.items() if k not in ("year", "share_rented", "loan_balance", "home_value", "equity", "cumulative_net_out")}
    h = years[horizon - 1]
    selling = h["home_value"] * i.selling_cost_pct
    net_proceeds = h["home_value"] - selling - h["loan_balance"]
    total_out_h = sum(x["total_out"] for x in years[:horizon])
    avoided_h = sum(x["rent_avoided"] for x in years[:horizon])
    cum_net_h = h["cumulative_net_out"]
    crossover = next((x["year"] for x in years if x["principal"] > x["interest"] > 0 or (x["interest"] <= 0 < x["principal"])), None)
    pmi_end = next((x["year"] for x in years if pmi_on and x["pmi"] == 0), None)
    return {
        "loan": loan,
        "monthly_payment": pmt,
        "cash_to_close": cash_to_close,
        "monthly_year1": monthly,
        "years": years,
        "sale": {"year": horizon, "home_value": h["home_value"], "selling_costs": selling,
                 "loan_payoff": h["loan_balance"], "net_proceeds": net_proceeds},
        "summary": {
            "cash_to_close": cash_to_close["total"],
            "monthly_out_year1": monthly["total_out"],
            "monthly_rent_year1": monthly["rent_in"],
            "monthly_net_year1": monthly["net_out"],
            "total_out_over_horizon": total_out_h,
            "net_out_over_horizon": cum_net_h,
            "net_gain_at_horizon": net_proceeds - cash_to_close["total"] - cum_net_h,
            "rent_avoided_over_horizon": avoided_h,
            "net_gain_vs_renting": net_proceeds - cash_to_close["total"] - cum_net_h + avoided_h,
            "principal_overtakes_interest_year": crossover,
            "loan_paid_off_year": i.term_years if loan > 0 else None,
            "pmi_ends_year": pmi_end,
        },
    }
