import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Neighborhood, NeighborhoodMetric, NeighborhoodScore
from app.services import MarketContext
from app.valuation import engine, scenarios
from app.valuation.factors import PropertyProfile

SQUARE = {
    "type": "Polygon",
    "coordinates": [[[-74.02, 40.70], [-74.00, 40.70], [-74.00, 40.72], [-74.02, 40.72], [-74.02, 40.70]]],
}


def make_session():
    engine_ = create_engine("sqlite://")
    Base.metadata.create_all(engine_)
    session = sessionmaker(bind=engine_)()
    session.add(
        Neighborhood(code="MN0101", name="Test", borough="Manhattan", residential=True, geometry=SQUARE, area_km2=4)
    )
    session.add(NeighborhoodScore(nta_code="MN0101", score=65, rank=1, pillars={}, coverage=1.0))
    session.add(
        NeighborhoodMetric(nta_code="MN0101", metric="zhvi_cagr_10y", value=0.05, source="zillow", as_of="2025")
    )
    session.add(NeighborhoodMetric(nta_code="MN0101", metric="zori_rent", value=3500, source="zillow", as_of="2025"))
    session.commit()
    return session


def profile():
    return PropertyProfile(price=1_000_000, nta_code="MN0101", sqft=800, bedrooms=2, rent_estimate=4200)


def test_compare_presets_rank_bear_below_base_below_bull_on_appreciation_only():
    """Bear/Base/Bull only vary appreciation - a factor everything else holds fixed for, so cap rate
    and monthly cash flow must be identical across the three and only IRR/equity move."""
    session = make_session()
    ctx = MarketContext.load(session)
    results = {r.name: r for r in scenarios.compare(profile(), ctx, {})}
    assert results["Bear"].cap_rate == results["Base"].cap_rate == results["Bull"].cap_rate
    assert results["Bear"].monthly_cash_flow == results["Base"].monthly_cash_flow == results["Bull"].monthly_cash_flow
    assert results["Bear"].irr_10 < results["Base"].irr_10 < results["Bull"].irr_10
    assert results["Bear"].assumptions["appreciation_override"] < results["Base"].assumptions["appreciation_override"]


def test_compare_higher_rates_preset_only_moves_the_rate():
    session = make_session()
    ctx = MarketContext.load(session)
    results = {r.name: r for r in scenarios.compare(profile(), ctx, {})}
    base, higher = results["Base"], results["Higher rates"]
    assert higher.assumptions["interest_rate"] == pytest.approx(base.assumptions["interest_rate"] + 0.015)
    assert higher.assumptions["rent_growth"] == base.assumptions["rent_growth"]
    # A higher rate with the same everything else must not improve cash flow.
    assert higher.monthly_cash_flow <= base.monthly_cash_flow


def test_compare_respects_caller_overrides_as_the_baseline():
    """A caller override (e.g. from Quick Mode's sliders) should shift every preset, not just Base -
    presets are deltas *relative to* the resolved baseline, not fixed absolute values."""
    session = make_session()
    ctx = MarketContext.load(session)
    default_base = next(r for r in scenarios.compare(profile(), ctx, {}) if r.name == "Base")
    overridden_base = next(r for r in scenarios.compare(profile(), ctx, {"interest_rate": 0.09}) if r.name == "Base")
    assert overridden_base.assumptions["interest_rate"] == 0.09
    assert overridden_base.monthly_cash_flow < default_base.monthly_cash_flow


def test_compare_rejects_unknown_delta_key():
    session = make_session()
    ctx = MarketContext.load(session)
    with pytest.raises(engine.UnknownOverrideError):
        scenarios.compare(profile(), ctx, {}, [{"name": "Bad", "deltas": {"not_a_field": 1.0}}])


def test_sensitivity_is_ranked_by_swing_descending():
    session = make_session()
    ctx = MarketContext.load(session)
    rows = scenarios.sensitivity(profile(), ctx, {})
    swings = [r["swing"] for r in rows]
    assert swings == sorted(swings, reverse=True)
    # Every configured factor must come back - an `==` check, not a subset one. A subset assertion
    # passes silently when rows get dropped, which is exactly how a one-bar tornado shipped once.
    assert {r["factor"] for r in rows} == set(scenarios.SENSITIVITY_SWINGS)


