"""Does the score's price-based logic predict the next 10 years? Uses Zillow condo value history by NTA.

For each base year B we compute, with only data available at B:
  - valuation gap: discount of the NTA's condo value to its borough median
  - momentum: value growth per year over the 5 years before B
  - combined: the average of the two percentile ranks (the price pillars of the growth score)
and compare each with the NTA's actual value growth per year from B to B+10 (Spearman rank correlation).
The non-price pillars (permits, census, crime) aren't backtested yet: they lack a clean 10-year history here.
"""

from datetime import date

import pandas as pd
from sqlalchemy.orm import Session

from app.models import Neighborhood, NeighborhoodMetric


def run_backtest(session: Session, base_years: list[int] | None = None) -> dict:
    rows = (session.query(NeighborhoodMetric.nta_code, NeighborhoodMetric.metric, NeighborhoodMetric.value)
            .filter(NeighborhoodMetric.metric.like("hist_zhvi_%")).all())
    if not rows:
        return {"error": "No value history yet; run the zillow_research source first."}
    df = pd.DataFrame(rows, columns=["nta", "metric", "value"])
    df["year"] = df["metric"].str[-4:].astype(int)
    values = df.pivot_table(index="nta", columns="year", values="value")
    borough = pd.Series({n.code: n.borough for n in session.query(Neighborhood)})
    last_year = int(values.columns.max())
    base_years = base_years or [y for y in (2008, 2010, 2012, 2014) if y + 10 <= last_year and y - 5 >= values.columns.min()]

    results = []
    for b in base_years:
        v = values[[b - 5, b, b + 10]].dropna()
        gap = 1 - v[b] / v[b].groupby(borough.reindex(v.index)).transform("median")
        momentum = (v[b] / v[b - 5]) ** (1 / 5) - 1
        outcome = (v[b + 10] / v[b]) ** (1 / 10) - 1
        combined = (gap.rank(pct=True) + momentum.rank(pct=True)) / 2
        top = outcome[combined >= combined.quantile(0.8)].median()
        bottom = outcome[combined <= combined.quantile(0.2)].median()
        results.append({
            "base_year": b,
            "horizon": f"{b}-{b + 10}",
            "neighborhoods": int(len(v)),
            "spearman_valuation_gap": _spearman(gap, outcome),
            "spearman_momentum": _spearman(momentum, outcome),
            "spearman_combined": _spearman(combined, outcome),
            "top_quintile_growth": round(float(top), 4),
            "bottom_quintile_growth": round(float(bottom), 4),
        })
    return {"generated": date.today().isoformat(), "method": __doc__.strip(), "results": results}


def _spearman(a: pd.Series, b: pd.Series) -> float:
    return round(float(a.rank().corr(b.rank())), 3)
