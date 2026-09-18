"""Census tract boundaries from TIGERweb — the universal geography every national source rolls up to.

Free, keyless, and national. Tracts are fetched per county because that is the only filter the
service exposes cheaply (`WHERE STATE=.. AND COUNTY=..`); a region supplies its county list.

Geometry comes back as ArcGIS rings rather than GeoJSON, so it is converted here. The service caps a
single response well below a large county's tract count, so requests are paged with
`resultOffset` — a county silently truncated at the cap would produce a region that looks loaded but
is missing half its neighborhoods.
"""

from typing import Any

from app.models import Area
from app.pipeline.areas import KnownRegion
from app.sources.base import Source, SourceContext, SourceSkipped

TRACTS_URL = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Tracts_Blocks/MapServer/0/query"
PAGE_SIZE = 500
OUT_FIELDS = "GEOID,NAME,BASENAME,AREALAND,STATE,COUNTY"


def _rings_to_geojson(geometry: dict[str, Any] | None) -> dict | None:
    """ArcGIS `rings` -> GeoJSON. ArcGIS puts every ring of every part in one flat list, so a county
    with multi-part tracts (islands, split blocks) becomes a MultiPolygon of one-ring polygons.
    That is coarser than resolving true holes, and enough for display and point-in-polygon."""
    rings = (geometry or {}).get("rings")
    if not rings:
        return None
    if len(rings) == 1:
        return {"type": "Polygon", "coordinates": [[[x, y] for x, y, *_ in rings[0]]]}
    return {"type": "MultiPolygon", "coordinates": [[[[x, y] for x, y, *_ in ring]] for ring in rings]}


def fetch_county_tracts(ctx: SourceContext, county_fips: str) -> list[dict]:
    state, county = county_fips[:2], county_fips[2:]
    features: list[dict] = []
    offset = 0
    while True:
        response = ctx.http.get(
            TRACTS_URL,
            params={
                "where": f"STATE='{state}' AND COUNTY='{county}'",
                "outFields": OUT_FIELDS,
                "returnGeometry": "true",
                "outSR": "4326",
                "f": "json",
                "resultOffset": offset,
                "resultRecordCount": PAGE_SIZE,
            },
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        if "error" in payload:
            raise RuntimeError(f"TIGERweb error for {county_fips}: {payload['error']}")
        page = payload.get("features", [])
        features.extend(page)
        if len(page) < PAGE_SIZE:
            return features
        offset += PAGE_SIZE


class TigerwebTracts(Source):
    kind = "boundaries"
    coverage = "national"
    granularity = "tract"
    description = "Census tract boundaries (TIGERweb), the universal area unit"
    probe_url = f"{TRACTS_URL}?where=1%3D0&f=json"

    def run(self, ctx: SourceContext) -> int:
        region = ctx.region
        if region is None:
            raise SourceSkipped("no region selected; tracts are loaded per region")
        known = self.options.get("known_region")
        counties = known.counties if isinstance(known, KnownRegion) else self.options.get("counties", ())
        if not counties:
            raise SourceSkipped(f"no counties recorded for region {region.code}")
        return self.load_counties(ctx, counties, cbsa=region.code if region.kind == "cbsa" else None)

    def load_counties(self, ctx: SourceContext, counties, cbsa: str | None) -> int:
        existing = {a.code: a for a in ctx.session.query(Area).filter(Area.kind == "tract")}
        written = 0
        for county_fips in counties:
            for feature in fetch_county_tracts(ctx, county_fips):
                attrs = feature.get("attributes", {})
                geoid = attrs.get("GEOID")
                if not geoid:
                    continue
                area = existing.get(geoid)
                if area is None:
                    area = Area(kind="tract", code=geoid)
                    ctx.session.add(area)
                    existing[geoid] = area
                area.name = attrs.get("NAME") or f"Tract {attrs.get('BASENAME', geoid)}"
                area.state_fips = attrs.get("STATE")
                area.county_fips = county_fips
                area.cbsa = cbsa
                area.geometry = _rings_to_geojson(feature.get("geometry"))
                area.area_km2 = round((attrs.get("AREALAND") or 0) / 1_000_000, 4)
                # A tract with no land is water-only (harbours, bays). It has no residents to score,
                # and leaving it residential would drag every percentile toward an empty tract.
                area.residential = bool(attrs.get("AREALAND"))
                written += 1
        ctx.session.commit()
        return written
