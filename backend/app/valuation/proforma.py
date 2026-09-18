"""Deal-grade pro forma: the staged underwriting chain, year by year, before and after tax.

    Potential Gross Rent -> vacancy -> Effective Gross Income -> itemized OpEx -> NOI
      -> debt service -> Before-Tax Cash Flow -> depreciation -> taxable income -> income tax
      -> After-Tax Cash Flow -> reversion (exit value, costs, loan payoff, sale tax) -> IRR

Each stage consumes only the stage above it, so any number can be traced back to its inputs (the
memo `research/memos/2026-09-17-valuation-methodology.md` is the spec).

Deliberately *not* a second copy of the screener's math: amortization, purchase costs and IRR come
from `app.scoring.investment`, and tax treatment comes from `app.valuation.taxes`. What this module
adds is the structure the flat `investment._project` lacks: per-year growth vectors, a separate
property-tax growth rate, management as a share of collected income, cap-rate exits priced off
forward NOI, and the tax layer. With growth scalars, no management fee, no tax and an appreciation
exit it reproduces `investment.analyze` exactly (`tests/test_proforma.py` pins that), so the two
cannot silently drift apart.
"""

from dataclasses import asdict, dataclass, field

from app.scoring.investment import Assumptions, irr, loan_balance, monthly_payment, purchase_costs
from app.valuation import taxes

Rate = float | list[float]


@dataclass
class TaxInputs:
    """Investor-level tax inputs. `land_pct` has no default on purpose: omitting the land share is
    the largest single error available in an after-tax model (see `taxes.depreciable_basis`)."""

    land_pct: float
    jurisdiction: str | taxes.Jurisdiction | None = None  # code like "NY:NYC"; None -> the default market
    election: taxes.LossElection = taxes.LossElection.SUSPEND
    # Other taxable income / MAGI. It sets the Section 469 allowance and the LTCG/NIIT brackets on
    # sale. The default matches `FederalRules.ordinary_rate`'s 32% bracket; it is an assumption.
    other_income: float = 300_000.0
    property_kind: str = "condo"
    placed_in_service_month: int = 1


@dataclass
class ProFormaInputs:
    price: float
    monthly_rent: float
    hold_years: int = 10
    # Monthly operating costs, in year-1 dollars.
    common_charges: float = 0.0
    property_taxes: float = 0.0
    insurance_monthly: float = 0.0
    maintenance_monthly: float = 0.0
    other_income_monthly: float = 0.0  # parking, laundry etc.; not subject to vacancy
    vacancy_pct: float = 0.05
    management_pct: float = 0.05  # of effective gross income: you cannot manage income you never collect
    # Financing
    down_payment_pct: float = 0.25
    interest_rate: float = 0.065
    loan_years: int = 30
    new_development: bool = False
    # Growth. A list is one rate per year, entering year i+1 (list[0] takes year 1 to year 2);
    # it must cover the hold, and the forward-NOI year reuses its last value.
    rent_growth: Rate = 0.03
    expense_growth: Rate = 0.03
    tax_growth: Rate | None = None  # property taxes escalate on their own path; None -> expense_growth
    appreciation: Rate = 0.03  # per year; list[0] is year 1's appreciation
    # Exit. With `exit_cap_rate` set, value = forward (year hold+1) NOI / cap rate: a buyer prices
    # next year's income. Otherwise the property appreciates at `appreciation`.
    exit_cap_rate: float | None = None
    exit_cost_pct: float = 0.08
    tax: TaxInputs | None = None  # None -> before-tax only

    def __post_init__(self):
        if self.price <= 0:
            raise ValueError(f"price must be positive, got {self.price}")
        if self.hold_years < 1:
            raise ValueError(f"hold_years must be at least 1, got {self.hold_years}")
        if not 0.0 <= self.down_payment_pct <= 1.0:
            raise ValueError(f"down_payment_pct must be in [0, 1], got {self.down_payment_pct}")
        if not 0.0 <= self.vacancy_pct <= 1.0:
            raise ValueError(f"vacancy_pct must be in [0, 1], got {self.vacancy_pct}")
        if self.exit_cap_rate is not None and self.exit_cap_rate <= 0:
            raise ValueError(f"exit_cap_rate must be positive, got {self.exit_cap_rate}")
        for name in ("rent_growth", "expense_growth", "tax_growth", "appreciation"):
            rate = getattr(self, name)
            if isinstance(rate, list) and len(rate) < self.hold_years:
                raise ValueError(f"{name} has {len(rate)} entries but the hold is {self.hold_years} years")


