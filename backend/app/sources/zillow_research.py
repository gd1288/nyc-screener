"""Zillow Research public CSVs: condo home values (ZHVI) and rents (ZORI) by ZIP, mapped to neighborhoods.

ZIPs are mapped to NTAs using where DOF condo sales in each ZIP actually fall, weighted by sale count.
"""

import io

import pandas as pd
from sqlalchemy import func, select

from app.models import Sale
from app.sources.base import Source, SourceContext, SourceSkipped

BASE = "https://files.zillowstatic.com/research/public_csvs"
ZHVI_URL = f"{BASE}/zhvi/Zip_zhvi_uc_condo_tier_0.33_0.67_sm_sa_month.csv"
ZORI_URL = f"{BASE}/zori/Zip_zori_uc_sfrcondomfr_sm_month.csv"
NYC_COUNTIES = {"New York County", "Kings County", "Queens County", "Bronx County", "Richmond County"}


def zip_to_nta_weights(ctx: SourceContext) -> pd.DataFrame:
    rows = ctx.session.execute(
        select(Sale.zip_code, Sale.nta_code, func.count())
        .where(Sale.zip_code.is_not(None), Sale.nta_code.is_not(None))
        .group_by(Sale.zip_code, Sale.nta_code)
    ).all()
    if not rows:
        raise SourceSkipped("Needs condo sales loaded first (dof_condo_sales).")
    w = pd.DataFrame(rows, columns=["zip", "nta_code", "n"])
    w["weight"] = w["n"] / w.groupby("nta_code")["n"].transform("sum")
    return w


def load_zip_series(ctx: SourceContext, url: str) -> pd.DataFrame:
    """Returns a (zip x month) wide frame for NYC ZIPs."""
    resp = ctx.http.get(url, timeout=300)
    resp.raise_for_status()
    df = pd.read_csv(io.BytesIO(resp.content), dtype={"RegionName": str})
    df = df[(df["State"] == "NY") & df["CountyName"].isin(NYC_COUNTIES)]
    df = df.set_index(df["RegionName"].str.zfill(5))
    months = [c for c in df.columns if c[:2] in ("19", "20")]
    wide = df[months]
    wide.columns = pd.to_datetime(wide.columns)
    return wide


def to_nta(zip_values: pd.Series, weights: pd.DataFrame) -> pd.Series:
    """Weighted average of ZIP values per NTA, over the ZIPs that have data."""
    m = weights.merge(zip_values.rename("v"), left_on="zip", right_index=True).dropna(subset=["v"])
    m["wv"] = m["v"] * m["weight"]
    g = m.groupby("nta_code")
    return g["wv"].sum() / g["weight"].sum()


def cagr(end: pd.Series, start: pd.Series, years: float) -> pd.Series:
    return ((end / start) ** (1 / years) - 1).dropna()


class ZillowResearch(Source):
    kind = "neighborhood"
    description = "Zillow Research ZHVI (condo values) and ZORI (rents) by ZIP, 2000-present"

    def run(self, ctx: SourceContext) -> int:
        weights = zip_to_nta_weights(ctx)
        zhvi = load_zip_series(ctx, ZHVI_URL)
        zori = load_zip_series(ctx, ZORI_URL)

        yearly = zhvi.T.groupby(zhvi.columns.year).mean().T  # zip x year
        last_year = int(yearly.columns.max()) if zhvi.columns.max().month == 12 else int(yearly.columns.max()) - 1
        by_year = {y: to_nta(yearly[y], weights) for y in yearly.columns if y <= last_year}
        latest_value = to_nta(zhvi.iloc[:, -1], weights)
        latest_rent = to_nta(zori.iloc[:, -1], weights)
        rent_3y_ago = to_nta(zori.iloc[:, -37], weights) if zori.shape[1] > 36 else pd.Series(dtype=float)

        metrics = {
            "zhvi_condo_value": latest_value.to_dict(),
            "zhvi_cagr_5y": cagr(by_year[last_year], by_year[last_year - 5], 5).to_dict(),
            "zhvi_cagr_10y": cagr(by_year[last_year], by_year[last_year - 10], 10).to_dict(),
            "zori_rent": latest_rent.to_dict(),
            "zori_cagr_3y": cagr(latest_rent, rent_3y_ago, 3).to_dict(),
            "gross_rent_yield": (latest_rent * 12 / latest_value).dropna().to_dict(),
        }
        as_of_month = zhvi.columns.max().strftime("%Y-%m")
        as_of = {
            "zhvi_condo_value": as_of_month,
            "zhvi_cagr_5y": f"{last_year - 5}-{last_year}",
            "zhvi_cagr_10y": f"{last_year - 10}-{last_year}",
            "zori_rent": zori.columns.max().strftime("%Y-%m"),
            "zori_cagr_3y": f"3y to {zori.columns.max():%Y-%m}",
            "gross_rent_yield": as_of_month,
        }
        # Annual history, used by the backtest.
        for y, series in by_year.items():
            metrics[f"hist_zhvi_{y}"] = series.to_dict()
            as_of[f"hist_zhvi_{y}"] = str(y)
        return self.write_metrics(ctx, metrics, as_of)

