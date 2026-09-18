"""Pro forma. The parity test ties this module to `investment.analyze`; the rest are hand-worked."""

import pytest

from app.scoring import investment as inv
from app.valuation import proforma, taxes
from app.valuation.proforma import ProFormaInputs, TaxInputs, project


def deal(**kw) -> ProFormaInputs:
    base = dict(
        price=500_000,
        monthly_rent=3_000,
        common_charges=500,
        property_taxes=400,
        insurance_monthly=50,
        maintenance_monthly=50,
        vacancy_pct=0.05,
        management_pct=0.0,
        down_payment_pct=1.0,  # all cash unless a test says otherwise
        hold_years=10,
    )
    return ProFormaInputs(**{**base, **kw})


def test_year_one_chain_by_hand_all_cash():
    # PGR 36,000; vacancy 5% = 1,800; EGI 34,200. OpEx = (500+400+50+50) x 12 = 12,000. NOI 22,200.
    r = project(deal())
    y1 = r.years[0]
    assert y1.potential_gross_rent == pytest.approx(36_000)
    assert y1.vacancy == pytest.approx(1_800)
    assert y1.effective_gross_income == pytest.approx(34_200)
    assert y1.operating_expenses == pytest.approx(12_000)
    assert y1.noi == pytest.approx(22_200)
    assert y1.debt_service == 0 and y1.before_tax_cash_flow == pytest.approx(22_200)
    # No loan, price under $1M: title 0.45% + $3,000 attorney fee only.
    assert r.cash_invested == pytest.approx(500_000 + 2_250 + 3_000)
    assert r.going_in_cap_rate == pytest.approx(22_200 / 500_000)


@pytest.mark.parametrize("hold,loan_years", [(10, 30), (20, 30), (20, 15)])
def test_matches_investment_analyze_when_the_models_share_assumptions(hold, loan_years):
    """With scalar growth, no management fee, no tax and an appreciation exit, the pro forma and
    `investment.analyze` are the same model (the 20/15 case outlasts the loan and checks payoff)."""
    p = inv.PropertyInputs(
        price=800_000, sqft=800, bedrooms=2, common_charges=900, property_taxes=1_000, rent_estimate=4_500
    )
    a = inv.Assumptions(management_pct=0.0, appreciation_override=0.04, loan_years=loan_years)
    ref = inv.analyze(p, a)["projections"]["base"][str(hold)]

    r = project(
        ProFormaInputs(
            price=800_000,
            monthly_rent=4_500,
            hold_years=hold,
            common_charges=900,
            property_taxes=1_000,
            insurance_monthly=a.insurance_monthly,
            maintenance_monthly=a.maintenance_monthly,
            management_pct=0.0,
            vacancy_pct=a.vacancy_pct,
            down_payment_pct=a.down_payment_pct,
            interest_rate=a.interest_rate,
            loan_years=loan_years,
            rent_growth=a.rent_growth,
            expense_growth=a.expense_growth,
            appreciation=0.04,
            exit_cost_pct=a.exit_cost_pct,
        )
    )
    assert r.irr_before_tax == pytest.approx(ref["irr"], abs=1e-4)
    assert r.reversion.before_tax_equity == pytest.approx(ref["equity_at_exit"], abs=1)
    assert r.reversion.exit_value == pytest.approx(ref["value"], abs=1)
    assert r.equity_multiple_before_tax == pytest.approx(ref["equity_multiple"], abs=0.01)
    for row, ref_row in zip(r.years, ref["path"], strict=True):
        assert row.noi == pytest.approx(ref_row["noi"], abs=1)
        assert row.before_tax_cash_flow == pytest.approx(ref_row["cash_flow"], abs=1)
        assert row.loan_balance == pytest.approx(ref_row["loan_balance"], abs=1)


def test_management_fee_is_a_share_of_collected_income_not_gross_rent():
    # PGR 12,000, 10% vacancy -> EGI 10,800; 5% fee = 540 (not 600).
    y1 = project(deal(monthly_rent=1_000, vacancy_pct=0.10, management_pct=0.05)).years[0]
    assert y1.management == pytest.approx(540)


