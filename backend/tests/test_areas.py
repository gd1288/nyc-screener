"""The US-wide area model: region loading, the NYC mirror, and the tract adapter."""

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Area, AreaMetric, Neighborhood, Region
from app.pipeline import areas as areas_mod
from app.sources import tigerweb
from app.sources.base import Source, SourceContext

FIXTURES = Path(__file__).parent / "fixtures"
SQUARE = {
    "type": "Polygon",
    "coordinates": [[[-74.02, 40.70], [-74.00, 40.70], [-74.00, 40.72], [-74.02, 40.72], [-74.02, 40.70]]],
}


def make_session():
    engine_ = create_engine("sqlite://")
    Base.metadata.create_all(engine_)
    return sessionmaker(bind=engine_)()


def test_known_region_counties_are_real_counties_with_the_expected_names():
    """The CBSA-to-county lists are a hand-maintained table (no free API returns them), so they are
    checked against a recorded TIGERweb response. A mistyped FIPS would otherwise quietly load a
    different county's tracts and look like a successful region load."""
    recorded = json.loads((FIXTURES / "tigerweb_counties.json").read_text())
    real = {f["attributes"]["GEOID"]: f["attributes"]["BASENAME"] for f in recorded["features"]}

    expected_names = {
        "48021": "Bastrop",
        "48055": "Caldwell",
        "48209": "Hays",
        "48453": "Travis",
        "48491": "Williamson",
        "36005": "Bronx",
        "36047": "Kings",
        "36061": "New York",
        "36081": "Queens",
        "36085": "Richmond",
    }
    for region in areas_mod.KNOWN_REGIONS.values():
        for county in region.counties:
            assert county in real, f"{county} is not a real county GEOID ({region.name})"
            assert real[county] == expected_names[county]
        assert all(c.startswith(region.state_fips) for c in region.counties) or region.code == areas_mod.NYC_CBSA


def test_austin_and_nyc_do_not_share_counties():
    """A copy-paste between region entries is the likeliest way this table goes wrong."""
    austin = set(areas_mod.KNOWN_REGIONS["austin"].counties)
    nyc = set(areas_mod.KNOWN_REGIONS["nyc"].counties)
    assert austin and nyc and not (austin & nyc)


@pytest.mark.parametrize(
    "cbsa, state, expected",
    [("12420", "48", "cbsa:12420"), (None, "48", "state:48"), (None, None, "unassigned")],
)
def test_comparison_set_prefers_the_metro_then_the_state(cbsa, state, expected):
    """A percentile is only meaningful within a comparable market - ranking a Manhattan tract
    against a rural one measures two different housing markets, not two neighborhoods."""
    assert areas_mod.comparison_set_for(Area(kind="tract", code="x", cbsa=cbsa, state_fips=state)) == expected


def test_sync_nyc_ntas_mirrors_neighborhoods_and_is_idempotent():
    session = make_session()
    session.add(
        Neighborhood(code="MN0101", name="FiDi", borough="Manhattan", residential=True, geometry=SQUARE, area_km2=2.0)
    )
    session.add(
        Neighborhood(
            code="MN9999", name="A Park", borough="Manhattan", residential=False, geometry=SQUARE, area_km2=1.0
        )
    )
    session.commit()

    assert areas_mod.sync_nyc_ntas(session) == 2
    assert areas_mod.sync_nyc_ntas(session) == 2  # re-running updates rather than duplicating
    assert session.query(Area).filter(Area.kind == "nta").count() == 2

    area = session.query(Area).filter(Area.code == "MN0101").one()
    assert (area.cbsa, area.state_fips, area.county_fips, area.nta_code) == ("35620", "36", "36061", "MN0101")
    assert session.query(Area).filter(Area.code == "MN9999").one().residential is False


def test_sync_nyc_ntas_follows_a_renamed_neighborhood():
    session = make_session()
    session.add(
        Neighborhood(code="MN0101", name="Old", borough="Manhattan", residential=True, geometry=SQUARE, area_km2=2.0)
    )
    session.commit()
    areas_mod.sync_nyc_ntas(session)

    session.query(Neighborhood).one().name = "New"
    session.commit()
    areas_mod.sync_nyc_ntas(session)

    assert session.query(Area).filter(Area.kind == "nta").one().name == "New"


def test_ensure_region_is_idempotent():
    session = make_session()
    first = areas_mod.ensure_region(session, "cbsa", "12420", "Austin", "48")
    second = areas_mod.ensure_region(session, "cbsa", "12420", "Austin", "48")
    assert first.id == second.id
    assert session.query(Region).count() == 1


def test_resolve_region_refuses_a_bare_cbsa_code():
    """Without a county list there is nothing to fetch, and a region that loads zero tracts would
    look like a working region that simply has no data."""
    assert areas_mod.resolve_region("austin") is areas_mod.KNOWN_REGIONS["austin"]
    assert areas_mod.resolve_region("AUSTIN ") is areas_mod.KNOWN_REGIONS["austin"]
    assert areas_mod.resolve_region("12420") is None
    assert areas_mod.resolve_region("nowhere") is None


@pytest.mark.parametrize(
    "geometry, expected_type",
    [
        ({"rings": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}, "Polygon"),
        ({"rings": [[[0, 0], [1, 0], [1, 1], [0, 0]], [[5, 5], [6, 5], [6, 6], [5, 5]]]}, "MultiPolygon"),
    ],
)
def test_arcgis_rings_convert_to_geojson(geometry, expected_type):
    assert tigerweb._rings_to_geojson(geometry)["type"] == expected_type