@dataclass
class YearRow:
    year: int
    potential_gross_rent: float
    vacancy: float
    other_income: float
    effective_gross_income: float
    common_charges: float
    property_taxes: float
    insurance: float
    maintenance: float
    management: float
    operating_expenses: float
    noi: float
    debt_service: float
    interest: float
    principal: float
    loan_balance: float
    before_tax_cash_flow: float
    property_value: float | None  # only on the appreciation path
    # Tax layer - None when the pro forma is before-tax only.
    depreciation: float | None = None
    taxable_income: float | None = None
    income_tax: float | None = None  # negative when a loss is deductible
    suspended_loss_balance: float | None = None
    after_tax_cash_flow: float | None = None


@dataclass
class Reversion:
    exit_value: float
    selling_costs: float
    loan_payoff: float
    before_tax_equity: float
    sale_tax: taxes.SaleTax | None = None
    after_tax_equity: float | None = None


@dataclass
class ProFormaResult:
    cash_invested: float
    purchase_costs: dict[str, float]
    loan_amount: float
    depreciable_basis: float | None
    years: list[YearRow]
    reversion: Reversion
    before_tax_flows: list[float]
    after_tax_flows: list[float] | None
    irr_before_tax: float | None
    irr_after_tax: float | None
    equity_multiple_before_tax: float | None
    equity_multiple_after_tax: float | None
    forward_noi: float
    going_in_cap_rate: float = field(default=0.0)

    def to_dict(self) -> dict:
        return asdict(self)


def _factors(rate: Rate, n: int) -> list[float]:
    """Cumulative growth index: out[0] = 1 and out[i] = out[i-1] * (1 + rate_i), where rate_i is the
    scalar or `rate[i-1]` (the last entry is reused past the end of a list). For a scalar this is
    exactly `(1 + rate) ** i`."""
    out = [1.0]
    for i in range(1, n + 1):
        g = rate if not isinstance(rate, list) else rate[min(i - 1, len(rate) - 1)]
        out.append(out[-1] * (1 + g))
    return out


def _resolve_jurisdiction(t: TaxInputs) -> taxes.Jurisdiction:
    return t.jurisdiction if isinstance(t.jurisdiction, taxes.Jurisdiction) else taxes.jurisdiction(t.jurisdiction)


