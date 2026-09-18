"""`engine.run(mode="deal")`: opt-in, additive, and built from the same resolved inputs as quick mode."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Neighborhood, NeighborhoodMetric, NeighborhoodScore
from app.services import MarketContext
from app.valuation import engine, taxes
from app.valuation.engine import DealOptions
from app.valuation.factors import PropertyProfile
from app.valuation.proforma import TaxInputs

SQUARE = {
    "type": "Polygon",
    "coordinates": [[[-74.02, 40.70], [-74.00, 40.70], [-74.00, 40.72], [-74.02, 40.72], [-74.02, 40.70]]],
}


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


PROFILE = PropertyProfile(price=1_000_000, nta_code="MN0101", sqft=800, bedrooms=2, rent_estimate=4200)


def test_quick_is_the_default_and_has_no_deal_block(ctx):
    assert "deal" not in engine.run(PROFILE, ctx)
    assert engine.run(PROFILE, ctx) == engine.run(PROFILE, ctx, mode="quick")


def test_deal_mode_only_adds_a_key_and_leaves_every_quick_number_alone(ctx):
    quick = engine.run(PROFILE, ctx)
    deal = engine.run(PROFILE, ctx, mode="deal")
    assert {k: v for k, v in deal.items() if k != "deal"} == quick
    assert set(deal["deal"]) == {"headline", "proforma"}


def test_unknown_mode_is_rejected(ctx):
    with pytest.raises(ValueError, match="Unknown mode"):
        engine.run(PROFILE, ctx, mode="turbo")


@pytest.mark.parametrize("hold", [10, 20])
def test_deal_and_quick_agree_when_the_models_share_assumptions(ctx, hold):
    """End-to-end wiring check: resolved rent, costs, appreciation and financing reach the pro forma
    intact. Only management differs by design (share of EGI vs of gross rent), so it is zeroed."""
    result = engine.run(PROFILE, ctx, {"management_pct": 0.0}, mode="deal", deal=DealOptions(hold_years=hold))
    quick = result["projections"]["base"][str(hold)]
    pf = result["deal"]["proforma"]
    assert pf["irr_before_tax"] == pytest.approx(quick["irr"], abs=1e-4)
    assert pf["reversion"]["before_tax_equity"] == pytest.approx(quick["equity_at_exit"], abs=1)
    assert result["deal"]["headline"]["irr"] == pf["irr_before_tax"]  # no tax inputs -> before-tax


def test_resolved_rent_and_costs_flow_into_the_first_year(ctx):
    result = engine.run(PROFILE, ctx, mode="deal")
    y1 = result["deal"]["proforma"]["years"][0]
    assert y1["potential_gross_rent"] == pytest.approx(result["exact"]["rent"] * 12)
    assert y1["common_charges"] == pytest.approx(result["exact"]["common_charges"] * 12)
    assert y1["property_taxes"] == pytest.approx(result["exact"]["property_taxes"] * 12)


def test_overrides_reach_the_pro_forma_and_unknown_ones_still_raise(ctx):
    high = engine.run(PROFILE, ctx, {"interest_rate": 0.09}, mode="deal")
    low = engine.run(PROFILE, ctx, {"interest_rate": 0.04}, mode="deal")
    assert high["deal"]["proforma"]["years"][0]["debt_service"] > low["deal"]["proforma"]["years"][0]["debt_service"]
    with pytest.raises(engine.UnknownOverrideError):
        engine.run(PROFILE, ctx, {"nope": 1}, mode="deal")


def test_headline_irr_is_after_tax_when_tax_inputs_are_given(ctx):
    opts = DealOptions(tax=TaxInputs(land_pct=0.2, jurisdiction="NY:NYC"))
    h = engine.run(PROFILE, ctx, mode="deal", deal=opts)["deal"]["headline"]
    assert h["after_tax"] is True and h["irr"] == h["irr_after_tax"]
    assert h["irr_after_tax"] < h["irr_before_tax"]
    plain = engine.run(PROFILE, ctx, mode="deal")["deal"]["headline"]
    assert plain["after_tax"] is False and plain["irr_after_tax"] is None


def test_tax_rate_overrides_change_the_result_and_respect_statutory_ceilings(ctx):
    base = DealOptions(tax=TaxInputs(land_pct=0.2, jurisdiction="US"))
    low = engine.run(PROFILE, ctx, mode="deal", deal=base.with_set({"recapture_rate": 0.10}))
    high = engine.run(PROFILE, ctx, mode="deal", deal=base.with_set({"recapture_rate": 0.25}))
    assert low["deal"]["headline"]["irr_after_tax"] > high["deal"]["headline"]["irr_after_tax"]
    with pytest.raises(taxes.RateOutOfRangeError):
        engine.run(PROFILE, ctx, mode="deal", deal=base.with_set({"recapture_rate": 0.30}))


def test_with_set_rejects_unknown_keys_and_tax_rates_without_tax_inputs():
    with pytest.raises(engine.UnknownOverrideError):
        DealOptions().with_set({"bogus": 1})
    with pytest.raises(ValueError, match="no tax inputs"):
        DealOptions().with_set({"recapture_rate": 0.2})
    assert DealOptions().with_set({"hold_years": 15.0}).hold_years == 15


def test_exit_cap_spread_lowers_the_return(ctx):
    flat = engine.run(PROFILE, ctx, mode="deal", deal=DealOptions(exit_cap_spread=0.0))
    wide = engine.run(PROFILE, ctx, mode="deal", deal=DealOptions(exit_cap_spread=0.015))
    assert wide["deal"]["headline"]["irr"] < flat["deal"]["headline"]["irr"]
    assert wide["deal"]["headline"]["exit_cap_rate"] == pytest.approx(flat["deal"]["headline"]["exit_cap_rate"] + 0.015)
