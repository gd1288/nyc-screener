"""Scenarios in deal mode: what the Stress test tab reads once it runs on the full pro forma."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Neighborhood, NeighborhoodMetric, NeighborhoodScore
from app.services import MarketContext
from app.valuation import engine, scenarios
from app.valuation.engine import DealOptions
from app.valuation.factors import PropertyProfile
from app.valuation.proforma import TaxInputs

SQUARE = {
    "type": "Polygon",
    "coordinates": [[[-74.02, 40.70], [-74.00, 40.70], [-74.00, 40.72], [-74.02, 40.72], [-74.02, 40.70]]],
}
PROFILE = PropertyProfile(price=1_000_000, nta_code="MN0101", sqft=800, bedrooms=2, rent_estimate=4200)
NO_MGMT = {"management_pct": 0.0}  # the one deliberate difference between the two models
TAXED = DealOptions(tax=TaxInputs(land_pct=0.2, jurisdiction="US"))


@pytest.fixture
def ctx():
    engine_ = create_engine("sqlite://")
    Base.metadata.create_all(engine_)
    session = sessionmaker(bind=engine_)()
    session.add(
        Neighborhood(code="MN0101", name="Test", borough="Manhattan", residential=True, geometry=SQUARE, area_km2=4)
    )
    session.add(NeighborhoodScore(nta_code="MN0101", score=65, rank=1, pillars={}, coverage=1.0))
    session.add(NeighborhoodMetric(nta_code="MN0101", metric="zhvi_cagr_10y", value=0.05, source="zillow", as_of="2025"))
    session.add(NeighborhoodMetric(nta_code="MN0101", metric="zori_rent", value=3500, source="zillow", as_of="2025"))
    session.commit()
    return MarketContext.load(session)


def by_name(results):
    return {r.name: r for r in results}


def test_compare_deal_base_case_matches_quick_when_models_share_assumptions(ctx):
    quick = by_name(scenarios.compare(PROFILE, ctx, NO_MGMT))["Base"]
    deal = by_name(scenarios.compare(PROFILE, ctx, NO_MGMT, mode="deal"))["Base"]
    assert deal.irr_10 == pytest.approx(quick.irr_10, abs=1e-4)
    assert deal.irr_20 == pytest.approx(quick.irr_20, abs=1e-4)
    assert deal.equity_multiple_10 == pytest.approx(quick.equity_multiple_10, abs=0.01)


def test_compare_deal_presets_still_rank_bear_below_base_below_bull(ctx):
    r = by_name(scenarios.compare(PROFILE, ctx, {}, mode="deal"))
    assert r["Bear"].irr_10 < r["Base"].irr_10 < r["Bull"].irr_10


def test_quick_results_keep_their_shape_and_leave_deal_fields_empty(ctx):
    r = scenarios.compare(PROFILE, ctx, {})[0]
    assert r.after_tax is None and r.npv_10 is None and r.deal_set == {}


def test_deal_results_carry_the_extra_headline_numbers(ctx):
    r = by_name(scenarios.compare(PROFILE, ctx, {}, mode="deal", deal=TAXED))["Base"]
    assert r.after_tax is True
    assert r.npv_10 is not None and r.dcr_year1 is not None and r.break_even_ratio_year1 is not None


def test_set_applies_absolute_deal_inputs_to_that_scenario_only(ctx):
    rows = [
        {"name": "Base", "deltas": {}},
        {"name": "Cap expansion", "deltas": {}, "set": {"exit_cap_spread": 0.02}},
    ]
    r = by_name(scenarios.compare(PROFILE, ctx, {}, rows, mode="deal", deal=DealOptions(exit_cap_spread=0.0)))
    assert r["Cap expansion"].irr_10 < r["Base"].irr_10
    assert r["Cap expansion"].deal_set == {"exit_cap_spread": 0.02} and r["Base"].deal_set == {}


def test_a_tax_law_scenario_moves_after_tax_return(ctx):
    rows = [
        {"name": "Today", "deltas": {}},
        {"name": "Recapture at ceiling", "deltas": {}, "set": {"recapture_rate": 0.25}},
        {"name": "Recapture cut", "deltas": {}, "set": {"recapture_rate": 0.10}},
    ]
    r = by_name(scenarios.compare(PROFILE, ctx, {}, rows, mode="deal", deal=TAXED))
    assert r["Recapture cut"].irr_10 > r["Today"].irr_10 >= r["Recapture at ceiling"].irr_10


def test_a_mixed_condition_and_event_scenario_runs(ctx):
    rows = [{"name": "Recession + cap shock", "deltas": {"rent_growth": -0.02, "vacancy_pct": 0.05}, "set": {"exit_cap_spread": 0.02}}]
    (r,) = scenarios.compare(PROFILE, ctx, {}, rows, mode="deal")
    assert r.assumptions["vacancy_pct"] == pytest.approx(0.10)
    assert r.deal_set == {"exit_cap_spread": 0.02}
    assert r.npv_10 < 0 and r.dcr_year1 < 1  # a deep-loss case may have no solvable IRR; NPV still reports it


def test_compare_rejects_misuse(ctx):
    with pytest.raises(ValueError, match="mode is 'quick'"):
        scenarios.compare(PROFILE, ctx, {}, [{"name": "x", "set": {"exit_cap_spread": 0.01}}])
    with pytest.raises(engine.UnknownOverrideError):
        scenarios.compare(PROFILE, ctx, {}, [{"name": "x", "set": {"bogus": 1}}], mode="deal")
    with pytest.raises(ValueError, match="mode='deal'"):
        scenarios.compare(PROFILE, ctx, {}, deal=DealOptions())
    with pytest.raises(ValueError, match="Unknown mode"):
        scenarios.compare(PROFILE, ctx, {}, mode="turbo")


def test_sensitivity_deal_mode_adds_an_exit_cap_row_only_when_the_deal_uses_one(ctx):
    quick = scenarios.sensitivity(PROFILE, ctx, {})
    plain = scenarios.sensitivity(PROFILE, ctx, {}, mode="deal")
    capped = scenarios.sensitivity(PROFILE, ctx, {}, mode="deal", deal=DealOptions(exit_cap_spread=0.0))
    explicit = scenarios.sensitivity(PROFILE, ctx, {}, mode="deal", deal=DealOptions(exit_cap_rate=0.05))
    assert len(quick) == len(plain) == 6
    assert "exit_cap_spread" in {r["factor"] for r in capped} and len(capped) == 7
    assert {r["factor"] for r in explicit} >= {"exit_cap_rate"} and "exit_cap_spread" not in {r["factor"] for r in explicit}
    swings = [r["swing"] for r in capped if r["swing"] is not None]
    assert swings == sorted(swings, reverse=True)


def test_data_table_deal_mode_can_grid_a_deal_input(ctx):
    t = scenarios.data_table(
        PROFILE, ctx, {}, "interest_rate", "exit_cap_spread", [0.05, 0.07], [0.0, 0.01, 0.02],
        mode="deal", deal=DealOptions(exit_cap_spread=0.0),
    )  # fmt: skip
    grid = t["irr_grid"]
    assert len(grid) == 3 and all(len(row) == 2 for row in grid)
    assert grid[0][0] > grid[2][0] and grid[0][0] > grid[0][1]  # wider exit cap and higher rate both hurt


def test_data_table_rejects_deal_inputs_in_quick_mode(ctx):
    with pytest.raises(engine.UnknownOverrideError):
        scenarios.data_table(PROFILE, ctx, {}, "interest_rate", "exit_cap_spread", [0.06], [0.0])


def test_monte_carlo_deal_mode_is_deterministic_given_a_seed(ctx):
    a = scenarios.monte_carlo(PROFILE, ctx, {}, n=100, seed=7, mode="deal")
    b = scenarios.monte_carlo(PROFILE, ctx, {}, n=100, seed=7, mode="deal")
    assert a == b and a["valid_n"] > 0 and a["p10"] <= a["p50"] <= a["p90"]
