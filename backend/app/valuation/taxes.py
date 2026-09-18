"""Jurisdiction-pluggable tax rules for the deal-grade pro forma.

Tax treatment is *data*, not engine logic: `FederalRules` plus a `JURISDICTIONS` registry keyed by
state (then locality). Adding a market is a dict entry, not a change to `proforma.py`.

Three things here are deliberate, and each exists because the reference models got them wrong:

1. **Depreciable basis is derived, never entered.** `depreciable_basis()` computes it from price,
   capitalized costs and a land allocation. A free-hand basis field can silently disagree with the
   deal by a large multiple.
2. **Rates are validated against statutory ceilings.** Unrecaptured Section 1250 gain is capped at
   25% and long-term capital gain at 20% (+ NIIT). An out-of-range override raises rather than
   quietly compounding into every downstream number.
3. **Loss deductibility is an election, not an assumption.** Whether a rental loss is currently
   deductible turns on Section 469, the $25k active-participation allowance and the real-estate-
   professional exception. `LossElection` makes the caller choose; the default suspends.

Rates reflect federal law and NY State/NYC rules as of 2026. They are inputs, not constants - every
one is overridable so "what if long-term gains rise to 28%" is a scenario, not a code change.
"""

from dataclasses import dataclass, field, replace
from enum import Enum

# Statutory ceilings. These bound what a caller may set; they are not themselves assumptions.
MAX_RECAPTURE_RATE = 0.25  # unrecaptured Section 1250 gain
MAX_LTCG_RATE = 0.20  # top long-term capital gains bracket, before NIIT

RESIDENTIAL_LIFE = 27.5  # years, straight line
COMMERCIAL_LIFE = 39.0

RESIDENTIAL_KINDS = {"condo", "coop", "single_family", "1_4_family", "multifamily"}


class LossElection(str, Enum):
    """How a rental loss is treated in the year it arises.

    `SUSPEND` is the default because it is the general rule under Section 469: passive losses are
    carried forward against future passive income and released on disposition. The other two are
    taxpayer-specific and must be chosen deliberately.
    """

    SUSPEND = "suspend"
    ACTIVE_PARTICIPATION = "active_participation_25k"
    REAL_ESTATE_PROFESSIONAL = "real_estate_professional"


class RateOutOfRangeError(ValueError):
    """A tax rate override exceeded its statutory ceiling."""

    def __init__(self, name: str, value: float, ceiling: float):
        self.name, self.value, self.ceiling = name, value, ceiling
        super().__init__(f"{name}={value:.4f} exceeds the statutory ceiling of {ceiling:.4f}")


@dataclass(frozen=True)
class FederalRules:
    residential_life: float = RESIDENTIAL_LIFE
    commercial_life: float = COMMERCIAL_LIFE
    recapture_rate: float = 0.25
    # (taxable income at or above, rate) - checked high to low. Defaults are married-filing-jointly.
    ltcg_brackets: tuple[tuple[float, float], ...] = ((583_750.0, 0.20), (96_700.0, 0.15), (0.0, 0.0))
    niit_rate: float = 0.038
    niit_threshold: float = 250_000.0  # MAGI, married filing jointly
    ordinary_rate: float = 0.32  # marginal bracket the investor's other income puts them in
    # Section 469 active-participation allowance, phased out 50 cents per dollar of MAGI over the start.
    allowance: float = 25_000.0
    allowance_phaseout_start: float = 100_000.0
    allowance_phaseout_end: float = 150_000.0

    def __post_init__(self):
        if self.recapture_rate > MAX_RECAPTURE_RATE:
            raise RateOutOfRangeError("recapture_rate", self.recapture_rate, MAX_RECAPTURE_RATE)
        top = max(r for _, r in self.ltcg_brackets)
        if top > MAX_LTCG_RATE:
            raise RateOutOfRangeError("ltcg_brackets", top, MAX_LTCG_RATE)

    def ltcg_rate(self, taxable_income: float) -> float:
        for threshold, rate in sorted(self.ltcg_brackets, reverse=True):
            if taxable_income >= threshold:
                return rate
        return 0.0


