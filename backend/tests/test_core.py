from datetime import date, timedelta

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.geo import NeighborhoodIndex
from app.models import Listing, ListingStatus, Neighborhood
from app.pipeline.geocode import normalize_unit
from app.pipeline.listings import RawListing, expire_stale_off_market, mark_sold, sync_listings
from app.scoring import investment as inv
from app.scoring.neighborhood import score_frame

SQUARE = {"type": "Polygon", "coordinates": [[[-74.02, 40.70], [-74.00, 40.70], [-74.00, 40.72], [-74.02, 40.72], [-74.02, 40.70]]]}


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        s.add(Neighborhood(code="MN0101", name="Test", borough="Manhattan", residential=True, geometry=SQUARE, area_km2=4))
        s.commit()
        yield s


def raw(price=1_000_000, ext="a", **kw):
    return RawListing(external_id=ext, address="1 Test St", unit="12A", price=price, listed_date=date(2026, 1, 1),
                      latitude=40.71, longitude=-74.01, **kw)


def test_lifecycle_new_price_cut_off_market_relist_sold(session):
    geo = NeighborhoodIndex.load(session)
    stats = sync_listings(session, "src", [raw()], complete=True, geo=geo)
    listing = session.query(Listing).one()
    assert stats.new == 1 and listing.nta_code == "MN0101" and listing.status == ListingStatus.ACTIVE

    sync_listings(session, "src", [raw(price=950_000)], complete=True, geo=geo)
    assert listing.price == 950_000 and listing.original_price == 1_000_000
    assert [s.event for s in listing.snapshots] == ["listed", "price_change"]

    sync_listings(session, "src", [], complete=True, geo=geo)
    assert listing.status == ListingStatus.ACTIVE  # one miss is tolerated
    sync_listings(session, "src", [], complete=True, geo=geo)
    assert listing.status == ListingStatus.OFF_MARKET

    sync_listings(session, "src", [raw(price=950_000)], complete=True, geo=geo)
    assert listing.status == ListingStatus.ACTIVE and listing.snapshots[-1].event == "relisted"

    mark_sold(listing, 925_000, date(2026, 3, 1), "DOC1")
    session.commit()
    assert listing.status == ListingStatus.SOLD and listing.sold_price == 925_000


def test_incomplete_fetch_never_marks_off_market(session):
    geo = NeighborhoodIndex.load(session)
    sync_listings(session, "src", [raw()], complete=False, geo=geo)
    for _ in range(3):
        sync_listings(session, "src", [], complete=False, geo=geo)
    assert session.query(Listing).one().status == ListingStatus.ACTIVE


def test_stale_off_market_becomes_withdrawn(session):
    geo = NeighborhoodIndex.load(session)
    sync_listings(session, "src", [raw()], complete=True, geo=geo)
    listing = session.query(Listing).one()
    listing.status, listing.off_market_date = ListingStatus.OFF_MARKET, date.today() - timedelta(days=120)
    session.commit()
    assert expire_stale_off_market(session) == 1 and listing.status == ListingStatus.WITHDRAWN


def test_price_history_seeds_original_price(session):
    geo = NeighborhoodIndex.load(session)
    sync_listings(session, "src", [raw(price=900_000, price_history=[(date(2026, 1, 1), 1_000_000)])],
                  complete=False, geo=geo)
    listing = session.query(Listing).one()
    assert listing.original_price == 1_000_000
    assert [s.event for s in listing.snapshots] == ["listed", "price_change"]


@pytest.mark.parametrize("given,expected", [("#12A", "12A"), ("Apt 12a", "12A"), ("Unit PH-1", "PH-1"), ("", None)])
def test_normalize_unit(given, expected):
    assert normalize_unit(given) == expected


def test_mortgage_payment_matches_standard_amortization():
    # $750k at 6.5% over 30 years -> $4,740.51/month (standard amortization table)
    assert inv.monthly_payment(750_000, 0.065, 30) == pytest.approx(4740.51, abs=0.01)
    assert inv.loan_balance(750_000, 0.065, 30, 360) == pytest.approx(0, abs=1)


def test_nyc_purchase_costs():
    a = inv.Assumptions()
    costs = inv.purchase_costs(2_500_000, 1_875_000, a)
    assert costs["mansion_tax"] == pytest.approx(25_000)  # 1% at $2-3M
    assert costs["mortgage_recording_tax"] == pytest.approx(1_875_000 * 0.01925)
    assert "nyc_transfer_tax" not in costs
    assert inv.mansion_tax_rate(999_999) == 0
    new_dev = inv.purchase_costs(2_500_000, 0, inv.Assumptions(new_development=True))
    assert new_dev["nyc_transfer_tax"] == pytest.approx(2_500_000 * 0.01425)
    assert new_dev["mortgage_recording_tax"] == 0


def test_irr_simple_case():
    assert inv.irr([-100, 0, 121]) == pytest.approx(0.10, abs=1e-6)


def test_analyze_all_cash_no_growth_irr_equals_cap_rate_less_exit_drag():
    p = inv.PropertyInputs(price=1_000_000, rent_estimate=5_000, common_charges=800, property_taxes=700)
    a = inv.Assumptions(down_payment_pct=1.0, appreciation_override=0.0, rent_growth=0, expense_growth=0,
                        exit_cost_pct=0, vacancy_pct=0, management_pct=0, maintenance_monthly=0, insurance_monthly=0)
    result = inv.analyze(p, a)
    assert result["monthly"]["noi"] == 3_500
    assert result["cap_rate"] == pytest.approx(0.042)
    # With no appreciation or exit costs, IRR is the NOI yield on total cash (price + closing costs).
    cash = result["cash_invested"]
    assert result["projections"]["base"]["10"]["irr"] == pytest.approx(42_000 / cash, abs=2e-3)


def test_opportunity_score_requires_growth_and_reweights():
    assert inv.opportunity_score(None, 80, 80) is None
    assert inv.opportunity_score(60, None, None) == 60
    assert inv.opportunity_score(60, 100, 20) == pytest.approx(0.5 * 60 + 0.25 * 100 + 0.25 * 20)


def test_score_frame_percentiles_direction_and_missing_pillars():
    idx = [f"N{i}" for i in range(20)]
    wide = pd.DataFrame({
        "residential": True,
        "value_gap_borough": range(20),                   # higher is better
        "felonies_per_1k_units": range(20),               # lower is better
        "floodplain_2050s_pct": [0.0] * 19 + [1.0],
    }, index=idx)
    weights = {"valuation": 50, "quality": 50, "development": 0, "infrastructure": 0, "demographics": 0,
               "momentum": 0, "commercial": 0, "flood_risk_penalty": 10}
    out = score_frame(wide, weights)
    assert out.loc["N19", "pillars"]["valuation"]["score"] == 100
    assert out.loc["N19", "pillars"]["quality"]["score"] == 5  # most crime -> lowest percentile
    assert out.loc["N19", "pillars"]["flood_risk_penalty"]["points"] == -10
    assert out.loc["N0", "coverage"] == pytest.approx(1.0)


def test_building_address_key_matches_dof_format():
    from app.services import building_address_key

    assert building_address_key("15 William St") == building_address_key("15 WILLIAM STREET, 27A")
    assert building_address_key("200 E 72nd St") == building_address_key("200 EAST 72 STREET, 5B")
    assert building_address_key("25 Broad Street") != building_address_key("15 WILLIAM STREET")
