"""Transit access today (MTA subway stations) and planned infrastructure catalysts (catalysts.yaml)."""

import math
from collections import defaultdict

import numpy as np
import shapely
import shapely.affinity
import yaml

from app.config import BACKEND_DIR
from app.sources import socrata
from app.sources.base import Source, SourceContext

CATALYSTS_FILE = BACKEND_DIR / "catalysts.yaml"


def load_catalysts() -> list[dict]:
    with open(CATALYSTS_FILE) as f:
        return yaml.safe_load(f)["catalysts"]


class SubwayAccess(Source):
    kind = "neighborhood"
    description = "MTA subway stations (data.ny.gov 39hk-dx4f): station complexes and routes per neighborhood"
    probe_socrata = ("data.ny.gov", "39hk-dx4f")

    def run(self, ctx: SourceContext) -> int:
        rows = list(socrata.nys(ctx.http, "39hk-dx4f", ctx.settings.socrata_app_token))
        complexes: dict[str, dict] = {}
        for r in rows:
            c = complexes.setdefault(r["complex_id"], {"lon": float(r["gtfs_longitude"]),
                                                      "lat": float(r["gtfs_latitude"]), "routes": set()})
            c["routes"].update(r.get("daytime_routes", "").split())
        items = list(complexes.values())
        codes = ctx.geo.lookup_many([c["lon"] for c in items], [c["lat"] for c in items])
        stations, routes = defaultdict(int), defaultdict(set)
        for code, c in zip(codes, items, strict=True):
            if code:
                stations[code] += 1
                routes[code] |= c["routes"]

        # Distance from each neighborhood's centroid to the nearest station (km), a better
        # signal than raw counts for small neighborhoods sitting next to a hub.
        pts = shapely.points([c["lon"] for c in items], [c["lat"] for c in items])
        nearest_km = {}
        for code, geom in zip(ctx.geo.codes, ctx.geo.geoms, strict=True):
            centroid = geom.representative_point()
            d = shapely.distance(centroid, pts)
            i = int(np.argmin(d))
            nearest_km[code] = _km(centroid.x, centroid.y, items[i]["lon"], items[i]["lat"])

        return self.write_metrics(
            ctx,
            {
                "subway_stations": {c: float(stations.get(c, 0)) for c in ctx.geo.codes},
                "subway_routes": {c: float(len(routes.get(c, ()))) for c in ctx.geo.codes},
                "nearest_subway_km": nearest_km,
            },
            {"subway_stations": "current", "subway_routes": "current", "nearest_subway_km": "current"},
        )


class PlannedCatalysts(Source):
    kind = "neighborhood"
    description = "Curated planned transit/infrastructure projects (edit backend/catalysts.yaml)"

    def probe(self, ctx: SourceContext) -> tuple[bool | None, str]:
        # This source reads a local file, not the network — "reachability" means "the file is
        # there and parses", not an HTTP check.
        try:
            projects = load_catalysts()
            return True, f"backend/catalysts.yaml: {len(projects)} project(s)"
        except Exception as e:  # noqa: BLE001
            return False, f"backend/catalysts.yaml: {type(e).__name__}: {e}"

    def run(self, ctx: SourceContext) -> int:
        score = defaultdict(float)
        for project in load_catalysts():
            weight = float(project.get("weight", 1.0))
            radius_km = float(project.get("radius_km", 0.8))
            touched = set()
            for lon, lat in project["points"]:
                # Buffer in degrees, stretched for longitude at NYC's latitude.
                zone = shapely.affinity.scale(shapely.Point(lon, lat).buffer(radius_km / 111.0), xfact=111.0 / 84.4)
                touched |= {ctx.geo.codes[i] for i in ctx.geo.tree.query(zone, predicate="intersects")}
            for code in touched:
                score[code] += weight
        return self.write_metrics(
            ctx,
            {"planned_catalysts": {c: score.get(c, 0.0) for c in ctx.geo.codes}},
            {"planned_catalysts": "current plans"},
        )


def _km(lon1, lat1, lon2, lat2) -> float:
    return math.hypot((lon2 - lon1) * 84.4, (lat2 - lat1) * 111.0)
