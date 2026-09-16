"""DOF Citywide Annualized Calendar Sales (condo units) -> sales table + price metrics."""

from datetime import date

import numpy as np
import pandas as pd
from sqlalchemy import delete

from app.models import Sale
from app.sources import socrata
from app.sources.base import Source, SourceContext

# Residential condo unit categories (the dataset has variants with a double space).
CONDO_CATEGORIES = ["04 TAX CLASS 1 CONDOS", "12 CONDOS - WALKUP APARTMENTS", "13 CONDOS - ELEVATOR APARTMENTS",
                    "15 CONDOS - 2-10 UNIT RESIDENTIAL", "16 CONDOS - 2-10 UNIT WITH COMMERCIAL UNIT"]
MIN_ARMS_LENGTH_PRICE = 100_000  # below this, sales are usually family transfers / non-market deeds
MIN_SALES_FOR_STAT = 15


def _category_filter() -> str:
    variants = []
    for c in CONDO_CATEGORIES:
        code, rest = c.split(" ", 1)
        variants += [f"'{code} {rest}'", f"'{code}  {rest}'"]
    return f"building_class_category in ({', '.join(variants)})"


def repeat_sales_cagr(df: pd.DataFrame) -> pd.Series:
    """Median annualised appreciation per NTA from units that sold twice (>= 2 years apart)."""
    df = df.sort_values("sale_date")
    prev = df.groupby("bbl")[["price", "sale_date"]].shift(1)
    years = (df["sale_date"] - prev["sale_date"]).dt.days / 365.25
    pairs = df.assign(years=years, ratio=df["price"] / prev["price"]).dropna(subset=["years"])
    pairs = pairs[(pairs["years"] >= 2) & pairs["ratio"].between(0.33, 3)]  # drop likely non-market pairs
    pairs = pairs.assign(cagr=pairs["ratio"] ** (1 / pairs["years"]) - 1)
    grouped = pairs.groupby("nta_code")["cagr"]
    return grouped.median()[grouped.count() >= MIN_SALES_FOR_STAT]


class DofCondoSales(Source):
    kind = "sales"
    description = "NYC Dept. of Finance annualized sales, residential condo units (2016-present)"

    def run(self, ctx: SourceContext) -> int:
        rows = socrata.nyc(
            ctx.http,
            self.options.get("dataset", "w2pb-icbu"),
            ctx.settings.socrata_app_token,
            select="bbl,borough,block,address,apartment_number,zip_code,sale_price,sale_date,year_built,"
            "building_class_category,latitude,longitude,nta",
            where=f"{_category_filter()} and sale_date >= '{self.options.get('since', '2016-01-01')}'",
            order="sale_date,bbl",
        )
        df = pd.DataFrame(list(rows))
        if df.empty:
            return 0
        df["price"] = pd.to_numeric(df["sale_price"], errors="coerce")
        df = df[df["price"] >= MIN_ARMS_LENGTH_PRICE].copy()
        df["sale_date"] = pd.to_datetime(df["sale_date"])
        for col in ("latitude", "longitude", "year_built"):
            df[col] = pd.to_numeric(df.get(col), errors="coerce")
        df = df.dropna(subset=["bbl"]).drop_duplicates(subset=["bbl", "sale_date", "price"])
        # Recompute NTA from coordinates so codes always match our boundary table.
        df["nta_code"] = ctx.geo.lookup_many(df["longitude"], df["latitude"])
        df["nta_code"] = df["nta_code"].fillna(df.get("nta"))

        ctx.session.execute(delete(Sale).where(Sale.source == self.name))
        ctx.session.bulk_insert_mappings(
            Sale,
            [
                dict(
                    bbl=r.bbl, building_key=f"{r.borough}-{r.block}", address=r.address, unit=r.apartment_number or None,
                    zip_code=(r.zip_code or None), nta_code=r.nta_code, price=r.price, sale_date=r.sale_date.date(),
                    year_built=None if np.isnan(r.year_built) or r.year_built == 0 else int(r.year_built),
                    category=" ".join(r.building_class_category.split()), latitude=_nan(r.latitude),
                    longitude=_nan(r.longitude), source=self.name,
                )
                for r in df.itertuples()
            ],
        )
        ctx.session.commit()
        self._write_price_metrics(ctx, df)
        return len(df)

    def _write_price_metrics(self, ctx: SourceContext, df: pd.DataFrame) -> None:
        df = df.dropna(subset=["nta_code"]).assign(year=lambda d: d["sale_date"].dt.year)
        last_full_year = date.today().year - 1
        latest_year = int(min(df["year"].max(), last_full_year))
        recent = df[df["year"] >= latest_year - 1]  # two years of sales for a stable median
        base = df[df["year"].between(latest_year - 6, latest_year - 5)]

        def medians(frame):
            g = frame.groupby("nta_code")["price"]
            return g.median()[g.count() >= MIN_SALES_FOR_STAT]

        med_recent, med_base = medians(recent), medians(base)
        growth = ((med_recent / med_base) ** (1 / 5) - 1).dropna()
        vol_recent = recent.groupby("nta_code").size() / 2
        vol_base = base.groupby("nta_code").size() / 2
        volume_change = (vol_recent / vol_base - 1).dropna()

        span = f"{latest_year - 1}-{latest_year}"
        self.write_metrics(
            ctx,
            {
                "condo_median_price": med_recent.to_dict(),
                "condo_median_price_cagr_5y": growth.to_dict(),
                "condo_repeat_sales_cagr": repeat_sales_cagr(df).to_dict(),
                "condo_sales_per_year": vol_recent.to_dict(),
                "condo_sales_volume_change_5y": volume_change.to_dict(),
            },
            as_of={
                "condo_median_price": span,
                "condo_median_price_cagr_5y": f"{latest_year - 6}-{latest_year}",
                "condo_repeat_sales_cagr": f"{df['year'].min()}-{df['year'].max()}",
                "condo_sales_per_year": span,
                "condo_sales_volume_change_5y": f"{latest_year - 6}-{latest_year}",
            },
        )


def _nan(v):
    return None if v is None or v != v else float(v)