def test_a_fully_vacant_year_still_owes_expenses_and_debt_service():
    r = project(deal(vacancy_pct=1.0, down_payment_pct=0.25))
    y1 = r.years[0]
    assert y1.effective_gross_income == 0
    assert y1.noi == pytest.approx(-12_000)
    assert y1.before_tax_cash_flow == pytest.approx(-12_000 - y1.debt_service)
    assert y1.debt_service > 0


def test_other_income_is_not_subject_to_vacancy():
    y1 = project(deal(monthly_rent=1_000, other_income_monthly=100, vacancy_pct=0.10)).years[0]
    assert y1.effective_gross_income == pytest.approx(12_000 * 0.9 + 1_200)


def test_a_constant_growth_vector_equals_the_scalar():
    a = project(deal(rent_growth=0.04, appreciation=0.05, down_payment_pct=0.3))
    b = project(deal(rent_growth=[0.04] * 10, appreciation=[0.05] * 10, down_payment_pct=0.3))
    assert b.irr_before_tax == pytest.approx(a.irr_before_tax)
    assert [r.noi for r in b.years] == pytest.approx([r.noi for r in a.years])


def test_growth_vector_applies_each_years_own_rate():
    r = project(deal(rent_growth=[0.0, 0.10] + [0.0] * 8))
    pgr = [row.potential_gross_rent for row in r.years]
    assert pgr[1] == pytest.approx(pgr[0])  # list[0] takes year 1 -> 2
    assert pgr[2] == pytest.approx(pgr[0] * 1.10)  # list[1] takes year 2 -> 3
    assert pgr[3] == pytest.approx(pgr[2])


def test_appreciation_vector_compounds_year_by_year():
    r = project(deal(appreciation=[0.10, -0.10] + [0.0] * 8))
    assert r.years[0].property_value == pytest.approx(550_000)
    assert r.years[1].property_value == pytest.approx(495_000)
    assert r.reversion.exit_value == pytest.approx(495_000)


def test_a_growth_list_shorter_than_the_hold_is_rejected():
    with pytest.raises(ValueError, match="rent_growth"):
        deal(rent_growth=[0.03] * 9)


def test_property_taxes_grow_on_their_own_path():
    r = project(deal(expense_growth=0.0, tax_growth=0.10))
    assert r.years[1].property_taxes == pytest.approx(400 * 12 * 1.10)
    assert r.years[1].common_charges == pytest.approx(500 * 12)


def test_cap_rate_exit_prices_forward_noi_not_the_final_year():
    r = project(deal(rent_growth=0.10, expense_growth=0.0, exit_cap_rate=0.05))
    year_11_pgr = 36_000 * 1.10**10
    year_11_noi = year_11_pgr * 0.95 - 12_000
    assert r.forward_noi == pytest.approx(year_11_noi)
    assert r.reversion.exit_value == pytest.approx(year_11_noi / 0.05)
    assert r.years[-1].property_value is None  # no appreciation path when priced off a cap rate


def test_amortization_is_consistent_interest_is_by_difference():
    r = project(deal(down_payment_pct=0.25, hold_years=10))
    loan = 375_000
    assert sum(y.principal for y in r.years) == pytest.approx(loan - r.years[-1].loan_balance)
    for y in r.years:
        assert y.interest == pytest.approx(y.debt_service - y.principal)
        assert y.interest > 0
    assert r.years[-1].loan_balance == pytest.approx(inv.loan_balance(loan, 0.065, 30, 120))


def test_debt_service_stops_after_the_loan_is_paid_off():
    r = project(deal(down_payment_pct=0.25, hold_years=12, loan_years=10))
    assert r.years[9].loan_balance == pytest.approx(0, abs=1e-6)
    assert r.years[10].debt_service == 0 and r.years[11].interest == pytest.approx(0, abs=1e-6)


def test_no_tax_inputs_means_no_after_tax_figures():
    r = project(deal())
    assert r.after_tax_flows is None and r.irr_after_tax is None
    assert r.reversion.sale_tax is None and r.years[0].income_tax is None


