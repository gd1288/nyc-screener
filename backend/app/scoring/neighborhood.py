"""Neighborhood Growth Score (0-100).

Each metric is converted to a percentile rank across residential neighborhoods (inverted where lower is
better). Metrics roll up into pillars; pillars combine with editable weights. A pillar with no data counts
as neutral (50) and `coverage` records how much of the weight was backed by data.
Flood exposure is a separate penalty in points, so a strong neighborhood with high climate risk is marked down.
"""

from dataclasses import dataclass

import pandas as pd
import shapely
from shapely.geometry import shape
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import AppSetting, Neighborhood, NeighborhoodMetric, NeighborhoodScore


@dataclass(frozen=True)
class MetricDef:
    key: str
    label: str
    higher_is_better: bool = True
    fmt: str = "pct"  # pct, num, money, km


PILLARS: dict[str, dict] = {
    "valuation": {
        "label": "Valuation gap / catch-up room",
        "description": "Cheaper than its borough and its neighbors, with a strong rent yield: room to catch up.",
        "metrics": [
            MetricDef("value_gap_borough", "Discount to borough median condo value"),
            MetricDef("value_gap_neighbors", "Discount to adjacent neighborhoods"),
            MetricDef("gross_rent_yield", "Gross rent yield (rent / value)"),
        ],
    },
    "development": {
        "label": "Development pipeline",
        "description": "New housing being built or planned and recent upzonings: signs of investment and demand.",
        "metrics": [
            MetricDef("pipeline_units_pct", "Units filed/approved/permitted, % of housing stock"),
            MetricDef("new_units_5y_pct", "Units completed in last 5 yrs, % of stock"),
            MetricDef("rezoned_area_pct", "Area upzoned in last 10 yrs (MIH)"),
        ],
    },
    "infrastructure": {
        "label": "Infrastructure & transit",
        "description": "Transit access today plus funded/planned projects that improve access in the future.",
        "metrics": [
            MetricDef("planned_catalysts", "Planned transit/development catalysts nearby", fmt="num"),
            MetricDef("subway_routes", "Subway routes serving the neighborhood", fmt="num"),
            MetricDef("nearest_subway_km", "Distance to nearest subway station", higher_is_better=False, fmt="km"),
        ],
    },
    "demographics": {
        "label": "Demographic shift",
        "description": "Population, income and education rising, with a large share of young adults.",
        "metrics": [
            MetricDef("population_change_10y", "Population change, 10 yrs"),
            MetricDef("income_cagr_10y", "Household income growth per year, 10 yrs"),
            MetricDef("bachelors_share_change_10y", "Change in bachelor's-degree share, 10 yrs"),
            MetricDef("age_25_34_share", "Share of residents aged 25-34"),
        ],
    },
    "momentum": {
        "label": "Price & rent momentum",
        "description": "Recent appreciation in condo values and rents, and rising sales activity.",
        "metrics": [
            MetricDef("zhvi_cagr_5y", "Condo value growth per year, 5 yrs"),
            MetricDef("zhvi_cagr_10y", "Condo value growth per year, 10 yrs"),
            MetricDef("condo_repeat_sales_cagr", "Repeat-sale appreciation per year (DOF)"),
            MetricDef("zori_cagr_3y", "Rent growth per year, 3 yrs"),
            MetricDef("condo_sales_volume_change_5y", "Change in condo sales volume, 5 yrs"),
        ],
    },
    "commercial": {
        "label": "Commercial vitality",
        "description": "Restaurants and bars opening: an early sign of neighborhood change.",
        "metrics": [
            MetricDef("liquor_new_share", "Share of liquor licenses issued in last 3 yrs"),
            MetricDef("liquor_per_km2", "Liquor licenses per km²", fmt="num"),
        ],
    },
    "quality": {
        "label": "Safety & quality of life",
        "description": "Lower and falling serious crime.",
        "metrics": [
            MetricDef("felonies_per_1k_units", "Felonies per 1,000 housing units", higher_is_better=False, fmt="num"),
            MetricDef("felony_change_5y", "Felony change, 5 yrs", higher_is_better=False),
        ],
    },
}

# Backtest (app/scoring/backtest.py, 2008-2024): the valuation gap predicted next-10-year condo growth in every
# period (Spearman 0.20-0.41) while trailing momentum was mostly negative (mean reversion), hence 25 vs 5.
DEFAULT_WEIGHTS = {
    "valuation": 25, "development": 20, "infrastructure": 15, "demographics": 15,
    "momentum": 5, "commercial": 10, "quality": 10, "flood_risk_penalty": 15,
}
FLOOD_FULL_PENALTY_SHARE = 0.5  # 50%+ of the neighborhood in the 2050s floodplain = full penalty
WEIGHTS_KEY = "score_weights"
NEUTRAL = 50.0


def get_weights(session: Session) -> dict[str, float]:
    row = session.get(AppSetting, WEIGHTS_KEY)
    return {**DEFAULT_WEIGHTS, **(row.value if row else {})}


def set_weights(session: Session, weights: dict[str, float]) -> dict[str, float]:
    clean = {k: max(float(v), 0.0) for k, v in weights.items() if k in DEFAULT_WEIGHTS}
    session.merge(AppSetting(key=WEIGHTS_KEY, value=clean))
    session.commit()
    return get_weights(session)


