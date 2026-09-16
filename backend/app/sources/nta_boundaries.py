import shapely
from shapely.geometry import mapping, shape

from app.models import Neighborhood
from app.sources.base import Source, SourceContext

# Degrees -> km at NYC's latitude (~40.7N); accurate to well under 1% across the city.
KM_PER_DEG_LON = 84.4
KM_PER_DEG_LAT = 111.0


def area_km2(geom) -> float:
    return shapely.transform(geom, lambda c: c * [KM_PER_DEG_LON, KM_PER_DEG_LAT]).area


class NtaBoundaries(Source):
    kind = "boundaries"
    description = "NYC 2020 Neighborhood Tabulation Areas (262 neighborhoods), NYC Open Data 9nt8-h7nd"

    def run(self, ctx: SourceContext) -> int:
        resp = ctx.http.get(
            "https://data.cityofnewyork.us/resource/9nt8-h7nd.geojson", params={"$limit": 1000}, timeout=120
        )
        resp.raise_for_status()
        existing = {n.code: n for n in ctx.session.query(Neighborhood).all()}
        features = resp.json()["features"]
        for f in features:
            p = f["properties"]
            geom = shapely.make_valid(shape(f["geometry"]))
            row = existing.get(p["nta2020"]) or Neighborhood(code=p["nta2020"])
            row.name = p["ntaname"]
            row.borough = p["boroname"]
            row.residential = p["ntatype"] == "0"  # 5-9 = parks, cemeteries, airports, etc.
            row.geometry = mapping(shapely.set_precision(geom, 1e-6))
            row.area_km2 = area_km2(geom)
            ctx.session.merge(row)
        ctx.session.commit()
        return len(features)