def test_depreciable_basis_is_derived_from_price_costs_and_land():
    r = project(deal(tax=TaxInputs(land_pct=0.20, jurisdiction="US")))
    capitalized = r.purchase_costs["total"] - r.purchase_costs["mortgage_recording_tax"]
    assert r.depreciable_basis == pytest.approx(taxes.depreciable_basis(500_000, capitalized, 0.20))
    assert r.years[0].depreciation == pytest.approx(r.depreciable_basis / 27.5 * 11.5 / 12)
    assert r.years[1].depreciation == pytest.approx(r.depreciable_basis / 27.5)


def test_land_share_is_a_required_tax_input():
    with pytest.raises(TypeError):
        TaxInputs()  # type: ignore[call-arg]


def test_after_tax_year_one_by_hand_federal_only():
    # NOI 22,200, no interest. Basis = (500,000 + 5,250) x 0.8 = 404,200; year-1 depreciation
    # = 404,200 / 27.5 x 11.5/12 = 14,085.5. Taxable = 22,200 - 14,085.5; tax at 32%.
    r = project(deal(tax=TaxInputs(land_pct=0.20, jurisdiction="US")))
    y1 = r.years[0]
    taxable = 22_200 - 404_200 / 27.5 * 11.5 / 12
    assert y1.taxable_income == pytest.approx(taxable)
    assert y1.income_tax == pytest.approx(taxable * 0.32)
    assert y1.after_tax_cash_flow == pytest.approx(22_200 - taxable * 0.32)


def test_after_tax_equity_is_price_less_costs_payoff_and_sale_tax():
    r = project(deal(down_payment_pct=0.25, appreciation=0.05, tax=TaxInputs(land_pct=0.2, jurisdiction="NY:NYC")))
    rev = r.reversion
    assert rev.sale_tax is not None
    assert rev.after_tax_equity == pytest.approx(
        rev.exit_value - rev.selling_costs - rev.loan_payoff - rev.sale_tax.total
    )
    assert rev.sale_tax.recapture_gain == pytest.approx(sum(y.depreciation for y in r.years))
    assert r.after_tax_flows is not None and r.irr_after_tax is not None
    assert r.irr_after_tax < r.irr_before_tax  # tax on a profitable deal always costs return


def test_default_election_suspends_losses_and_releases_them_on_sale():
    # Heavily leveraged with high costs: interest + depreciation exceed NOI, so a loss arises.
    r = project(
        deal(
            monthly_rent=2_000, down_payment_pct=0.2, tax=TaxInputs(land_pct=0.2, jurisdiction="US"), appreciation=0.05
        )
    )
    y1 = r.years[0]
    assert y1.taxable_income == 0 and y1.income_tax == 0  # suspended, not deducted
    assert y1.suspended_loss_balance > 0
    assert r.reversion.sale_tax.suspended_released == pytest.approx(r.years[-1].suspended_loss_balance)


def test_real_estate_professional_deducts_the_loss_currently():
    tax = TaxInputs(land_pct=0.2, jurisdiction="US", election=taxes.LossElection.REAL_ESTATE_PROFESSIONAL)
    r = project(deal(monthly_rent=2_000, down_payment_pct=0.2, tax=tax))
    assert r.years[0].income_tax < 0  # a saving
    assert r.years[0].suspended_loss_balance == 0


def test_invalid_inputs_are_rejected():
    for kw in ({"hold_years": 0}, {"down_payment_pct": 1.2}, {"vacancy_pct": -0.1}, {"exit_cap_rate": 0}):
        with pytest.raises(ValueError):
            deal(**kw)
    with pytest.raises(ValueError):
        ProFormaInputs(price=0, monthly_rent=1)


def test_result_serializes_to_a_plain_dict():
    d = project(deal(tax=TaxInputs(land_pct=0.2))).to_dict()
    assert len(d["years"]) == 10 and d["reversion"]["sale_tax"]["total"] is not None
    assert proforma.project is project
