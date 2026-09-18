"""Tax rules. Expected numbers are worked by hand from the statutory rates in `taxes.py`."""

import pytest

from app.valuation import taxes
from app.valuation.taxes import FederalRules, LossElection, RateOutOfRangeError

US = taxes.JURISDICTIONS["US"]  # federal only: 32% ordinary, 25% recapture, LTCG by bracket, 3.8% NIIT
NYC = taxes.JURISDICTIONS["NY:NYC"]


def test_depreciable_basis_is_price_plus_capitalized_costs_less_land():
    assert taxes.depreciable_basis(500_000, 15_000, 0.20) == pytest.approx(412_000)  # 515,000 x 0.80


@pytest.mark.parametrize("land_pct", [-0.01, 1.0, 1.5])
def test_depreciable_basis_rejects_an_impossible_land_share(land_pct):
    with pytest.raises(ValueError):
        taxes.depreciable_basis(500_000, 0, land_pct)


def test_first_year_depreciation_uses_the_mid_month_convention():
    sched = taxes.depreciation_schedule(275_000, 27.5, 3, placed_in_service_month=1)
    assert sched[0] == pytest.approx(10_000 * 11.5 / 12)  # IRS Pub 946 residential table: January = 3.485%
    assert sched[1] == pytest.approx(10_000)


def test_placed_in_service_mid_year_prorates_the_first_year():
    assert taxes.depreciation_schedule(275_000, 27.5, 1, placed_in_service_month=7)[0] == pytest.approx(
        10_000 * 5.5 / 12
    )


def test_cumulative_depreciation_never_exceeds_basis():
    sched = taxes.depreciation_schedule(30_000, 27.5, 40)
    assert sum(sched) == pytest.approx(30_000)
    assert all(a >= 0 for a in sched)
    assert sched[-1] == 0.0  # fully depreciated well before year 40


@pytest.mark.parametrize("basis,life,years", [(0, 27.5, 5), (100_000, 0, 5)])
def test_depreciation_of_nothing_is_zero(basis, life, years):
    assert taxes.depreciation_schedule(basis, life, years) == [0.0] * years


def test_depreciation_life_by_property_kind():
    assert taxes.depreciation_life("condo", FederalRules()) == 27.5
    assert taxes.depreciation_life("office", FederalRules()) == 39.0


def test_recapture_rate_above_the_statutory_ceiling_raises():
    with pytest.raises(RateOutOfRangeError):
        FederalRules(recapture_rate=0.26)


def test_ltcg_bracket_above_twenty_percent_raises():
    with pytest.raises(RateOutOfRangeError):
        FederalRules(ltcg_brackets=((0.0, 0.25),))


def test_with_overrides_revalidates_ceilings_and_rejects_unknown_fields():
    with pytest.raises(RateOutOfRangeError):
        taxes.with_overrides(US, recapture_rate=0.30)
    with pytest.raises(ValueError):
        taxes.with_overrides(US, not_a_rate=0.1)
    assert taxes.with_overrides(US, ordinary_rate=0.37).federal.ordinary_rate == 0.37
    assert taxes.with_overrides(NYC, state_income_rate=0.05).state_income_rate == 0.05


@pytest.mark.parametrize("income,rate", [(0, 0.0), (96_699, 0.0), (96_700, 0.15), (583_749, 0.15), (583_750, 0.20)])
def test_ltcg_rate_brackets(income, rate):
    assert FederalRules().ltcg_rate(income) == rate


def test_jurisdiction_falls_back_from_locality_to_state_to_federal():
    assert taxes.jurisdiction(None).code == "NY:NYC"
    assert taxes.jurisdiction("NY:NYC").code == "NY:NYC"
    assert taxes.jurisdiction("NY:BUFFALO").code == "NY"
    assert taxes.jurisdiction("CA:LA").code == "US"


def test_state_capital_gain_rate_defaults_to_income_rate_unless_overridden():
    assert NYC.combined_capital_gain_rate == pytest.approx(0.0685 + 0.03876)
    j = taxes.Jurisdiction(
        code="X", name="X", state_income_rate=0.05, local_income_rate=0.01, state_capital_gain_rate=0.02
    )
    assert j.combined_capital_gain_rate == pytest.approx(0.03)


@pytest.mark.parametrize(
    "election,magi,expected",
    [
        (LossElection.SUSPEND, 0, 0.0),
        (LossElection.REAL_ESTATE_PROFESSIONAL, 500_000, 40_000.0),
        (LossElection.ACTIVE_PARTICIPATION, 100_000, 25_000.0),  # full allowance up to the phase-out start
        (LossElection.ACTIVE_PARTICIPATION, 125_000, 12_500.0),  # halfway through the phase-out
        (LossElection.ACTIVE_PARTICIPATION, 150_000, 0.0),
    ],
)
def test_allowed_loss_by_election(election, magi, expected):
    assert taxes.allowed_loss(40_000, election, magi, FederalRules()) == pytest.approx(expected)


