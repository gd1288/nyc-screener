"""Joins listings with neighborhood data and the investment model for the API."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from statistics import median

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Listing, Neighborhood, NeighborhoodMetric, NeighborhoodScore, Sale
from app.pipeline.listings import days_on_market, ownership_type
from app.scoring import investment as inv
from app.valuation import comps

NEW_LISTING_DAYS = 3
COMPS_YEARS = 3


@dataclass
class MarketContext:
    """Neighborhood data loaded once per request and shared across listings."""

    names: dict[str, tuple[str, str]]
    scores: dict[str, float | None]
    metrics: dict[str, dict[str, float]]
    city_value_cagr_10y: float | None
    listing_ppsf_by_nta: dict[str, float]

    @classmethod
    def load(cls, session: Session) -> "MarketContext":
        names = {
            n.code: (n.name, n.borough)
            for n in session.query(Neighborhood.code, Neighborhood.name, Neighborhood.borough)
        }
        scores = dict(session.query(NeighborhoodScore.nta_code, NeighborhoodScore.score).all())
        metrics: dict[str, dict[str, float]] = {}
        for code, metric, value in session.query(
            NeighborhoodMetric.nta_code, NeighborhoodMetric.metric, NeighborhoodMetric.value
        ).filter(NeighborhoodMetric.metric.in_(["zori_rent", "zhvi_cagr_10y", "condo_median_price"])):
            metrics.setdefault(code, {})[metric] = value
        cagrs = [m["zhvi_cagr_10y"] for m in metrics.values() if "zhvi_cagr_10y" in m]
        ppsf: dict[str, list[float]] = {}
        for code, price, sqft in session.query(Listing.nta_code, Listing.price, Listing.sqft).filter(
            Listing.status == "active", Listing.sqft > 200
        ):
            ppsf.setdefault(code, []).append(price / sqft)
        return cls(
            names=names,
            scores=scores,
            metrics=metrics,
            city_value_cagr_10y=median(cagrs) if cagrs else None,
            listing_ppsf_by_nta={c: median(v) for c, v in ppsf.items() if len(v) >= 5},
        )


STREET_SUFFIXES = {
    "ST": "STREET",
    "AVE": "AVENUE",
    "AV": "AVENUE",
    "PL": "PLACE",
    "BLVD": "BOULEVARD",
    "RD": "ROAD",
    "DR": "DRIVE",
    "PKWY": "PARKWAY",
    "SQ": "SQUARE",
    "TER": "TERRACE",
    "LN": "LANE",
    "CT": "COURT",
    "E": "EAST",
    "W": "WEST",
    "N": "NORTH",
    "S": "SOUTH",
}


def building_address_key(address: str) -> str:
    """'15 William St, 27A' -> '15 WILLIAM STREET' (house number + normalised street, unit dropped)."""
    street = address.split(",")[0].upper().replace(".", " ")
    tokens = [STREET_SUFFIXES.get(t, t) for t in street.split()]
    return " ".join(
        t.removesuffix("TH").removesuffix("ST").removesuffix("ND").removesuffix("RD")
        if t[:1].isdigit() and i > 0
        else t
        for i, t in enumerate(tokens)
    )


def building_sales(session: Session, listing: Listing, years: int = COMPS_YEARS) -> list[Sale]:
    """Recent sales in the listing's building: same tax block (a condo's units share one) and street address."""
    if not listing.bbl:
        return []
    key = f"{listing.bbl[0]}-{int(listing.bbl[1:6])}"
    since = date.today() - timedelta(days=365 * years)
    target = building_address_key(listing.address)
    sales = (
        session.query(Sale)
        .filter(Sale.building_key == key, Sale.sale_date >= since)
        .order_by(Sale.sale_date.desc())
        .all()
    )
    return [s for s in sales if building_address_key(s.address) == target]


def price_history_stats(listing: Listing) -> dict:
    prices = [s.price for s in listing.snapshots if s.event in ("listed", "price_change", "relisted") and s.price]
    cuts = sum(1 for a, b in zip(prices, prices[1:]) if b < a)  # noqa: B905 - deliberately offset pairwise zip
    increases = sum(1 for a, b in zip(prices, prices[1:]) if b > a)  # noqa: B905 - deliberately offset pairwise zip
    last_change = max((s.observed_at for s in listing.snapshots if s.event == "price_change"), default=None)
    return {
        "price_cuts": cuts,
        "price_increases": increases,
        "price_change_pct": (listing.price / listing.original_price - 1) if listing.original_price else 0.0,
        "last_price_change": last_change.date().isoformat() if last_change else None,
        "times_relisted": sum(1 for s in listing.snapshots if s.event == "relisted"),
    }


def property_inputs(listing: Listing, ctx: MarketContext) -> inv.PropertyInputs:
    m = ctx.metrics.get(listing.nta_code or "", {})
    return inv.PropertyInputs(
        price=listing.price,
        sqft=listing.sqft,
        bedrooms=listing.bedrooms,
        common_charges=listing.common_charges,
        property_taxes=listing.property_taxes,
        rent_estimate=listing.rent_estimate,
        neighborhood_rent=m.get("zori_rent"),
        neighborhood_value_cagr_10y=m.get("zhvi_cagr_10y"),
        city_value_cagr_10y=ctx.city_value_cagr_10y,
        growth_score=ctx.scores.get(listing.nta_code or ""),
    )


def comps_ratio(listing: Listing, ctx: MarketContext, bldg_sales: list[Sale] | None) -> tuple[float | None, str | None]:
    """Listing price relative to comparable pricing, and what it was compared against."""
    estimate = comps.estimate_value(
        sqft=listing.sqft,
        nta_ppsf=ctx.listing_ppsf_by_nta.get(listing.nta_code or ""),
        building_prices=[s.price for s in bldg_sales or []],
    )
    if estimate is None:
        return None, None
    return listing.price / estimate.value, estimate.basis


def summarize(
    session: Session,
    listing: Listing,
    ctx: MarketContext,
    assumptions: inv.Assumptions | None = None,
    with_building_sales: bool = True,
) -> dict:
    analysis = inv.analyze(property_inputs(listing, ctx), assumptions)
    bldg = building_sales(session, listing) if with_building_sales else None
    ratio, ratio_basis = comps_ratio(listing, ctx, bldg)
    growth = ctx.scores.get(listing.nta_code or "")
    name, borough = ctx.names.get(listing.nta_code or "", (None, None))
    base10 = analysis["projections"]["base"]["10"]
    return {
        "id": listing.id,
        "source": listing.source,
        "url": listing.url,
        "address": listing.address,
        "unit": listing.unit,
        "neighborhood_code": listing.nta_code,
        "neighborhood": name,
        "borough": borough,
        "latitude": listing.latitude,
        "longitude": listing.longitude,
        "price": listing.price,
        "original_price": listing.original_price,
        "bedrooms": listing.bedrooms,
        "bathrooms": listing.bathrooms,
        "sqft": listing.sqft,
        "price_per_sqft": round(listing.price / listing.sqft) if listing.sqft else None,
        "year_built": listing.year_built,
        "status": listing.status,
        "ownership": ownership_type(listing.bbl),
        "listed_date": listing.listed_date.isoformat(),
        "first_seen": listing.first_seen.isoformat(),
        "is_new": listing.first_seen >= datetime.now() - timedelta(days=NEW_LISTING_DAYS),
        "days_on_market": days_on_market(listing),
        "off_market_date": listing.off_market_date.isoformat() if listing.off_market_date else None,
        "sold_date": listing.sold_date.isoformat() if listing.sold_date else None,
        "sold_price": listing.sold_price,
        "sold_vs_list_pct": (listing.sold_price / listing.price - 1) if listing.sold_price else None,
        "sold_vs_original_pct": (listing.sold_price / listing.original_price - 1) if listing.sold_price else None,
        **price_history_stats(listing),
        "growth_score": growth,
        "gross_yield": analysis["gross_yield"],
        "cap_rate": analysis["cap_rate"],
        "cash_on_cash": analysis["cash_on_cash"],
        "monthly_cash_flow": analysis["monthly"]["cash_flow"],
        "irr_10y_base": base10["irr"],
        "comps_ratio": ratio,
        "comps_basis": ratio_basis,
        "opportunity_score": inv.opportunity_score(
            growth, inv.value_score(ratio), inv.yield_score(analysis["cap_rate"])
        ),
        "estimated_fields": analysis["estimated_fields"],
        "notes": listing.notes,
    }


def neighborhood_sales_stats(session: Session, nta_code: str) -> dict:
    since = date.today() - timedelta(days=365 * 2)
    rows = session.execute(
        select(func.count(), func.min(Sale.sale_date), func.max(Sale.sale_date)).where(
            Sale.nta_code == nta_code, Sale.sale_date >= since
        )
    ).one()
    prices = [p for (p,) in session.query(Sale.price).filter(Sale.nta_code == nta_code, Sale.sale_date >= since)]
    return {
        "sales_2y": rows[0],
        "median_price_2y": median(prices) if prices else None,
        "first": rows[1].isoformat() if rows[1] else None,
        "last": rows[2].isoformat() if rows[2] else None,
    }
