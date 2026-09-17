"""Development pipeline signals: DCP Housing Database (completions, permits) and MIH rezonings."""

from datetime import date

import shapely
from shapely.geometry import shape

from app.models import Neighborhood
from app.sources import socrata
from app.sources.base import Source, SourceContext


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


class HousingDatabase(Source):
    kind = "neighborhood"
    description = "NYC DCP Housing Database by 2020 NTA: completed units by year, filed/approved/permitted pipeline"
    probe_socrata = ("data.cityofnewyork.us", "kyz5-72x5")

    def run(self, ctx: SourceContext) -> int:
        rows = list(socrata.nyc(ctx.http, "kyz5-72x5", ctx.settings.socrata_app_token))
        valid = {c for (c,) in ctx.session.query(Neighborhood.code)}
        comp_years = sorted(int(k[4:]) for k in rows[0] if k.startswith("comp") and k[4:].isdigit())
        last = comp_years[-1]
        completions, pipeline, housing_units = {}, {}, {}
        for r in rows:
            code, units = r.get("nta2010"), _num(r.get("cenunits20"))
            if code not in valid or units < 200:  # skip non-residential areas; ratios are meaningless
                continue
            housing_units[code] = units
            completed = sum(_num(r.get(f"comp{y}")) for y in range(last - 4, last + 1))
            completions[code] = completed / units
            pipeline[code] = (_num(r.get("filed")) + _num(r.get("approved")) + _num(r.get("permitted"))) / units
        return self.write_metrics(
            ctx,
            {"new_units_5y_pct": completions, "pipeline_units_pct": pipeline, "housing_units": housing_units},
            {"new_units_5y_pct": f"{last - 4}-{last}", "pipeline_units_pct": "current", "housing_units": "2020 census"},
        )


class Rezonings(Source):
    kind = "neighborhood"
    description = "NYC DCP Mandatory Inclusionary Housing areas: neighborhood upzonings adopted since 2016"
    probe_socrata = ("data.cityofnewyork.us", "m79g-k9r4")

    def run(self, ctx: SourceContext) -> int:
        years = int(self.options.get("lookback_years", 10))
        since = date.today().replace(year=date.today().year - years).isoformat()
        rows = socrata.nyc(ctx.http, "m79g-k9r4", ctx.settings.socrata_app_token,
                           where=f"status='Adopted' and date_adopte >= '{since}'")
        geoms = [shapely.make_valid(shape(r["the_geom"])) for r in rows if r.get("the_geom")]
        share = area_share_by_nta(ctx, geoms)
        return self.write_metrics(ctx, {"rezoned_area_pct": share}, {"rezoned_area_pct": f"adopted since {since[:4]}"})


def area_share_by_nta(ctx: SourceContext, geoms: list) -> dict[str, float]:
    """Share of each NTA's area covered by the union of `geoms` (0 for NTAs with no overlap)."""
    geo = ctx.geo
    shares = {code: 0.0 for code in geo.codes}
    if not geoms:
        return shares
    tree = shapely.STRtree(geoms)
    for code, nta in zip(geo.codes, geo.geoms, strict=True):
        hits = tree.query(nta, predicate="intersects")
        if len(hits):
            covered = shapely.union_all([geoms[i] for i in hits]).intersection(nta)
            shares[code] = min(covered.area / nta.area, 1.0) if nta.area else 0.0
    return shares
