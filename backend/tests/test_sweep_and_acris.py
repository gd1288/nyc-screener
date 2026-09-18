"""The stale-listing checks: RentCast update-only sweeps and the ACRIS sold check."""

from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.geo import NeighborhoodIndex
from app.models import Listing, ListingStatus, Neighborhood
from app.pipeline.listings import RawListing, sync_listings
from app.sources import acris
from app.sources.base import SourceContext
from app.sources.rentcast import RentCastListings, scope_ids

SQUARE = {
    "type": "Polygon",
    "coordinates": [[[-74.02, 40.70], [-74.00, 40.70], [-74.00, 40.72], [-74.02, 40.72], [-74.02, 40.70]]],
}
AREA = {"name": "a", "latitude": 40.71, "longitude": -74.01, "radius": 1}


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        s.add(Neighborhood(code="MN0101", name="Test", borough="Manhattan", residential=True, geometry=SQUARE, area_km2=4))
        s.commit()
        yield s


# ------------------------------------------------------------------ RentCast sweep

class _Resp:
    def __init__(self, items, total):
        self.items, self.headers = items, {"X-Total-Count": str(total)}

    def raise_for_status(self):
        pass

    def json(self):
        return self.items


class _Http:
    def __init__(self, ext_ids, total, price=900_000):
        self.ext_ids, self.total, self.price, self.calls = ext_ids, total, price, []

    def get(self, url, params=None, **kw):
        if "geosearch" in url:
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"features": []})
        self.calls.append(params)
        items = [{"id": e, "price": self.price, "addressLine1": "1 Test St", "addressLine2": "Apt 3B", "latitude": 40.71,
                  "longitude": -74.01, "listedDate": "2026-09-10T00:00:00Z"} for e in self.ext_ids]
        return _Resp(items, self.total)


def _ctx(session, http):
    return SourceContext(session=session, settings=SimpleNamespace(rentcast_api_key="k"), http=http)


def _seed(session, ext="rc1"):
    geo = NeighborhoodIndex.load(session)
    sync_listings(session, "rentcast_listings", [RawListing(external_id=ext, address="1 Test St", unit="3B", price=1_000_000,
                  listed_date=date(2026, 9, 1), latitude=40.71, longitude=-74.01)], complete=False, geo=geo)
    return session.query(Listing).one()


def test_sweep_updates_the_tracked_listing_under_the_original_source_name(session):
    """The sweep is a separately named config entry; its results must land on the listings the daily job created."""
    listing = _seed(session)
    src = RentCastListings("rentcast_sweep", mode="full", insert_new=False, page_size=500, areas=[AREA])
    src.run(_ctx(session, _Http(["rc1"], total=1)))
    assert session.query(Listing).count() == 1 and listing.price == 900_000


def test_sweep_never_adds_listings_it_was_not_already_tracking(session):
    _seed(session)
    src = RentCastListings("rentcast_sweep", mode="full", insert_new=False, page_size=500, areas=[AREA])
    src.run(_ctx(session, _Http(["rc1", "brand-new"], total=2)))
    assert session.query(Listing).count() == 1


def test_a_listing_missing_from_two_complete_sweeps_goes_off_market(session):
    listing = _seed(session)
    src = RentCastListings("rentcast_sweep", mode="full", insert_new=False, page_size=500, areas=[AREA], min_hours_between_requests=0)
    src.run(_ctx(session, _Http([], total=0)))
    assert listing.status == ListingStatus.ACTIVE and listing.missed_fetches == 1
    src.run(_ctx(session, _Http([], total=0)))
    assert listing.status == ListingStatus.OFF_MARKET


def test_a_sweep_too_big_for_its_page_budget_stops_after_one_request_and_proves_nothing(session):
    listing = _seed(session)
    http = _Http(["rc1"], total=5_000)
    src = RentCastListings("rentcast_sweep", mode="full", insert_new=False, page_size=1, max_requests_per_run=3, areas=[AREA])
    src.run(_ctx(session, http))
    assert len(http.calls) == 1 and listing.missed_fetches == 0 and listing.status == ListingStatus.ACTIVE


def test_scope_covers_only_listings_inside_the_searched_circle(session):
    _seed(session)
    session.add(Listing(source="rentcast_listings", external_id="far", address="9 Far St", price=1, original_price=1,
                        listed_date=date(2026, 9, 1), latitude=40.65, longitude=-73.95, status=ListingStatus.ACTIVE))
    session.commit()
    assert scope_ids(session, AREA) == {"rc1"}


# ------------------------------------------------------------------ ACRIS sold check

def _listing(session, bbl, unit="3B", listed=date(2026, 8, 21)):
    lst = Listing(source="rentcast_listings", external_id=f"x{bbl}", address="121 W 17th St", unit=unit, bbl=bbl, price=1_695_000,
                  original_price=1_695_000, listed_date=listed, status=ListingStatus.ACTIVE)
    session.add(lst)
    session.commit()
    return lst


def test_likely_coops_are_never_checked_for_a_deed(session, monkeypatch):
    coop = _listing(session, "1007930022")  # ordinary tax lot: no per-unit deed exists
    condo = _listing(session, "1013107501")  # condo billing lot
    checked = []
    monkeypatch.setattr(acris, "find_deed", lambda ctx, listing: checked.append(listing.id))
    acris.AcrisSoldCheck("acris_sold_check").run(SourceContext(session=session, settings=SimpleNamespace(), http=None))
    assert checked == [condo.id] and coop.id not in checked


def test_a_deed_recorded_before_the_listing_date_is_not_its_sale(session, monkeypatch):
    lst = _listing(session, "1013107501", listed=date(2026, 8, 21))
    wheres = []

    def fake_nyc(http, dataset, token, **kw):
        if dataset == acris.LEGALS:
            return [{"document_id": "2026081900706001", "unit": "3B"}]
        wheres.append(kw["where"])
        return []

    monkeypatch.setattr(acris.socrata, "nyc", fake_nyc)
    ctx = SourceContext(session=session, settings=SimpleNamespace(socrata_app_token=""), http=None)
    assert acris.find_deed(ctx, lst) is None
    assert "document_date >= '2026-08-21'" in wheres[0]  # nothing dated before the listing can match


def test_a_recent_only_sweep_judges_only_listings_new_enough_to_appear_in_it(session):
    """With daysOld=45 an older listing cannot show up even if still for sale, so it must not be counted as missed."""
    _seed(session)  # listed 2026-09-01
    session.add(Listing(source="rentcast_listings", external_id="old", address="7 Old St", price=1, original_price=1,
                        listed_date=date(2026, 5, 1), latitude=40.71, longitude=-74.01, status=ListingStatus.ACTIVE))
    session.commit()
    assert scope_ids(session, AREA) == {"rc1", "old"}
    assert scope_ids(session, AREA, listed_since=date(2026, 8, 1)) == {"rc1"}


def test_the_sweep_asks_only_for_recent_listings_when_configured(session):
    _seed(session)
    http = _Http(["rc1"], total=1)
    RentCastListings("rentcast_sweep", mode="full", insert_new=False, days_old=45, areas=[AREA]).run(_ctx(session, http))
    assert http.calls[0]["daysOld"] == 45