def load_metric_frame(session: Session) -> pd.DataFrame:
    """Wide frame (nta x metric) of raw metrics, plus derived ones used by the pillars."""
    rows = session.query(NeighborhoodMetric.nta_code, NeighborhoodMetric.metric, NeighborhoodMetric.value).all()
    hoods = session.query(Neighborhood).all()
    df = pd.DataFrame(rows, columns=["nta", "metric", "value"])
    wide = df.pivot_table(index="nta", columns="metric", values="value", aggfunc="first") if not df.empty else pd.DataFrame()
    wide = wide.reindex([h.code for h in hoods])
    meta = pd.DataFrame({"borough": [h.borough for h in hoods], "residential": [h.residential for h in hoods],
                         "area_km2": [h.area_km2 for h in hoods]}, index=[h.code for h in hoods])
    wide = wide.join(meta)

    def col(name):
        return wide[name] if name in wide else pd.Series(float("nan"), index=wide.index)

    value = col("zhvi_condo_value").fillna(col("condo_median_price"))
    wide["condo_value"] = value
    borough_median = value.groupby(wide["borough"]).transform("median")
    wide["value_gap_borough"] = 1 - value / borough_median
    neighbor_mean = pd.Series({code: value.reindex(nbrs).mean() for code, nbrs in _adjacency(hoods).items()})
    wide["value_gap_neighbors"] = 1 - value / neighbor_mean.reindex(wide.index)
    units = col("housing_units")
    wide["felonies_per_1k_units"] = (col("felonies") / units * 1000).where(units >= 500)
    licenses = col("liquor_licenses")
    wide["liquor_new_share"] = (col("liquor_licenses_new") / licenses).where(licenses >= 10)
    wide["liquor_per_km2"] = licenses / wide["area_km2"]
    return wide


def _adjacency(hoods: list[Neighborhood]) -> dict[str, list[str]]:
    geoms = [shapely.make_valid(shape(h.geometry)).buffer(0.0005) for h in hoods]  # ~50m to close slivers
    tree = shapely.STRtree(geoms)
    return {
        h.code: [hoods[j].code for j in tree.query(geoms[i], predicate="intersects") if j != i]
        for i, h in enumerate(hoods)
    }


def score_frame(wide: pd.DataFrame, weights: dict[str, float]) -> pd.DataFrame:
    res = wide[wide["residential"].astype(bool)]
    out = pd.DataFrame(index=res.index)
    details: dict[str, dict] = {code: {} for code in res.index}
    weighted_sum = pd.Series(0.0, index=res.index)
    weight_total = pd.Series(0.0, index=res.index)
    all_weight = sum(weights.get(p, 0) for p in PILLARS)

    for pillar, spec in PILLARS.items():
        pcts = {}
        for m in spec["metrics"]:
            if m.key in res and res[m.key].notna().sum() >= 10:
                pct = res[m.key].rank(pct=True, ascending=m.higher_is_better) * 100
                pcts[m.key] = pct
        pillar_score = pd.DataFrame(pcts).mean(axis=1) if pcts else pd.Series(float("nan"), index=res.index)
        w = weights.get(pillar, 0)
        has = pillar_score.notna()
        # A missing pillar counts as neutral (50) so thin data can't inflate a score; `coverage` flags it.
        weighted_sum += pillar_score.fillna(NEUTRAL) * w
        weight_total[has] += w
        for code in res.index:
            details[code][pillar] = {
                "label": spec["label"],
                "weight": w,
                "score": _r(pillar_score.get(code)),
                "metrics": {
                    m.key: {
                        "label": m.label, "fmt": m.fmt, "higher_is_better": m.higher_is_better,
                        "value": _r(res[m.key].get(code), 4) if m.key in res else None,
                        "percentile": _r(pcts[m.key].get(code)) if m.key in pcts else None,
                    }
                    for m in spec["metrics"]
                },
            }

    base = weighted_sum / all_weight if all_weight else pd.Series(float("nan"), index=res.index)
    flood = res["floodplain_2050s_pct"] if "floodplain_2050s_pct" in res else pd.Series(0.0, index=res.index)
    penalty = (flood.fillna(0) / FLOOD_FULL_PENALTY_SHARE).clip(upper=1) * weights.get("flood_risk_penalty", 0)
    out["score"] = (base - penalty).clip(lower=0, upper=100)
    out["coverage"] = weight_total / all_weight if all_weight else 0
    out["rank"] = out["score"].rank(ascending=False, method="min")
    for code in res.index:
        details[code]["flood_risk_penalty"] = {
            "label": "Flood risk penalty (2050s 100-yr floodplain)",
            "weight": weights.get("flood_risk_penalty", 0),
            "points": _r(-penalty.get(code, 0)),
            "floodplain_share": _r(flood.get(code), 4),
        }
    out["pillars"] = pd.Series(details)
    return out


def recompute_scores(session: Session) -> int:
    wide = load_metric_frame(session)
    if wide.drop(columns=["borough", "residential", "area_km2"]).dropna(how="all").empty:
        return 0
    scored = score_frame(wide, get_weights(session))
    session.execute(delete(NeighborhoodScore))
    for code, r in scored.iterrows():
        session.add(NeighborhoodScore(
            nta_code=code, score=_r(r["score"]), rank=None if pd.isna(r["rank"]) else int(r["rank"]),
            pillars=r["pillars"], coverage=float(r["coverage"]),
        ))
    session.commit()
    return len(scored)


def _r(v, digits: int = 1):
    if v is None or pd.isna(v):
        return None
    return round(float(v), digits)
