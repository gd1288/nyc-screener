"""Point-in-neighborhood lookups against the 2020 NTA polygons."""

import numpy as np
import shapely
from shapely.geometry import shape
from sqlalchemy.orm import Session

from app.models import Neighborhood


class NeighborhoodIndex:
    def __init__(self, neighborhoods: list[Neighborhood]):
        self.codes = [n.code for n in neighborhoods]
        self.geoms = [shapely.make_valid(shape(n.geometry)) for n in neighborhoods]
        self.tree = shapely.STRtree(self.geoms)

    @classmethod
    def load(cls, session: Session) -> "NeighborhoodIndex":
        rows = session.query(Neighborhood).all()
        if not rows:
            raise RuntimeError("No neighborhoods loaded yet; run the nta_boundaries source first.")
        return cls(rows)

    def lookup(self, lon: float | None, lat: float | None) -> str | None:
        if lon is None or lat is None:
            return None
        return self.lookup_many(np.array([lon]), np.array([lat]))[0]

    def lookup_many(self, lons, lats) -> list[str | None]:
        """Vectorised point-in-polygon. Returns an NTA code (or None) per point."""
        lons = np.asarray(lons, dtype=float)
        lats = np.asarray(lats, dtype=float)
        result: list[str | None] = [None] * len(lons)
        valid = ~(np.isnan(lons) | np.isnan(lats))
        idx = np.flatnonzero(valid)
        if len(idx) == 0:
            return result
        points = shapely.points(lons[idx], lats[idx])
        point_i, geom_i = self.tree.query(points, predicate="within")
        for p, g in zip(point_i, geom_i, strict=True):
            result[idx[p]] = self.codes[g]
        return result

    def counts(self, lons, lats) -> dict[str, int]:
        out: dict[str, int] = {}
        for code in self.lookup_many(lons, lats):
            if code:
                out[code] = out.get(code, 0) + 1
        return out
