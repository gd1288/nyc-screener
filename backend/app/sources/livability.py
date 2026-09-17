"""Quality-of-life, commercial vitality and climate-risk signals."""

from datetime import date

import numpy as np
import shapely
from shapely.geometry import shape

from app.sources import socrata
from app.sources.base import Source, SourceContext
from app.sources.development import area_share_by_nta


def _points(rows, lon_key="longitude", lat_key="latitude"):
    lons, lats = [], []
    for r in rows:
        try:
            lons.append(float(r[lon_key]))
            lats.append(float(r[lat_key]))
        except (KeyError, TypeError, ValueError):
            continue
    return np.array(lons), np.array(lats)


class NypdFelonies(Source):
    kind = "neighborhood"
    description = "NYPD complaint data (historic, qgea-i56i): felony counts, latest full year vs 5 years earlier"
    probe_socrata = ("data.cityofnewyork.us", "qgea-i56i")

    def _count(self, ctx: SourceContext, year: int) -> dict[str, int]:
        rows = socrata.nyc(
            ctx.http, "qgea-i56i", ctx.settings.socrata_app_token, select="latitude,longitude",
            where=f"law_cat_cd='FELONY' and cmplnt_fr_dt between '{year}-01-01' and '{year}-12-31T23:59:59'",
            order="cmplnt_num",
        )
        return ctx.geo.counts(*_points(rows))

    def run(self, ctx: SourceContext) -> int:
        latest = int(self.options.get("year") or date.today().year - 1)
        now, then = self._count(ctx, latest), self._count(ctx, latest - 5)
        change = {c: now.get(c, 0) / then[c] - 1 for c in ctx.geo.codes if then.get(c, 0) >= 25}
        return self.write_metrics(
            ctx,
            {"felonies": {c: float(now.get(c, 0)) for c in ctx.geo.codes}, "felony_change_5y": change},
            {"felonies": str(latest), "felony_change_5y": f"{latest - 5}-{latest}"},
        )


class LiquorLicenses(Source):
    kind = "neighborhood"
    description = "NYS Liquor Authority active licenses (9s3h-dpkz): bars/restaurants and how many opened recently"
    probe_socrata = ("data.ny.gov", "9s3h-dpkz")

    def run(self, ctx: SourceContext) -> int:
        years = int(self.options.get("recent_years", 3))
        cutoff = date.today().replace(year=date.today().year - years).isoformat()
        rows = list(socrata.nys(
            ctx.http, "9s3h-dpkz", ctx.settings.socrata_app_token, select="originalissuedate,georeference",
            where="premisescounty in ('New York','Kings','Queens','Bronx','Richmond')",
        ))
        pts = [(r["georeference"]["coordinates"], r.get("originalissuedate", "")) for r in rows if r.get("georeference")]
        codes = ctx.geo.lookup_many([p[0][0] for p in pts], [p[0][1] for p in pts])
        total, recent = {}, {}
        for code, (_, issued) in zip(codes, pts, strict=True):
            if code:
                total[code] = total.get(code, 0) + 1
                if issued >= cutoff:
                    recent[code] = recent.get(code, 0) + 1
        return self.write_metrics(
            ctx,
            {
                "liquor_licenses": {c: float(total.get(c, 0)) for c in ctx.geo.codes},
                "liquor_licenses_new": {c: float(recent.get(c, 0)) for c in ctx.geo.codes},
            },
            {"liquor_licenses": "active now", "liquor_licenses_new": f"issued since {cutoff[:7]}"},
        )


class FutureFloodplain(Source):
    kind = "neighborhood"
    description = "NYC Future Floodplain 2050s, 100-year (27ya-gqtm): share of neighborhood area at risk"
    probe_socrata = ("data.cityofnewyork.us", "27ya-gqtm")

    def run(self, ctx: SourceContext) -> int:
        dataset = self.options.get("dataset", "27ya-gqtm")
        resp = ctx.http.get(f"https://data.cityofnewyork.us/resource/{dataset}.geojson",
                            params={"$limit": 50000}, timeout=600)
        resp.raise_for_status()
        geoms = [shapely.make_valid(shape(f["geometry"])) for f in resp.json()["features"] if f.get("geometry")]
        share = area_share_by_nta(ctx, geoms)
        return self.write_metrics(ctx, {"floodplain_2050s_pct": share}, {"floodplain_2050s_pct": "2050s projection"})
