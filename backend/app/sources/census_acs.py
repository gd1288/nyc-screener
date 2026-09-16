"""US Census ACS 5-year estimates by tract, aggregated to 2020 NTAs (requires CENSUS_API_KEY).

Compares the latest ACS release with the one ten years earlier. Older releases use 2010 tracts; those are
mapped to NTAs through their 2020 successors (same code, or split children sharing the first four digits).
"""

from collections import Counter, defaultdict
from datetime import date

from app.sources import socrata
from app.sources.base import Source, SourceContext

COUNTIES = ["005", "047", "061", "081", "085"]
VARS = {
    "pop": "B01003_001E",
    "households": "B11001_001E",
    "agg_income": "B19025_001E",
    "pop25": "B15003_001E",
    "ba": "B15003_022E",
    "ma": "B15003_023E",
    "prof": "B15003_024E",
    "phd": "B15003_025E",
    "m25": "B01001_011E",
    "m30": "B01001_012E",
    "f25": "B01001_035E",
    "f30": "B01001_036E",
    "tenure": "B25003_001E",
    "renters": "B25003_003E",
}


class CensusAcs(Source):
    kind = "neighborhood"
    requires = ["census_api_key"]
    description = "US Census ACS 5-year: population, income, education, age and tenure trends by neighborhood"

    def run(self, ctx: SourceContext) -> int:
        latest = int(self.options.get("latest_year") or self._latest_available(ctx))
        earlier = latest - 10
        tract_to_nta = {r["geoid"]: r["ntacode"] for r in socrata.nyc(
            ctx.http, "hm78-6dwm", ctx.settings.socrata_app_token, select="geoid,ntacode")}

        now = self._aggregate(self._fetch(ctx, latest), tract_to_nta)
        then = self._aggregate(self._fetch(ctx, earlier), _legacy_mapping(tract_to_nta))

        metrics = defaultdict(dict)
        for nta, v in now.items():
            if v["pop"] < 500:
                continue
            p = then.get(nta)
            metrics["population"][nta] = v["pop"]
            metrics["mean_household_income"][nta] = v["agg_income"] / v["households"] if v["households"] else None
            metrics["bachelors_plus_share"][nta] = _share(v, ["ba", "ma", "prof", "phd"], "pop25")
            metrics["age_25_34_share"][nta] = _share(v, ["m25", "m30", "f25", "f30"], "pop")
            metrics["renter_share"][nta] = _share(v, ["renters"], "tenure")
            if p and p["pop"] >= 500 and p["households"]:
                metrics["population_change_10y"][nta] = v["pop"] / p["pop"] - 1
                inc_then = p["agg_income"] / p["households"]
                if v["households"] and inc_then:
                    metrics["income_cagr_10y"][nta] = (metrics["mean_household_income"][nta] / inc_then) ** 0.1 - 1
                metrics["bachelors_share_change_10y"][nta] = (
                    metrics["bachelors_plus_share"][nta] - _share(p, ["ba", "ma", "prof", "phd"], "pop25"))
        span = f"{earlier}-{latest}"
        as_of = {k: (span if "change" in k or "cagr" in k else f"ACS {latest - 4}-{latest}") for k in metrics}
        return self.write_metrics(ctx, dict(metrics), as_of)

    def _latest_available(self, ctx: SourceContext) -> int:
        for year in range(date.today().year - 1, date.today().year - 5, -1):
            r = ctx.http.get(f"https://api.census.gov/data/{year}/acs/acs5",
                             params={"get": "NAME", "for": "state:36", "key": ctx.settings.census_api_key})
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("application/json"):
                return year
        raise RuntimeError("Could not find a recent ACS 5-year release.")

    def _fetch(self, ctx: SourceContext, year: int) -> dict[str, dict[str, float]]:
        out = {}
        for county in COUNTIES:
            r = ctx.http.get(
                f"https://api.census.gov/data/{year}/acs/acs5",
                params={"get": ",".join(VARS.values()), "for": "tract:*", "in": f"state:36 county:{county}",
                        "key": ctx.settings.census_api_key},
                timeout=120,
            )
            r.raise_for_status()
            header, *rows = r.json()
            for row in rows:
                rec = dict(zip(header, row))
                geoid = rec["state"] + rec["county"] + rec["tract"]
                out[geoid] = {k: max(float(rec[v] or 0), 0.0) for k, v in VARS.items()}  # negatives = suppressed
        return out

    @staticmethod
    def _aggregate(tracts: dict[str, dict], mapping: dict[str, str]) -> dict[str, dict[str, float]]:
        agg: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for geoid, values in tracts.items():
            nta = mapping.get(geoid)
            if nta:
                for k, v in values.items():
                    agg[nta][k] += v
        return agg


def _share(v: dict, parts: list[str], total: str) -> float | None:
    return sum(v[p] for p in parts) / v[total] if v[total] else None


def _legacy_mapping(tract_to_nta: dict[str, str]) -> dict[str, str]:
    """Map 2010 tract GEOIDs to 2020 NTAs: exact code match, else the most common NTA among split children."""
    mapping = dict(tract_to_nta)
    by_parent = defaultdict(Counter)
    for geoid, nta in tract_to_nta.items():
        by_parent[geoid[:9]][nta] += 1
    for parent, counter in by_parent.items():
        mapping.setdefault(parent + "00", counter.most_common(1)[0][0])
    return mapping