@dataclass(frozen=True)
class Jurisdiction:
    """State + local income tax on top of the federal rules.

    Most states tax capital gain as ordinary income, so `capital_gain_rate` defaults to the income
    rate rather than to zero - a separate field only where a state actually differs.
    """

    code: str
    name: str
    state_income_rate: float = 0.0
    local_income_rate: float = 0.0
    state_capital_gain_rate: float | None = None  # None -> taxed as ordinary income
    federal: FederalRules = field(default_factory=FederalRules)

    @property
    def combined_income_rate(self) -> float:
        return self.state_income_rate + self.local_income_rate

    @property
    def combined_capital_gain_rate(self) -> float:
        if self.state_capital_gain_rate is None:
            return self.combined_income_rate
        return self.state_capital_gain_rate + self.local_income_rate


# NY first; every other market is a dict entry, not an engine change.
JURISDICTIONS: dict[str, Jurisdiction] = {
    "NY:NYC": Jurisdiction(
        code="NY:NYC",
        name="New York City, NY",
        state_income_rate=0.0685,  # NYS marginal at a typical investor income
        local_income_rate=0.03876,  # NYC resident top rate
    ),
    "NY": Jurisdiction(code="NY", name="New York State", state_income_rate=0.0685),
    "US": Jurisdiction(code="US", name="Federal only"),
}
DEFAULT_JURISDICTION = "NY:NYC"


def jurisdiction(code: str | None) -> Jurisdiction:
    """Look up a jurisdiction, falling back from `NY:NYC` to `NY` to federal-only."""
    if not code:
        return JURISDICTIONS[DEFAULT_JURISDICTION]
    if code in JURISDICTIONS:
        return JURISDICTIONS[code]
    state = code.split(":")[0]
    return JURISDICTIONS.get(state, JURISDICTIONS["US"])


def depreciation_life(property_kind: str, rules: FederalRules) -> float:
    return rules.residential_life if property_kind in RESIDENTIAL_KINDS else rules.commercial_life


def depreciable_basis(price: float, capitalized_costs: float, land_pct: float) -> float:
    """Price plus capitalized acquisition costs, less the non-depreciable land component.

    Land is never depreciable, which is why `land_pct` is required rather than optional - omitting
    it is the single largest error available in an after-tax model.
    """
    if not 0.0 <= land_pct < 1.0:
        raise ValueError(f"land_pct must be in [0, 1), got {land_pct}")
    return max((price + capitalized_costs) * (1.0 - land_pct), 0.0)


def depreciation_schedule(basis: float, life: float, years: int, placed_in_service_month: int = 1) -> list[float]:
    """Straight-line depreciation with the IRS mid-month convention.

    The first year is pro-rated from the middle of the month the property was placed in service, so
    a January purchase takes 11.5/12 of a full year. Cumulative depreciation is capped at the
    basis: you cannot take more depreciation than you have, which is what keeps the adjusted basis
    from going negative in `tax_on_sale`.
    """
    if life <= 0 or basis <= 0 or years <= 0:
        return [0.0] * max(years, 0)
    full = basis / life
    first_fraction = (12 - placed_in_service_month + 0.5) / 12
    out, taken = [], 0.0
    for y in range(years):
        amount = full * first_fraction if y == 0 else full
        amount = min(amount, max(basis - taken, 0.0))
        taken += amount
        out.append(amount)
    return out


def allowed_loss(loss: float, election: LossElection, magi: float, rules: FederalRules) -> float:
    """How much of a passive rental loss is currently deductible, given the election.

    `loss` is a positive number. Returns the deductible portion; the remainder is suspended and
    carried forward by the caller.
    """
    if loss <= 0:
        return 0.0
    if election is LossElection.REAL_ESTATE_PROFESSIONAL:
        return loss  # not passive at all, so no Section 469 limit applies
    if election is LossElection.ACTIVE_PARTICIPATION:
        start, end = rules.allowance_phaseout_start, rules.allowance_phaseout_end
        if magi <= start:
            allowance = rules.allowance
        elif magi >= end:
            allowance = 0.0
        else:
            allowance = rules.allowance * (1 - (magi - start) / (end - start))
        return min(loss, allowance)
    return 0.0  # SUSPEND


@dataclass
class OperatingTax:
    taxable_income: float
    deductible_loss: float
    suspended_added: float
    suspended_released: float
    suspended_balance: float
    tax: float


