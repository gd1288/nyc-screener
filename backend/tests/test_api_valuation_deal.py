"""The valuation API's deal mode: opt-in, validated, and additive to the quick-mode responses."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import valuation as valuation_api
from app.db import Base
from app.main import app
from app.models import Neighborhood, ValuationProperty

SQUARE = {
    "type": "Polygon",
    "coordinates": [[[-74.02, 40.70], [-74.00, 40.70], [-74.00, 40.72], [-74.02, 40.72], [-74.02, 40.70]]],
}
BASE = "/api/valuation/properties/1"
TAX = {"land_pct": 0.2, "jurisdiction": "US"}


@pytest.fixture
def client():
    db_engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(db_engine)
    Session = sessionmaker(bind=db_engine)
    with Session() as session:
        session.add(
            Neighborhood(code="MN0101", name="Test", borough="Manhattan", residential=True, geometry=SQUARE, area_km2=4)
        )
        session.add(
            ValuationProperty(label="Flat", property_type="condo", nta_code="MN0101", price=1_000_000, rent_estimate=4_200)
        )
        session.commit()
    app.dependency_overrides[valuation_api.db] = lambda: Session()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_run_defaults_to_quick_mode_with_no_deal_block(client):
    body = client.post(f"{BASE}/run", json={}).json()
    assert "deal" not in body and "projections" in body


def test_run_deal_mode_adds_the_pro_forma_and_keeps_the_quick_keys(client):
    quick = client.post(f"{BASE}/run", json={}).json()
    r = client.post(f"{BASE}/run", json={"mode": "deal", "deal": {"tax": TAX}})
    assert r.status_code == 200
    body = r.json()
    assert {k: v for k, v in body.items() if k != "deal"} == quick
    assert body["deal"]["headline"]["after_tax"] is True
    assert len(body["deal"]["proforma"]["years"]) == 10
    assert body["deal"]["proforma"]["reversion"]["sale_tax"]["total"] is not None  # serializes cleanly


def test_run_hold_years_sets_the_pro_forma_length(client):
    body = client.post(f"{BASE}/run", json={"mode": "deal", "deal": {"hold_years": 15}}).json()
    assert len(body["deal"]["proforma"]["years"]) == 15


def test_deal_inputs_without_deal_mode_are_rejected_not_ignored(client):
    r = client.post(f"{BASE}/run", json={"deal": {"hold_years": 5}})
    assert r.status_code == 422 and "mode='deal'" in r.json()["detail"]


@pytest.mark.parametrize(
    "deal",
    [
        {"tax": {"land_pct": 1.0}},  # land can't be 100% of the basis
        {"tax": {"land_pct": 0.2, "placed_in_service_month": 13}},
        {"tax": TAX, "tax_rate_overrides": {"recapture_rate": 0.30}},  # over the statutory ceiling
        {"tax": TAX, "tax_rate_overrides": {"bogus": 0.1}},
        {"tax_rate_overrides": {"recapture_rate": 0.2}},  # tax rate with no tax inputs
        {"exit_cap_rate": 0},
        {"hold_years": 0},
    ],
)
def test_invalid_deal_inputs_are_422_not_500(client, deal):
    assert client.post(f"{BASE}/run", json={"mode": "deal", "deal": deal}).status_code == 422


def test_unknown_mode_is_rejected(client):
    assert client.post(f"{BASE}/run", json={"mode": "turbo"}).status_code == 422


def test_compare_supports_absolute_set_inputs_in_deal_mode(client):
    rows = [{"name": "Base"}, {"name": "Cap shock", "set": {"exit_cap_spread": 0.02}}]
    r = client.post(
        f"{BASE}/scenarios/compare", json={"mode": "deal", "deal": {"exit_cap_spread": 0.0}, "scenarios": rows}
    )
    assert r.status_code == 200
    base, shock = r.json()
    assert shock["irr_10"] < base["irr_10"] and shock["deal_set"] == {"exit_cap_spread": 0.02}


def test_compare_presets_still_work_in_quick_mode(client):
    r = client.post(f"{BASE}/scenarios/compare", json={})
    assert r.status_code == 200 and [x["name"] for x in r.json()][:2] == ["Bear", "Base"]


def test_compare_rejects_set_in_quick_mode_and_unknown_set_keys(client):
    quick = client.post(f"{BASE}/scenarios/compare", json={"scenarios": [{"name": "x", "set": {"exit_cap_spread": 0.01}}]})
    unknown = client.post(
        f"{BASE}/scenarios/compare", json={"mode": "deal", "scenarios": [{"name": "x", "set": {"bogus": 1}}]}
    )
    assert quick.status_code == 422 and unknown.status_code == 422


def test_sensitivity_deal_mode_includes_the_exit_cap_row(client):
    rows = client.post(
        f"{BASE}/sensitivity", json={"mode": "deal", "deal": {"exit_cap_spread": 0.0}}
    ).json()
    assert "exit_cap_spread" in {r["factor"] for r in rows}
    assert "exit_cap_spread" not in {r["factor"] for r in client.post(f"{BASE}/sensitivity", json={}).json()}


def test_data_table_deal_factor_needs_explicit_values_and_then_works(client):
    payload = {"mode": "deal", "deal": {"exit_cap_spread": 0.0}, "x_factor": "interest_rate", "y_factor": "exit_cap_spread"}
    assert client.post(f"{BASE}/data-table", json=payload).status_code == 422
    r = client.post(f"{BASE}/data-table", json={**payload, "y_values": [0.0, 0.01, 0.02]})
    assert r.status_code == 200
    grid = r.json()["irr_grid"]
    assert len(grid) == 3 and grid[0][2] > grid[2][2]  # a wider exit cap lowers the return


def test_data_table_rejects_deal_factors_in_quick_mode(client):
    r = client.post(f"{BASE}/data-table", json={"y_factor": "exit_cap_spread", "y_values": [0.0, 0.01]})
    assert r.status_code == 422


def test_monte_carlo_deal_mode(client):
    r = client.post(f"{BASE}/monte-carlo", json={"mode": "deal", "n": 100, "seed": 3})
    assert r.status_code == 200 and r.json()["valid_n"] > 0
