"""Loading areas and the regions they belong to.

`areas` is the US-wide table every new source writes to. NYC is not migrated into it — its NTAs are
*mirrored* into it, so the existing `neighborhoods` pages keep reading their own tables unchanged
while the same scoring code can rank an NTA and an Austin tract through one path. That mirroring is
what makes Phase 1 additive rather than a rewrite of a working screener.

A region is loaded on demand (`POST /api/regions`, or `app.cli add-region`). Only regions marked
`watched` refresh on a schedule, so looking at Austin once doesn't commit every later refresh to
re-fetching it.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Area, Neighborhood, Region

NYC_CBSA = "35620"
NY_STATE_FIPS = "36"
# NYC's five boroughs are five counties; the tract GEOIDs national sources use are keyed by these.
NYC_COUNTY_FIPS = {
    "Manhattan": "36061",
    "Bronx": "36005",
    "Brooklyn": "36047",
    "Queens": "36081",
    "Staten Island": "36085",
}


@dataclass(frozen=True)
class KnownRegion:
    kind: str
    code: str
    name: str
    state_fips: str
    counties: tuple[str, ...]  # 5-digit county FIPS; tracts are fetched per county


# Metros whose CBSA and member counties are recorded here so `add-region austin` works without the
# user supplying FIPS codes. The county lists are the OMB delineation, and every code is checked
# against TIGERweb's own county names by `tests/test_areas.py::test_known_region_counties_are_real`
# — a mistyped FIPS would otherwise silently load the wrong metro's tracts.
#
# There is no free API that returns a CBSA's counties (the Census API rejects that geography
# combination and TIGERweb's county layer carries no CBSA field), which is why this is a table.
KNOWN_REGIONS = {
    "nyc": KnownRegion(
        "cbsa", NYC_CBSA, "New York-Newark-Jersey City, NY-NJ", NY_STATE_FIPS, tuple(sorted(NYC_COUNTY_FIPS.values()))
    ),
    "austin": KnownRegion(
        "cbsa", "12420", "Austin-Round Rock-San Marcos, TX", "48", ("48021", "48055", "48209", "48453", "48491")
    ),
}


def comparison_set_for(area: Area) -> str:
    """The set an area's percentiles are ranked within.

    A metro by default — ranking a Manhattan tract against a rural one measures the difference
    between two housing markets, not the difference between two neighborhoods. Areas with no CBSA
    fall back to their state so they are still ranked against *something* comparable.
    """
    if area.cbsa:
        return f"cbsa:{area.cbsa}"
    if area.state_fips:
        return f"state:{area.state_fips}"
    return "unassigned"


def ensure_region(session: Session, kind: str, code: str, name: str, state_fips: str | None = None) -> Region:
    region = session.query(Region).filter(Region.kind == kind, Region.code == code).one_or_none()
    if region is None:
        region = Region(kind=kind, code=code, name=name, state_fips=state_fips)
        session.add(region)
        session.commit()
    return region


def resolve_region(name_or_code: str) -> KnownRegion | None:
    """A metro by nickname. An unknown CBSA code is deliberately *not* resolved: without its county
    list there is nothing to fetch tracts for, and returning a region that loads zero areas would
    look like a working region with no data."""
    return KNOWN_REGIONS.get(name_or_code.strip().lower())


def sync_nyc_ntas(session: Session) -> int:
    """Mirror NYC's neighborhoods into `areas`. Idempotent: re-running updates in place rather than
    duplicating, so it is safe to call on every refresh."""
    ensure_region(session, "cbsa", NYC_CBSA, KNOWN_REGIONS["nyc"].name, NY_STATE_FIPS)
    existing = {a.code: a for a in session.query(Area).filter(Area.kind == "nta")}
    synced = 0
    for hood in session.query(Neighborhood):
        area = existing.get(hood.code)
        if area is None:
            area = Area(kind="nta", code=hood.code)
            session.add(area)
        area.name = hood.name
        area.state_fips = NY_STATE_FIPS
        area.county_fips = NYC_COUNTY_FIPS.get(hood.borough)
        area.cbsa = NYC_CBSA
        area.residential = hood.residential
        area.geometry = hood.geometry
        area.area_km2 = hood.area_km2
        area.nta_code = hood.code
        synced += 1
    session.commit()
    return synced