def test_allowed_loss_never_exceeds_the_loss_itself_or_goes_negative():
    assert taxes.allowed_loss(10_000, LossElection.ACTIVE_PARTICIPATION, 0, FederalRules()) == 10_000
    assert taxes.allowed_loss(-5, LossElection.REAL_ESTATE_PROFESSIONAL, 0, FederalRules()) == 0.0


def test_profit_absorbs_suspended_losses_before_it_is_taxed():
    # income = 50,000 - 20,000 - 10,000 = 20,000; 5,000 suspended is released, leaving 15,000 x 32%.
    t = taxes.operating_tax(50_000, 20_000, 10_000, 5_000, US)
    assert (t.taxable_income, t.suspended_released, t.suspended_balance) == (15_000, 5_000, 0)
    assert t.tax == pytest.approx(4_800)


def test_suspended_balance_only_partly_used_carries_forward():
    t = taxes.operating_tax(50_000, 20_000, 10_000, 30_000, US)  # income 20,000 < 30,000 suspended
    assert (t.taxable_income, t.suspended_released, t.suspended_balance, t.tax) == (0, 20_000, 10_000, 0)


def test_loss_is_suspended_by_default():
    t = taxes.operating_tax(20_000, 25_000, 10_000, 1_000, US)  # loss of 15,000
    assert (t.deductible_loss, t.suspended_added, t.suspended_balance, t.tax) == (0, 15_000, 16_000, 0)


def test_active_participation_deducts_up_to_the_allowance_and_suspends_the_rest():
    t = taxes.operating_tax(20_000, 25_000, 10_000, 0, US, LossElection.ACTIVE_PARTICIPATION, magi=125_000)
    assert t.deductible_loss == pytest.approx(12_500)
    assert t.suspended_added == pytest.approx(2_500)
    assert t.tax == pytest.approx(-12_500 * 0.32)  # a tax saving


def test_operating_tax_rate_includes_state_and_city():
    t = taxes.operating_tax(50_000, 20_000, 10_000, 0, NYC)
    assert t.tax == pytest.approx(20_000 * (0.32 + 0.0685 + 0.03876))


def test_sale_splits_recapture_from_capital_gain_and_adds_niit():
    # Net 940,000 - adjusted basis 500,000 = 440,000 gain, of which 100,000 is recapture (25%).
    # Remaining 340,000 at 15% (income 440,000 sits in the 15% band). NIIT: (440,000 - 250,000) x 3.8%.
    s = taxes.tax_on_sale(1_000_000, 60_000, 600_000, 100_000, US)
    assert s.adjusted_basis == 500_000
    assert (s.total_gain, s.recapture_gain, s.capital_gain) == (440_000, 100_000, 340_000)
    assert s.recapture_tax == pytest.approx(25_000)
    assert s.capital_gains_tax == pytest.approx(51_000)
    assert s.niit == pytest.approx(7_220)
    assert s.total == pytest.approx(83_220)


def test_sale_adds_state_and_city_tax_on_the_whole_gain():
    s = taxes.tax_on_sale(300_000, 0, 200_000, 0, NYC)  # 100,000 gain, no recapture
    assert s.capital_gains_tax == pytest.approx(15_000)
    assert s.niit == 0
    assert s.state_local_tax == pytest.approx(100_000 * (0.0685 + 0.03876))
    assert s.total == pytest.approx(15_000 + 10_726)


def test_recapture_is_capped_at_the_gain():
    s = taxes.tax_on_sale(500_000, 0, 480_000, 100_000, US)  # adjusted basis 380,000, gain 120,000
    assert s.recapture_gain == 100_000
    s = taxes.tax_on_sale(390_000, 0, 480_000, 100_000, US)  # gain only 10,000 < depreciation taken
    assert s.recapture_gain == 10_000
    assert s.capital_gain == 0


def test_suspended_losses_reduce_tax_on_a_gain_at_the_ordinary_rate():
    plain = taxes.tax_on_sale(300_000, 0, 200_000, 0, US)
    released = taxes.tax_on_sale(300_000, 0, 200_000, 0, US, suspended_balance=20_000)
    assert released.suspended_benefit == pytest.approx(6_400)
    assert released.total == pytest.approx(plain.total - 6_400)


def test_loss_on_sale_releases_suspended_balance_and_yields_a_benefit():
    # Net 470,000 vs adjusted basis 550,000 = 80,000 loss; with 10,000 suspended, 90,000 x 32% saved.
    s = taxes.tax_on_sale(500_000, 30_000, 600_000, 50_000, US, suspended_balance=10_000)
    assert s.total_gain == -80_000
    assert s.total == pytest.approx(-28_800)
    assert s.capital_gains_tax == 0 and s.recapture_tax == 0


def test_adjusted_basis_cannot_go_negative():
    s = taxes.tax_on_sale(100_000, 0, 50_000, 80_000, US)
    assert s.adjusted_basis == 0