def test_arcgis_rings_drop_the_z_and_m_ordinates():
    """ArcGIS can return 3- or 4-element vertices; GeoJSON consumers here expect [x, y]."""
    converted = tigerweb._rings_to_geojson({"rings": [[[1, 2, 99], [3, 4, 99], [1, 2, 99]]]})
    assert converted["coordinates"] == [[[1, 2], [3, 4], [1, 2]]]


@pytest.mark.parametrize("geometry", [None, {}, {"rings": []}])
def test_missing_geometry_is_none_not_an_empty_shape(geometry):
    assert tigerweb._rings_to_geojson(geometry) is None


class _FakeHttp:
    """Serves one recorded TIGERweb page per request, so the pager is exercised without the network."""

    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append(params)
        page = self.pages[min(len(self.calls) - 1, len(self.pages) - 1)]

        class _Response:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return page

        return _Response()


def _tract_feature(geoid, land=5_000_000):
    return {
        "attributes": {
            "GEOID": geoid,
            "NAME": f"Census Tract {geoid[-4:]}",
            "AREALAND": land,
            "STATE": geoid[:2],
            "COUNTY": geoid[2:5],
        },
        "geometry": {"rings": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
    }


def test_tract_loader_writes_areas_and_marks_water_only_tracts_non_residential():
    session = make_session()
    http = _FakeHttp([{"features": [_tract_feature("48453000100"), _tract_feature("48453000200", land=0)]}])
    ctx = SourceContext(session=session, settings=None, http=http)

    written = tigerweb.TigerwebTracts("t").load_counties(ctx, ["48453"], cbsa="12420")

    assert written == 2
    loaded = {a.code: a for a in session.query(Area)}
    assert loaded["48453000100"].residential is True
    assert loaded["48453000100"].cbsa == "12420"
    assert loaded["48453000100"].area_km2 == 5.0
    # A water-only tract has no residents; leaving it residential would drag every percentile.
    assert loaded["48453000200"].residential is False


def test_tract_loader_pages_until_a_short_page():
    """A county truncated at the service's record cap would look like a fully loaded region."""
    session = make_session()
    full = {"features": [_tract_feature(f"484530{i:04d}") for i in range(tigerweb.PAGE_SIZE)]}
    http = _FakeHttp([full, {"features": [_tract_feature("48453999999")]}])
    ctx = SourceContext(session=session, settings=None, http=http)

    tigerweb.TigerwebTracts("t").load_counties(ctx, ["48453"], cbsa="12420")

    assert len(http.calls) == 2
    assert http.calls[1]["resultOffset"] == tigerweb.PAGE_SIZE
    assert session.query(Area).count() == tigerweb.PAGE_SIZE + 1


def test_tract_loader_is_idempotent():
    session = make_session()
    for _ in range(2):
        http = _FakeHttp([{"features": [_tract_feature("48453000100")]}])
        tigerweb.TigerwebTracts("t").load_counties(
            SourceContext(session=session, settings=None, http=http), ["48453"], cbsa="12420"
        )
    assert session.query(Area).count() == 1


class _MetricSource(Source):
    kind = "neighborhood"
    coverage = "national"
    granularity = "tract"


def test_write_area_metrics_skips_codes_with_no_area_row():
    """An area's geometry and CBSA come from the boundary source that owns it; inventing a bare row
    from a metric feed would produce areas that can never be scored or mapped."""
    session = make_session()
    session.add(Area(kind="tract", code="48453000100", name="T1"))
    session.commit()
    ctx = SourceContext(session=session, settings=None, http=None)

    written = _MetricSource("fhfa").write_area_metrics(
        ctx, {"hpi_cagr_5y": {"48453000100": 0.04, "99999999999": 0.09}}, {"hpi_cagr_5y": "2024"}
    )

    assert written == 1
    assert session.query(AreaMetric).one().value == pytest.approx(0.04)


def test_write_area_metrics_replaces_only_its_own_metrics():
    session = make_session()
    session.add(Area(kind="tract", code="48453000100", name="T1"))
    session.commit()
    ctx = SourceContext(session=session, settings=None, http=None)
    _MetricSource("other").write_area_metrics(ctx, {"walkability": {"48453000100": 12.0}}, {})

    _MetricSource("fhfa").write_area_metrics(ctx, {"hpi_cagr_5y": {"48453000100": 0.04}}, {})
    _MetricSource("fhfa").write_area_metrics(ctx, {"hpi_cagr_5y": {"48453000100": 0.07}}, {})

    values = {(m.source, m.metric): m.value for m in session.query(AreaMetric)}
    assert values == {("other", "walkability"): 12.0, ("fhfa", "hpi_cagr_5y"): 0.07}


def test_nan_area_metrics_are_skipped():
    session = make_session()
    session.add(Area(kind="tract", code="48453000100", name="T1"))
    session.commit()
    ctx = SourceContext(session=session, settings=None, http=None)

    written = _MetricSource("f").write_area_metrics(ctx, {"m": {"48453000100": float("nan")}}, {})

    assert written == 0
    assert session.query(AreaMetric).count() == 0


def test_every_source_declares_a_coverage_and_granularity():
    """The defaults describe the pre-area-model NYC sources. A national source that forgets to
    override them would be skipped for every non-NYC region, which is silent, not loud."""
    from app.sources.registry import load_sources

    for entry in load_sources():
        assert entry.source.coverage.split(":")[0] in {"national", "state", "city"}
        assert entry.source.granularity in {"tract", "block_group", "zcta", "nta", "county", "point"}
