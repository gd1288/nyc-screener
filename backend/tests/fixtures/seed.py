"""Seed a fresh, empty database with just enough data for the app to render — used by CI's
Playwright smoke test (`ci.yml`), not by normal development (real data comes from `app.cli refresh`).

Run with `DATABASE_URL` pointed at a throwaway file, e.g.:
    DATABASE_URL=sqlite:///./data/ci_test.db uv run python -m tests.fixtures.seed
"""

from datetime import datetime

from app.db import Base, SessionLocal, engine
from app.models import Neighborhood, NeighborhoodMetric, NeighborhoodScore

# Two small, deliberately simple polygons — real enough to satisfy geometry fields and render on
# the map, not meant to be geographically accurate.
_MANHATTAN_BOX = {
    "type": "Polygon",
    "coordinates": [[[-74.01, 40.70], [-73.99, 40.70], [-73.99, 40.72], [-74.01, 40.72], [-74.01, 40.70]]],
}
_BROOKLYN_BOX = {
    "type": "Polygon",
    "coordinates": [[[-73.99, 40.68], [-73.97, 40.68], [-73.97, 40.70], [-73.99, 40.70], [-73.99, 40.68]]],
}

NEIGHBORHOODS = [
    dict(code="MN0101", name="Test Financial District", borough="Manhattan", area_km2=1.2, geometry=_MANHATTAN_BOX),
    dict(code="BK0101", name="Test Williamsburg", borough="Brooklyn", area_km2=2.1, geometry=_BROOKLYN_BOX),
]


def seed() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        if session.query(Neighborhood).count() > 0:
            print("seed: database already has neighborhoods, skipping (not touching real data)")
            return
        for n in NEIGHBORHOODS:
            session.add(Neighborhood(**n))
        session.flush()
        for i, n in enumerate(NEIGHBORHOODS):
            session.add(
                NeighborhoodScore(
                    nta_code=n["code"],
                    score=80.0 - i * 10,
                    rank=i + 1,
                    pillars={"growth": {"score": 75.0, "metrics": {}}, "value": {"score": 70.0, "metrics": {}}},
                    coverage=1.0,
                    computed_at=datetime.now(),
                )
            )
            # The neighborhoods page defaults to "active condo markets only" (>=10 condo sales/yr);
            # without this metric these seeded rows would be hidden by that default filter and the
            # smoke test would see an empty page, not because the app is broken but because the
            # fixture didn't look like a real neighborhood. Give it a value comfortably over 10.
            session.add(
                NeighborhoodMetric(
                    nta_code=n["code"],
                    metric="condo_sales_per_year",
                    value=25.0,
                    source="seed",
                    as_of="test fixture",
                )
            )
        session.commit()
    print(f"seed: wrote {len(NEIGHBORHOODS)} neighborhoods + scores")


if __name__ == "__main__":
    seed()