def project(inp: ProFormaInputs) -> ProFormaResult:
    n = inp.hold_years
    loan = inp.price * (1 - inp.down_payment_pct)
    costs = purchase_costs(inp.price, loan, Assumptions(new_development=inp.new_development))
    cash_invested = inp.price * inp.down_payment_pct + costs["total"]
    payment = monthly_payment(loan, inp.interest_rate, inp.loan_years)

    # n + 1 growth steps: the extra one is the forward year a cap-rate exit is priced on.
    rent_idx = _factors(inp.rent_growth, n + 1)
    exp_idx = _factors(inp.expense_growth, n + 1)
    tax_idx = _factors(inp.tax_growth if inp.tax_growth is not None else inp.expense_growth, n + 1)
    value_idx = _factors(inp.appreciation, n)

    def operating(y: int) -> dict[str, float]:
        """Income statement for 0-based year `y`, down to NOI."""
        pgr = inp.monthly_rent * 12 * rent_idx[y]
        vacancy = pgr * inp.vacancy_pct  # vacancy reduces income exactly once
        other = inp.other_income_monthly * 12 * rent_idx[y]
        egi = pgr - vacancy + other
        common = inp.common_charges * 12 * exp_idx[y]
        prop_tax = inp.property_taxes * 12 * tax_idx[y]
        insurance = inp.insurance_monthly * 12 * exp_idx[y]
        maintenance = inp.maintenance_monthly * 12 * exp_idx[y]
        management = egi * inp.management_pct
        opex = common + prop_tax + insurance + maintenance + management
        return {
            "pgr": pgr,
            "vacancy": vacancy,
            "other": other,
            "egi": egi,
            "common": common,
            "prop_tax": prop_tax,
            "insurance": insurance,
            "maintenance": maintenance,
            "management": management,
            "opex": opex,
            "noi": egi - opex,
        }

    tax = inp.tax
    j = _resolve_jurisdiction(tax) if tax else None
    capitalized = costs["total"] - costs["mortgage_recording_tax"]  # loan costs are amortized, not basis
    original_basis = inp.price + capitalized
    basis = taxes.depreciable_basis(inp.price, capitalized, tax.land_pct) if tax else None
    dep_schedule = (
        taxes.depreciation_schedule(
            basis,
            taxes.depreciation_life(tax.property_kind, j.federal),
            n,
            tax.placed_in_service_month,
        )
        if tax and j
        else []
    )

    rows: list[YearRow] = []
    balance_prev = loan
    suspended = 0.0
    cumulative_dep = 0.0
    for y in range(n):
        op = operating(y)
        # Debt service stops once the loan is paid off; a hold can outlast the loan term.
        months = min(12, max(inp.loan_years * 12 - y * 12, 0))
        debt_service = payment * months
        balance = loan_balance(loan, inp.interest_rate, inp.loan_years, (y + 1) * 12)
        principal = balance_prev - balance  # interest by difference, so there is one amortization formula
        interest = debt_service - principal
        btcf = op["noi"] - debt_service
        row = YearRow(
            year=y + 1,
            potential_gross_rent=op["pgr"],
            vacancy=op["vacancy"],
            other_income=op["other"],
            effective_gross_income=op["egi"],
            common_charges=op["common"],
            property_taxes=op["prop_tax"],
            insurance=op["insurance"],
            maintenance=op["maintenance"],
            management=op["management"],
            operating_expenses=op["opex"],
            noi=op["noi"],
            debt_service=debt_service,
            interest=interest,
            principal=principal,
            loan_balance=balance,
            before_tax_cash_flow=btcf,
            property_value=None if inp.exit_cap_rate else inp.price * value_idx[y + 1],
        )
        if tax and j:
            depreciation = dep_schedule[y]
            cumulative_dep += depreciation
            ot = taxes.operating_tax(op["noi"], interest, depreciation, suspended, j, tax.election, tax.other_income)
            suspended = ot.suspended_balance
            row.depreciation = depreciation
            row.taxable_income = ot.taxable_income
            row.income_tax = ot.tax
            row.suspended_loss_balance = suspended
            row.after_tax_cash_flow = btcf - ot.tax
        rows.append(row)
        balance_prev = balance

    forward_noi = operating(n)["noi"]
    exit_value = forward_noi / inp.exit_cap_rate if inp.exit_cap_rate else inp.price * value_idx[n]
    selling_costs = exit_value * inp.exit_cost_pct
    payoff = rows[-1].loan_balance
    pre_tax_equity = exit_value - selling_costs - payoff
    reversion = Reversion(
        exit_value=exit_value, selling_costs=selling_costs, loan_payoff=payoff, before_tax_equity=pre_tax_equity
    )

    before_flows = [-cash_invested] + [r.before_tax_cash_flow for r in rows]
    before_flows[-1] += pre_tax_equity

    after_flows: list[float] | None = None
    if tax and j:
        sale = taxes.tax_on_sale(
            exit_value,
            selling_costs,
            original_basis,
            cumulative_dep,
            j,
            taxable_income=tax.other_income,
            suspended_balance=suspended,
            magi=tax.other_income,
        )
        reversion.sale_tax = sale
        reversion.after_tax_equity = pre_tax_equity - sale.total
        after_flows = [-cash_invested] + [r.after_tax_cash_flow for r in rows]  # type: ignore[misc]
        after_flows[-1] += reversion.after_tax_equity

    def multiple(flows: list[float]) -> float | None:
        return sum(flows[1:]) / cash_invested if cash_invested else None

    return ProFormaResult(
        cash_invested=cash_invested,
        purchase_costs=costs,
        loan_amount=loan,
        depreciable_basis=basis,
        years=rows,
        reversion=reversion,
        before_tax_flows=before_flows,
        after_tax_flows=after_flows,
        irr_before_tax=irr(before_flows),
        irr_after_tax=irr(after_flows) if after_flows else None,
        equity_multiple_before_tax=multiple(before_flows),
        equity_multiple_after_tax=multiple(after_flows) if after_flows else None,
        forward_noi=forward_noi,
        going_in_cap_rate=rows[0].noi / inp.price,
    )
