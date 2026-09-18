import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Neighborhood, NeighborhoodMetric, NeighborhoodScore
from app.scoring import investment as inv
from app.services import MarketContext, property_inputs
from app.valuation import engine
from app.valuation.factors import FACTOR_DEFS, FactorEstimate, PropertyProfile, market_estimate

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


def test_engine_wires_a_backed_factor_into_assumptions_and_delegates_math(monkeypatch):
    """Prove two things at once, with a factor that isn't just echoed back: (1) a FactorDef estimate
    actually reaches Assumptions, and (2) engine.run's numbers exactly match a direct inv.analyze()
    call with that same Assumptions - i.e. engine.py delegates rather than reimplementing the math.
    A stub that only re-derives the engine's own output (as a bare appreciation round-trip would)
    can't catch divergence; this stubs a *different* factor to an arbitrary, independently-known value."""
    session = make_session(with_market_data=False)
    ctx = MarketContext.load(session)
    profile = PropertyProfile(price=1_000_000, nta_code="MN0101", sqft=800, bedrooms=2, rent_estimate=4000)

    stub = FactorEstimate(
        key="vacancy_pct", label="Vacancy rate", value=0.11, p10=0.09, p90=0.13, source="stub", as_of="test"
    )
    real_estimates = market_estimate(ctx, profile)
    monkeypatch.setattr(engine, "market_estimate", lambda c, p: {**real_estimates, "vacancy_pct": stub})

    result = engine.run(profile, ctx)
    assert result["assumptions"]["vacancy_pct"] == 0.11
    assert "vacancy_pct" not in result["estimated_factors"]  # now backed, by the stub
    assert "interest_rate" in result["estimated_factors"]  # still not backed

    direct = inv.analyze(property_inputs(profile, ctx), inv.Assumptions(vacancy_pct=0.11))
    assert result["cap_rate"] == direct["cap_rate"]
    assert result["monthly"] == direct["monthly"]
    assert result["projections"] == direct["projections"]


def test_appreciation_value_matches_hand_computed_base_appreciation():
    session = make_session(with_market_data=True)
    ctx = MarketContext.load(session)
    est = market_estimate(ctx, PropertyProfile(price=1_000_000, nta_code="MN0101"))["appreciation_override"]
    # city_value_cagr_10y = median([0.05]) = 0.05; neighborhood zhvi_cagr_10y = 0.05 (0 spread from
    # city); growth_score=65 tilts +((65-50)/50*0.01) = +0.003 -> 0.05 + 0 + 0.003 = 0.053
    assert est.value == pytest.approx(0.053, abs=1e-9)
    assert "neighborhood" in est.source.lower()


def test_appreciation_source_is_honest_when_only_citywide_data_backs_it():
    """A neighborhood with no zhvi_cagr_10y row of its own still gets an appreciation estimate (the
    citywide median is real data), but the source string must say so - not claim a neighborhood
    component that isn't there."""
    engine_ = create_engine("sqlite://")
    Base.metadata.create_all(engine_)
    session = sessionmaker(bind=engine_)()
    session.add(
        Neighborhood(code="MN0101", name="A", borough="Manhattan", residential=True, geometry=SQUARE, area_km2=4)
    )
    session.add(
        Neighborhood(code="MN0102", name="B", borough="Manhattan", residential=True, geometry=SQUARE, area_km2=4)
    )
    session.add(
        NeighborhoodMetric(nta_code="MN0102", metric="zhvi_cagr_10y", value=0.05, source="zillow", as_of="2025")
    )
    session.commit()

    ctx = MarketContext.load(session)
    est = market_estimate(ctx, PropertyProfile(price=1_000_000, nta_code="MN0101"))["appreciation_override"]
    assert est is not None
    assert "citywide median only" in est.source
    assert "no neighborhood-specific data" in est.source


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


def test_override_wins_in_assumptions_but_the_factor_stays_a_reported_gap():
    """A caller-supplied value should win over the (missing) market estimate, but the factor is
    still not backed by any real data source - overriding it doesn't make it any less of a gap for
    `research-gaps` to report. (Regression test: this used to silently drop the factor from
    estimated_factors the moment it was overridden, which hid real gaps - e.g. interest_rate,
    which the UI always sends a value for - from the "no live source" UI badge.)"""
    session = make_session(with_market_data=True)
    ctx = MarketContext.load(session)
    result = engine.run(PropertyProfile(price=1_000_000, nta_code="MN0101"), ctx, overrides={"interest_rate": 0.08})
    assert result["assumptions"]["interest_rate"] == 0.08
    assert "interest_rate" in result["estimated_factors"]


def test_unknown_override_key_is_rejected():
    session = make_session(with_market_data=True)
    ctx = MarketContext.load(session)
    with pytest.raises(engine.UnknownOverrideError):
        engine.run(PropertyProfile(price=1_000_000, nta_code="MN0101"), ctx, overrides={"not_a_real_field": 1.0})


def test_all_factor_defs_map_to_a_real_assumptions_field():
    valid = set(inv.Assumptions.__dataclass_fields__)
    for f in FACTOR_DEFS:
        assert f.key in valid, f"FactorDef {f.key!r} doesn't match an Assumptions field"