def test_sensitivity_reports_unsolvable_factors_instead_of_dropping_them():
    """A factor whose IRR can't be solved at either end still gets a row (with nulls); dropping it
    silently makes the tornado claim the remaining factors are all that matter."""
    session = make_session()
    ctx = MarketContext.load(session)
    hopeless = {
        "appreciation_override": -0.02,
        "down_payment_pct": 0.05,
        "exit_cost_pct": 0.15,
        "interest_rate": 0.10,
        "vacancy_pct": 0.15,
        "rent_growth": 0.0,
        "expense_growth": 0.06,
    }
    rows = scenarios.sensitivity(profile(), ctx, hopeless)
    assert {r["factor"] for r in rows} == set(scenarios.SENSITIVITY_SWINGS)
    for r in rows:
        if r["undefined"]:
            assert r["swing"] is None and (r["low_irr"] is None or r["high_irr"] is None)


def test_swung_ranges_are_recentred_on_caller_overrides_not_the_raw_market_estimate():
    """With an appreciation override, the tornado bar must bracket the base case the user is
    looking at - otherwise the Results strip shows an IRR that sits outside its own bar."""
    session = make_session()
    ctx = MarketContext.load(session)
    row = {r["factor"]: r for r in scenarios.sensitivity(profile(), ctx, {"appreciation_override": 0.08})}[
        "appreciation_override"
    ]
    assert row["low_irr"] <= row["base_irr"] <= row["high_irr"]
    assert row["low_value"] < 0.08 < row["high_value"]


def test_monte_carlo_distribution_moves_with_a_caller_override():
    session = make_session()
    ctx = MarketContext.load(session)
    high = scenarios.monte_carlo(profile(), ctx, {"appreciation_override": 0.08}, n=200, seed=3)
    low = scenarios.monte_carlo(profile(), ctx, {"appreciation_override": 0.0}, n=200, seed=3)
    assert high["p50"] > low["p50"]


@pytest.mark.parametrize(
    ("factor", "override", "floor"),
    [("down_payment_pct", 0.05, 0.01), ("vacancy_pct", 0.0, 0.0), ("interest_rate", 0.02, 0.005)],
)
def test_swung_ranges_are_clamped_to_a_sane_domain(factor, override, floor):
    """Baseline minus the swing must not run past what the number can mean - a negative down
    payment is a >100% LTV loan with negative cash invested, which reports a fantastic IRR and
    then tops the tornado."""
    session = make_session()
    ctx = MarketContext.load(session)
    row = {r["factor"]: r for r in scenarios.sensitivity(profile(), ctx, {factor: override})}[factor]
    assert row["low_value"] >= floor


def test_sensitivity_marks_appreciation_as_backed_and_rate_as_not():
    session = make_session()
    ctx = MarketContext.load(session)
    rows = {r["factor"]: r for r in scenarios.sensitivity(profile(), ctx, {})}
    assert rows["appreciation_override"]["backed_by_source"] is True
    assert rows["interest_rate"]["backed_by_source"] is False


def test_data_table_shape_matches_requested_axes():
    session = make_session()
    ctx = MarketContext.load(session)
    x_values, y_values = [0.05, 0.065, 0.08], [-0.01, 0.02, 0.05]
    table = scenarios.data_table(profile(), ctx, {}, "interest_rate", "appreciation_override", x_values, y_values)
    assert len(table["irr_grid"]) == len(y_values)
    assert all(len(row) == len(x_values) for row in table["irr_grid"])
    # Higher appreciation (later rows) at the same rate should never produce a worse 10y IRR.
    for col in range(len(x_values)):
        column_irrs = [table["irr_grid"][row][col] for row in range(len(y_values))]
        assert column_irrs == sorted(column_irrs)


def test_data_table_rejects_unknown_factor():
    session = make_session()
    ctx = MarketContext.load(session)
    with pytest.raises(engine.UnknownOverrideError):
        scenarios.data_table(profile(), ctx, {}, "not_a_field", "appreciation_override", [0.05], [0.02])


def test_monte_carlo_is_deterministic_given_a_seed_and_only_randomizes_backed_factors():
    session = make_session()
    ctx = MarketContext.load(session)
    r1 = scenarios.monte_carlo(profile(), ctx, {}, n=200, seed=7)
    r2 = scenarios.monte_carlo(profile(), ctx, {}, n=200, seed=7)
    assert r1 == r2
    assert r1["randomized_factors"] == ["appreciation_override"]  # the only factor with real data in this fixture
    assert "interest_rate" in r1["held_at_default"]
    assert r1["valid_n"] == 200
    assert r1["p10"] <= r1["p50"] <= r1["p90"]


def test_monte_carlo_n_is_capped():
    session = make_session()
    ctx = MarketContext.load(session)
    result = scenarios.monte_carlo(profile(), ctx, {}, n=999_999, seed=1)
    assert result["n"] == scenarios.MAX_MONTE_CARLO_RUNS