def operating_tax(
    noi: float,
    interest: float,
    depreciation: float,
    suspended_balance: float,
    j: Jurisdiction,
    election: LossElection = LossElection.SUSPEND,
    magi: float = 0.0,
) -> OperatingTax:
    """Income tax on one year of operations, threading the suspended-loss balance forward.

    Positive taxable income first absorbs any suspended losses carried in from prior years; a
    remaining loss is deductible only to the extent the election allows, and the rest is suspended.
    """
    rules = j.federal
    rate = rules.ordinary_rate + j.combined_income_rate
    income = noi - interest - depreciation

    if income >= 0:
        released = min(suspended_balance, income)
        taxable = income - released
        return OperatingTax(
            taxable_income=taxable,
            deductible_loss=0.0,
            suspended_added=0.0,
            suspended_released=released,
            suspended_balance=suspended_balance - released,
            tax=taxable * rate,
        )

    loss = -income
    deductible = allowed_loss(loss, election, magi, rules)
    return OperatingTax(
        taxable_income=-deductible,
        deductible_loss=deductible,
        suspended_added=loss - deductible,
        suspended_released=0.0,
        suspended_balance=suspended_balance + (loss - deductible),
        tax=-deductible * rate,
    )


@dataclass
class SaleTax:
    net_proceeds: float
    adjusted_basis: float
    total_gain: float
    recapture_gain: float
    capital_gain: float
    recapture_tax: float
    capital_gains_tax: float
    niit: float
    state_local_tax: float
    suspended_released: float
    suspended_benefit: float
    total: float


def tax_on_sale(
    sale_price: float,
    selling_costs: float,
    original_basis: float,
    cumulative_depreciation: float,
    j: Jurisdiction,
    taxable_income: float = 0.0,
    suspended_balance: float = 0.0,
    magi: float = 0.0,
) -> SaleTax:
    """Tax due on disposition, splitting the gain into Section 1250 recapture and long-term gain.

    Selling costs reduce the amount realised rather than being added to basis - the two are
    equivalent arithmetically, and netting them here keeps `adjusted_basis` meaning what its name
    says. Suspended passive losses are released in full on a fully taxable disposition.
    """
    rules = j.federal
    net_proceeds = sale_price - selling_costs
    adjusted_basis = max(original_basis - cumulative_depreciation, 0.0)
    total_gain = net_proceeds - adjusted_basis

    if total_gain <= 0:
        # A loss on sale still releases the suspended balance, which offsets other income.
        benefit = (suspended_balance + -total_gain) * (rules.ordinary_rate + j.combined_income_rate)
        return SaleTax(
            net_proceeds=net_proceeds,
            adjusted_basis=adjusted_basis,
            total_gain=total_gain,
            recapture_gain=0.0,
            capital_gain=total_gain,
            recapture_tax=0.0,
            capital_gains_tax=0.0,
            niit=0.0,
            state_local_tax=0.0,
            suspended_released=suspended_balance,
            suspended_benefit=benefit,
            total=-benefit,
        )

    recapture_gain = min(cumulative_depreciation, total_gain)
    capital_gain = total_gain - recapture_gain

    recapture_tax = recapture_gain * rules.recapture_rate
    capital_gains_tax = capital_gain * rules.ltcg_rate(taxable_income + total_gain)

    over_threshold = max(taxable_income + total_gain - rules.niit_threshold, 0.0)
    niit = min(total_gain, over_threshold) * rules.niit_rate

    state_local_tax = total_gain * j.combined_capital_gain_rate
    suspended_benefit = suspended_balance * (rules.ordinary_rate + j.combined_income_rate)

    return SaleTax(
        net_proceeds=net_proceeds,
        adjusted_basis=adjusted_basis,
        total_gain=total_gain,
        recapture_gain=recapture_gain,
        capital_gain=capital_gain,
        recapture_tax=recapture_tax,
        capital_gains_tax=capital_gains_tax,
        niit=niit,
        state_local_tax=state_local_tax,
        suspended_released=suspended_balance,
        suspended_benefit=suspended_benefit,
        total=recapture_tax + capital_gains_tax + niit + state_local_tax - suspended_benefit,
    )


def with_overrides(j: Jurisdiction, **rates: float) -> Jurisdiction:
    """Return a copy of `j` with federal or state rates replaced, for scenario analysis.

    Ceilings are re-validated, so a scenario cannot set a rate the law does not allow.
    """
    federal_fields = {k: v for k, v in rates.items() if hasattr(j.federal, k)}
    juris_fields = {k: v for k, v in rates.items() if hasattr(j, k) and k != "federal"}
    if unknown := set(rates) - set(federal_fields) - set(juris_fields):
        raise ValueError(f"Unknown tax rate field(s): {sorted(unknown)}")
    out = replace(j, **juris_fields) if juris_fields else j
    if federal_fields:
        out = replace(out, federal=replace(out.federal, **federal_fields))
    return out
