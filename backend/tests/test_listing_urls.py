"""Listing-page finder: what it accepts, what it refuses, what it keeps, and what it spends."""

from datetime import date, timedelta
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import AppSetting
from app.pipeline import listing_urls as lu

KEY = "pplx-secret-should-never-appear"


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        yield s


# ------------------------------------------------------------------ matching

ZILLOW = "https://www.zillow.com/homes/for_sale/141-E-55th-St-APT-1A-New-York-NY-10022_rb/"
STREETEASY = "https://streeteasy.com/building/141-east-55-street-new-york/1a"


def test_unit_and_building_matches_across_url_styles():
    assert lu.match_level("141 E 55th St", "1A", ZILLOW) == "unit"
    assert lu.match_level("141 E 55th St", "1A", STREETEASY) == "unit"
    assert lu.match_level("141 E 55th St", "9Z", "https://streeteasy.com/building/141-east-55-street-new-york") == "building"


@pytest.mark.parametrize(
    "url",
    [
        "https://streeteasy.com/building/143-east-55-street/1a",  # different number
        "https://streeteasy.com/building/141-east-56-street/1a",  # different street
        "https://evil.example.com/141-east-55-street",  # not an allowed site
        "https://zillow.com.evil.com/141-east-55-street",  # look-alike host
        "http://www.zillow.com/141-E-55th-St",  # not https
        "javascript:alert(1)",
        "https://www.zillow.com/homes/for_sale/",  # no address in it at all
        "",
    ],
)
def test_wrong_property_or_site_is_refused(url):
    assert lu.match_level("141 E 55th St", "1A", url) is None


def test_short_units_do_not_claim_a_unit_match():
    """Unit '5' would match almost any URL, so it never yields a unit link; another unit's page is refused."""
    assert lu.match_level("141 E 55th St", "5", "https://streeteasy.com/building/141-east-55-street-new-york/15b") is None
    assert lu.match_level("141 E 55th St", "5", "https://streeteasy.com/building/141-east-55-street-new-york") == "building"


@pytest.mark.parametrize(
    "url",
    [
        "https://www.redfin.com/NY/New-York/155-E-34th-St-10016/unit-16C/home/45253972",  # unit 16C is not 16S
        "https://www.compass.com/listing/155-east-34th-street-unit-16mn-manhattan-ny-10016/1695208345717077697/",
        "https://www.zillow.com/homedetails/155-E-34th-St-APT-16J-New-York-NY-10016/31507169_zpid/",
        "https://streeteasy.com/property/844640-155-east-34-street-phb",
        "https://www.elliman.com/newyorkcity/sales/detail/527-l-551-01_4340378/155-east-34th-st-midtown-east-new-york-ny",
    ],
)
def test_another_units_page_is_never_labelled_as_this_unit_or_the_building(url):
    assert lu.match_level("155 E 34th St", "16S", url) is None


@pytest.mark.parametrize(
    "url",
    [
        "https://streeteasy.com/building/155-east-34-street-new_york",
        "https://www.zillow.com/b/155-e-34th-st-new-york-ny-4Nwq/",
        "https://www.compass.com/building/warren-house-155-e-34th-st-manhattan-ny/281937762834239941/",
    ],
)
def test_genuine_building_pages_are_accepted_as_building_level(url):
    assert lu.match_level("155 E 34th St", "16S", url) == "building"


def test_suite_style_units_are_normalised():
    url = "https://streeteasy.com/building/50-west-47-street-new-york/ste-1808"
    assert lu.match_level("50 W 47th St", "STE1808", url) == "unit"


def test_unit_match_beats_a_better_ranked_building_match():
    results = [{"url": "https://streeteasy.com/building/141-east-55-street-new-york"}, {"url": ZILLOW}]
    assert lu.pick_url("141 E 55th St", "1A", results) == (ZILLOW, "unit")
    assert lu.pick_url("141 E 55th St", "1A", [{"url": "https://evil.example.com/x"}]) is None


# ------------------------------------------------------------------ the API call and what is kept

class _Http:
    def __init__(self, results=None, status=200):
        self.results, self.status, self.calls = results if results is not None else [], status, []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        return SimpleNamespace(
            status_code=self.status,
            json=lambda: {"results": self.results},
            raise_for_status=lambda: _raise(self.status),
        )


def _raise(status):
    if status >= 400:
        req = httpx.Request("POST", lu.API)
        raise httpx.HTTPStatusError("boom " + KEY, request=req, response=httpx.Response(status, request=req))


HIT = {"url": ZILLOW, "title": "141 E 55th St #1A", "snippet": "For sale $999,999 lovely renovated two bedroom", "date": "2026-09-01"}


def _listing(i=1, address="141 E 55th St", unit="1A"):
    return SimpleNamespace(id=i, address=address, unit=unit, borough="Manhattan")


def test_request_is_restricted_to_allowed_domains_and_key_is_in_a_header():
    http = _Http([HIT])
    lu.search(http, KEY, "q")
    call = http.calls[0]
    assert call["json"]["search_domain_filter"] == lu.ALLOWED_DOMAINS and len(lu.ALLOWED_DOMAINS) <= 20
    assert call["headers"]["Authorization"] == f"Bearer {KEY}" and KEY not in str(call["json"]) and KEY not in call["url"]


def test_result_text_is_dropped_and_only_the_url_is_stored(session):
    stats = lu.find_urls(session, _Http([HIT]), KEY, [_listing()])
    stored = session.get(AppSetting, lu.URLS_KEY).value["1"]
    assert stats["found_unit"] == 1 and stored["url"] == ZILLOW and stored["level"] == "unit"
    assert "999" not in str(stored) and "snippet" not in stored and "title" not in stored


def test_no_match_is_remembered_so_it_is_not_searched_again(session):
    http = _Http([{"url": "https://streeteasy.com/building/999-other-street", "snippet": "x"}])
    lu.find_urls(session, http, KEY, [_listing()])
    lu.find_urls(session, http, KEY, [_listing()])
    assert len(http.calls) == 1 and session.get(AppSetting, lu.URLS_KEY).value["1"]["url"] is None


def test_stale_entries_are_searched_again(session):
    old = (date.today() - timedelta(days=45)).isoformat()
    session.merge(AppSetting(key=lu.URLS_KEY, value={"1": {"url": None, "level": None, "found_at": old}}))
    session.commit()
    http = _Http([HIT])
    lu.find_urls(session, http, KEY, [_listing()])
    assert len(http.calls) == 1


# ------------------------------------------------------------------ spending and errors

def test_monthly_budget_is_a_hard_stop(session):
    http = _Http([])
    stats = lu.find_urls(session, http, KEY, [_listing(i, f"{100 + i} E 55th St", None) for i in range(1, 6)], monthly_limit=2)
    assert len(http.calls) == 2 and lu.requests_used(session) == 2 and "monthly budget" in stats["stopped"]


def test_per_run_limit_stops_early(session):
    http = _Http([])
    stats = lu.find_urls(session, http, KEY, [_listing(i, f"{100 + i} E 55th St", None) for i in range(1, 6)], limit=3)
    assert len(http.calls) == 3 and stats["stopped"] == "per-run limit"


def test_a_failed_call_is_still_counted_and_never_leaks_the_key(session):
    with pytest.raises(RuntimeError) as e:
        lu.find_urls(session, _Http(status=401), KEY, [_listing()])
    assert KEY not in str(e.value) and "401" in str(e.value)
    assert lu.requests_used(session) == 1
