"""Growth Score for any US area, ranked within its own metro.

The one rule that makes a national score mean anything: **percentiles are computed inside a
comparison set**, never across the whole table. Ranking a Manhattan tract against a Bastrop County
tract measures the gap between two housing markets, not between two neighbourhoods, and it would
make every NYC area look strong and every Austin area look weak regardless of local momentum. The
set each score was computed in is stored on the row (`AreaScore.comparison_set`), so a score can
never later be mistaken for a national one.

`PILLARS` declares the *target* set of signals, including pillars whose national sources are not
wired yet. That is deliberate and is what makes `coverage` readable: a pillar with no data scores
neutral (50) and lowers coverage, so an area backed by one pillar out of four reports 0.25 rather
than presenting a confident number built on a quarter of the evidence. Adding a source means its
pillar starts contributing; nothing here needs to change.
"""

from dataclasses import dataclass

import pandas as pd
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import Area, AreaMetric, AreaScore
from app.pipeline.areas import comparison_set_for

NEUTRAL = 50.0
MIN_AREAS_FOR_PERCENTILE = 5  # below this a "percentile" is just the ordering of a handful of rows


@dataclass(frozen=True)
class MetricDef:
    key: str
    label: str
    higher_is_better: bool = True


PILLARS: dict[str, dict] = {
    "momentum": {
        "label": "Price momentum",
        "description": "How fast home values have grown, from the FHFA tract index.",
        "source": "fhfa_tract_hpi",
        "metrics": [
            MetricDef("hpi_cagr_5y", "Home value growth per year, 5 yrs"),
            MetricDef("hpi_cagr_10y", "Home value growth per year, 10 yrs"),
            MetricDef("hpi_annual_change", "Home value change, latest year"),
        ],
    },
    "demographics": {
        "label": "Demographic shift",
        "description": "Population, income and education rising.",
        "source": "census_acs (not yet writing area metrics)",
        "metrics": [
            MetricDef("population_change_10y", "Population change, 10 yrs"),
            MetricDef("income_cagr_10y", "Household income growth per year, 10 yrs"),
            MetricDef("bachelors_share_change_10y", "Change in bachelor's-degree share, 10 yrs"),
        ],
    },
    "accessibility": {
        "label": "Walkability & access",
        "description": "How much is reachable without a car.",
        "source": "epa_walkability (not yet wired)",
        "metrics": [MetricDef("walkability_index", "EPA National Walkability Index")],
    },
    "risk": {
        "label": "Climate & hazard risk",
        "description": "Expected annual loss from natural hazards.",
        "source": "fema_nri (not yet wired)",
        "metrics": [MetricDef("fema_risk_index", "FEMA National Risk Index", higher_is_better=False)],
    },
}

DEFAULT_WEIGHTS = {"momentum": 30, "demographics": 30, "accessibility": 20, "risk": 20}


def load_area_frame(session: Session, comparison_set: str) -> pd.DataFrame:
    """Wide frame (area x metric) for one comparison set, residential areas only."""
    areas = [a for a in session.query(Area) if comparison_set_for(a) == comparison_set and a.residential]
    if not areas:
        return pd.DataFrame()
    ids = {a.id: a.code for a in areas}
    rows = session.query(AreaMetric.area_id, AreaMetric.metric, AreaMetric.value).filter(
        AreaMetric.area_id.in_(list(ids))
    )
    frame = pd.DataFrame(
        [(ids[area_id], metric, value) for area_id, metric, value in rows], columns=["code", "metric", "value"]
    )
    wide = (
        frame.pivot_table(index="code", columns="metric", values="value", aggfunc="first")
        if not frame.empty
        else pd.DataFrame()
    )
    return wide.reindex([a.code for a in areas])


def score_frame(wide: pd.DataFrame, weights: dict[str, float] | None = None) -> pd.DataFrame:
    weights = weights or DEFAULT_WEIGHTS
    out = pd.DataFrame(index=wide.index)
    details: dict[str, dict] = {code: {} for code in wide.index}
    weighted_sum = pd.Series(0.0, index=wide.index)
    backed_weight = pd.Series(0.0, index=wide.index)
    total_weight = sum(weights.get(pillar, 0) for pillar in PILLARS)

    for pillar, spec in PILLARS.items():
        percentiles = {}
        for metric in spec["metrics"]:
            if metric.key in wide and wide[metric.key].notna().sum() >= MIN_AREAS_FOR_PERCENTILE:
                percentiles[metric.key] = wide[metric.key].rank(pct=True, ascending=metric.higher_is_better) * 100
        pillar_score = (
            pd.DataFrame(percentiles).mean(axis=1) if percentiles else pd.Series(float("nan"), index=wide.index)
        )
        weight = weights.get(pillar, 0)
        # Neutral, not dropped: thin data must not be able to inflate a score, and `coverage`
        # is what records that the neutral value was a guess rather than a measurement.
        weighted_sum += pillar_score.fillna(NEUTRAL) * weight
        backed_weight[pillar_score.notna()] += weight
        for code in wide.index:
            details[code][pillar] = {
                "label": spec["label"],
                "weight": weight,
                "score": _round(pillar_score.get(code)),
                "source": spec["source"],
                "metrics": {
                    m.key: {
                        "label": m.label,
                        "higher_is_better": m.higher_is_better,
                        "value": _round(wide[m.key].get(code), 6) if m.key in wide else None,
                        "percentile": _round(percentiles[m.key].get(code)) if m.key in percentiles else None,
                    }
                    for m in spec["metrics"]
                },
            }

    out["score"] = (weighted_sum / total_weight).clip(lower=0, upper=100) if total_weight else float("nan")
    out["coverage"] = backed_weight / total_weight if total_weight else 0.0
    out["rank"] = out["score"].rank(ascending=False, method="min")
    out["pillars"] = pd.Series(details)
    return out


def recompute_area_scores(session: Session, comparison_set: str | None = None) -> int:
    """Score every comparison set (or just one). Each set is ranked independently."""
    sets = (
        [comparison_set]
        if comparison_set
        else sorted({comparison_set_for(a) for a in session.query(Area) if a.residential})
    )
    scored_total = 0
    for target in sets:
        wide = load_area_frame(session, target)
        if wide.empty:
            continue
        scored = score_frame(wide)
        codes = {a.code: a.id for a in session.query(Area) if comparison_set_for(a) == target}
        session.execute(delete(AreaScore).where(AreaScore.comparison_set == target))
        for code, row in scored.iterrows():
            session.add(
                AreaScore(
                    area_id=codes[code],
                    comparison_set=target,
                    score=_round(row["score"]),
                    rank=None if pd.isna(row["rank"]) else int(row["rank"]),
                    pillars=row["pillars"],
                    coverage=float(row["coverage"]),
                )
            )
            scored_total += 1
        session.commit()
    return scored_total


def _round(value, digits: int = 1):
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)
