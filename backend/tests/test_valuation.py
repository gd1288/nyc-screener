from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Neighborhood, NeighborhoodMetric, NeighborhoodScore
from app.scoring import investment as inv
from app.services import MarketContext, property_inputs
from app.valuation import engine
from app.valuation.factors import FACTOR_DEFS, PropertyProfile, market_estimate

SQUARE = {
    "type": "Polygon",
    "coordinates": [[[-74.02, 40.70], [-74.00, 40.70], [-74.00, 40.72], [-74.02, 40.72], [-74.02, 40.70]]],
}


def make_session(with_market_data: bool):
    engine_ = create_engine("sqlite://")
    Base.metadata.create_all(engine_)
    session = sessionmaker(bind=engine_)()
    session.add(
        Neighborhood(code="MN0101", name="Test", borough="Manhattan", residential=True, geometry=SQUARE, area_km2=4)
    )
    if with_market_data:
        session.add(NeighborhoodScore(nta_code="MN0101", score=65, rank=1, pillars={}, coverage=1.0))
        session.add(
            NeighborhoodMetric(nta_code="MN0101", metric="zhvi_cagr_10y", value=0.05, source="zillow", as_of="2025")
        )
        session.add(
            NeighborhoodMetric(nta_code="MN0101", metric="zori_rent", value=3500, source="zillow", as_of="2025")
        )
    session.commit()
    return session


def test_engine_matches_investment_analyze_for_same_inputs():
    """The valuation engine must delegate to investment.analyze, not reimplement it - otherwise the
    screener's Opportunity Score and a valuation run could disagree about the same property."""
    session = make_session(with_market_data=True)
    ctx = MarketContext.load(session)
    profile = PropertyProfile(price=1_000_000, nta_code="MN0101", sqft=800, bedrooms=2)

    result = engine.run(profile, ctx)
    direct = inv.analyze(
        property_inputs(profile, ctx), inv.Assumptions(appreciation_override=result["appreciation"]["base"])
    )

    assert result["cap_rate"] == direct["cap_rate"]
    assert result["gross_yield"] == direct["gross_yield"]
    assert result["projections"] == direct["projections"]


def test_appreciation_factor_backed_by_zillow_data():
    session = make_session(with_market_data=True)
    ctx = MarketContext.load(session)
    estimates = market_estimate(ctx, PropertyProfile(price=1_000_000, nta_code="MN0101"))
    assert estimates["appreciation_override"] is not None
    assert "Zillow" in estimates["appreciation_override"].source
    assert (
        estimates["appreciation_override"].p10
        < estimates["appreciation_override"].value
        < estimates["appreciation_override"].p90
    )


def test_factors_with_no_source_are_reported_as_gaps():
    session = make_session(with_market_data=False)
    ctx = MarketContext.load(session)
    estimates = market_estimate(ctx, PropertyProfile(price=1_000_000, nta_code="MN0101"))
    gap_keys = {k for k, v in estimates.items() if v is None}
    assert gap_keys == {"interest_rate", "rent_growth", "vacancy_pct", "expense_growth", "appreciation_override"}


def test_run_records_estimated_factors_and_falls_back_to_assumption_defaults():
    session = make_session(with_market_data=False)
    ctx = MarketContext.load(session)
    result = engine.run(PropertyProfile(price=1_000_000, nta_code="MN0101"), ctx)
    assert set(result["estimated_factors"]) == {
        "interest_rate",
        "rent_growth",
        "vacancy_pct",
        "expense_growth",
        "appreciation_override",
    }
    assert result["assumptions"]["interest_rate"] == inv.Assumptions().interest_rate


def test_override_clears_the_estimated_flag_and_wins_over_market_estimate():
    session = make_session(with_market_data=True)
    ctx = MarketContext.load(session)
    result = engine.run(PropertyProfile(price=1_000_000, nta_code="MN0101"), ctx, overrides={"interest_rate": 0.08})
    assert result["assumptions"]["interest_rate"] == 0.08
    assert "interest_rate" not in result["estimated_factors"]


def test_all_factor_defs_map_to_a_real_assumptions_field():
    valid = set(inv.Assumptions.__dataclass_fields__)
    for f in FACTOR_DEFS:
        assert f.key in valid, f"FactorDef {f.key!r} doesn't match an Assumptions field"
