import threading
from datetime import date

import httpx
import shapely
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from shapely.geometry import mapping, shape
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.models import (
    Listing,
    ListingSnapshot,
    ListingStatus,
    Neighborhood,
    NeighborhoodMetric,
    NeighborhoodScore,
    SourceRun,
)
from app.pipeline.listings import mark_sold, sync_listings
from app.scoring import investment as inv
from app.scoring.backtest import run_backtest
from app.scoring.neighborhood import (
    DEFAULT_WEIGHTS,
    PILLARS,
    get_weights,
    load_metric_frame,
    recompute_scores,
    set_weights,
)
from app.services import MarketContext, building_sales, neighborhood_sales_stats, property_inputs, summarize
from app.sources import manual_import
from app.sources.base import SourceContext
from app.sources.registry import is_running, load_sources, run_pipeline
from app.sources.transit import load_catalysts

router = APIRouter(prefix="/api")


def db():
    with SessionLocal() as session:
        yield session


# ---------------------------------------------------------------- summary


@router.get("/summary")
def summary(session: Session = Depends(db)):
    counts = dict(session.query(Listing.status, func.count()).group_by(Listing.status).all())
    ctx = MarketContext.load(session)
    active = session.query(Listing).filter(Listing.status == ListingStatus.ACTIVE).all()
    rows = [r for r in (summarize(session, listing, ctx) for listing in active) if r["ownership"] != "likely_coop"]
    last_run = session.query(func.max(SourceRun.finished_at)).scalar()
    return {
        "active": len(rows),
        "likely_coops_hidden": len(active) - len(rows),
        "off_market": counts.get(ListingStatus.OFF_MARKET, 0),
        "sold": counts.get(ListingStatus.SOLD, 0),
        "withdrawn": counts.get(ListingStatus.WITHDRAWN, 0),
        "new": sum(1 for r in rows if r["is_new"]),
        "price_drops": sum(1 for r in rows if r["price_cuts"] > 0),
        "neighborhoods_scored": session.query(func.count(NeighborhoodScore.score)).scalar(),
        "last_refresh": last_run.isoformat() if last_run else None,
        "refreshing": is_running(),
    }


# ---------------------------------------------------------------- listings


@router.get("/listings")
def list_listings(
    status: str = "active",
    borough: str | None = None,
    neighborhood: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    min_beds: float | None = None,
    min_growth: float | None = None,
    min_cap_rate: float | None = None,
    max_days_on_market: int | None = None,
    price_cut: bool = False,
    new_only: bool = False,
    include_coops: bool = False,
    session: Session = Depends(db),
):
    statuses = [ListingStatus.OFF_MARKET, ListingStatus.SOLD, ListingStatus.WITHDRAWN] if status == "closed" else [status]
    q = session.query(Listing).filter(Listing.status.in_(statuses))
    if neighborhood:
        q = q.filter(Listing.nta_code == neighborhood)
    if min_price is not None:
        q = q.filter(Listing.price >= min_price)
    if max_price is not None:
        q = q.filter(Listing.price <= max_price)
    if min_beds is not None:
        q = q.filter(Listing.bedrooms >= min_beds)
    ctx = MarketContext.load(session)
    rows = [summarize(session, listing, ctx) for listing in q.all()]

    def keep(r):
        return ((not borough or r["borough"] == borough)
                and (min_growth is None or (r["growth_score"] or 0) >= min_growth)
                and (min_cap_rate is None or (r["cap_rate"] or -1) >= min_cap_rate)
                and (max_days_on_market is None or r["days_on_market"] <= max_days_on_market)
                and (not price_cut or r["price_cuts"] > 0)
                and (not new_only or r["is_new"])
                and (include_coops or r["ownership"] != "likely_coop"))

    rows = [r for r in rows if keep(r)]
    rows.sort(key=lambda r: (r["opportunity_score"] is None, -(r["opportunity_score"] or 0)))
    return rows


class ListingIn(BaseModel):
    address: str
    unit: str | None = None
    price: float
    listed_date: date | None = None
    bedrooms: float | None = None
    bathrooms: float | None = None
    sqft: float | None = None
    year_built: int | None = None
    common_charges: float | None = None
    property_taxes: float | None = None
    rent_estimate: float | None = None
    url: str | None = None
    notes: str | None = None


def _source_ctx(session: Session, http) -> SourceContext:
    return SourceContext(session=session, settings=get_settings(), http=http)


@router.post("/listings")
def add_listing(body: ListingIn, session: Session = Depends(db)):
    try:
        raw = manual_import.raw_from_dict(body.model_dump())
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    with httpx.Client(follow_redirects=True) as http:
        ctx = _source_ctx(session, http)
        sync_listings(session, manual_import.SOURCE_NAME, [raw], complete=False, geo=ctx.geo, http=http)
    listing = session.query(Listing).filter_by(source=manual_import.SOURCE_NAME, external_id=raw.external_id).one()
    return summarize(session, listing, MarketContext.load(session))


class CsvIn(BaseModel):
    csv: str


@router.post("/listings/import")
def import_csv(body: CsvIn, session: Session = Depends(db)):
    raws, errors = manual_import.raws_from_csv(body.csv)
    if raws:
        with httpx.Client(follow_redirects=True) as http:
            ctx = _source_ctx(session, http)
            stats = sync_listings(session, manual_import.SOURCE_NAME, raws, complete=False, geo=ctx.geo, http=http)
        return {"new": stats.new, "updated": stats.updated, "price_changes": stats.price_changes, "errors": errors}
    return {"new": 0, "updated": 0, "price_changes": 0, "errors": errors or ["No rows found"]}


def _get_listing(session: Session, listing_id: int) -> Listing:
    listing = session.get(Listing, listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")
    return listing


@router.get("/listings/{listing_id}")
def listing_detail(listing_id: int, session: Session = Depends(db)):
    return _detail(session, _get_listing(session, listing_id), None)


@router.post("/listings/{listing_id}/analyze")
def analyze_listing(listing_id: int, assumptions: dict, session: Session = Depends(db)):
    allowed = {k: v for k, v in assumptions.items() if k in inv.Assumptions.__dataclass_fields__}
    return _detail(session, _get_listing(session, listing_id), inv.Assumptions(**allowed))


def _detail(session: Session, listing: Listing, assumptions: inv.Assumptions | None) -> dict:
    ctx = MarketContext.load(session)
    score = session.get(NeighborhoodScore, listing.nta_code) if listing.nta_code else None
    bldg = building_sales(session, listing)
    return {
        **summarize(session, listing, ctx, assumptions),
        "analysis": inv.analyze(property_inputs(listing, ctx), assumptions),
        "history": [{"date": s.observed_at.isoformat(), "event": s.event, "price": s.price, "status": s.status}
                    for s in listing.snapshots],
        "building_sales": [{"date": s.sale_date.isoformat(), "unit": s.unit, "price": s.price} for s in bldg[:25]],
        "neighborhood_sales": neighborhood_sales_stats(session, listing.nta_code) if listing.nta_code else None,
        "neighborhood_score": {"score": score.score, "rank": score.rank, "pillars": score.pillars,
                               "coverage": score.coverage} if score else None,
    }


class ListingPatch(BaseModel):
    price: float | None = None
    status: str | None = None
    sold_price: float | None = None
    sold_date: date | None = None
    common_charges: float | None = None
    property_taxes: float | None = None
    rent_estimate: float | None = None
    notes: str | None = None


@router.patch("/listings/{listing_id}")
def update_listing(listing_id: int, body: ListingPatch, session: Session = Depends(db)):
    listing = _get_listing(session, listing_id)
    data = body.model_dump(exclude_unset=True)
    for key in ("common_charges", "property_taxes", "rent_estimate", "notes"):
        if key in data:
            setattr(listing, key, data[key])
    if data.get("price") and abs(data["price"] - listing.price) >= 1:
        listing.price = data["price"]
        listing.snapshots.append(ListingSnapshot(event="price_change", price=listing.price, status=listing.status))
    status = data.get("status")
    if status == ListingStatus.SOLD:
        mark_sold(listing, data.get("sold_price"), data.get("sold_date") or date.today())
    elif status in ListingStatus.ALL and status != listing.status:
        listing.status = status
        listing.off_market_date = None if status == ListingStatus.ACTIVE else (listing.off_market_date or date.today())
        listing.snapshots.append(ListingSnapshot(event=status if status != "active" else "relisted",
                                                 price=listing.price, status=status))
    session.commit()
    return summarize(session, listing, MarketContext.load(session))


@router.delete("/listings/{listing_id}")
def delete_listing(listing_id: int, session: Session = Depends(db)):
    listing = _get_listing(session, listing_id)
    if listing.source != manual_import.SOURCE_NAME:
        raise HTTPException(400, "Only manually added listings can be deleted.")
    session.delete(listing)
    session.commit()
    return {"deleted": listing_id}


# ---------------------------------------------------------------- neighborhoods


KEY_METRICS = ["condo_value", "zori_rent", "gross_rent_yield", "zhvi_cagr_10y", "floodplain_2050s_pct",
               "condo_sales_per_year"]


@router.get("/neighborhoods")
def list_neighborhoods(session: Session = Depends(db)):
    wide = load_metric_frame(session)
    listing_counts = dict(session.query(Listing.nta_code, func.count()).filter(Listing.status == "active")
                          .group_by(Listing.nta_code).all())
    out = []
    for n, s in session.query(Neighborhood, NeighborhoodScore).join(NeighborhoodScore, NeighborhoodScore.nta_code == Neighborhood.code):
        row = wide.loc[n.code] if n.code in wide.index else None
        out.append({
            "code": n.code, "name": n.name, "borough": n.borough, "score": s.score, "rank": s.rank,
            "coverage": s.coverage,
            "pillars": {k: (v.get("score") if k != "flood_risk_penalty" else v.get("points")) for k, v in s.pillars.items()},
            "metrics": {k: (None if row is None or k not in row or row[k] != row[k] else float(row[k])) for k in KEY_METRICS},
            "active_listings": listing_counts.get(n.code, 0),
        })
    out.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0)))
    return out


_geojson_cache: dict = {}


@router.get("/neighborhoods/geojson")
def neighborhoods_geojson(session: Session = Depends(db)):
    scores = {s.nta_code: s for s in session.query(NeighborhoodScore)}
    if "geoms" not in _geojson_cache:
        _geojson_cache["geoms"] = {
            n.code: (n.name, n.borough, mapping(shapely.simplify(shape(n.geometry), 0.0002, preserve_topology=True)))
            for n in session.query(Neighborhood)
        }
    features = []
    for code, (name, borough, geom) in _geojson_cache["geoms"].items():
        s = scores.get(code)
        features.append({"type": "Feature", "geometry": geom,
                         "properties": {"code": code, "name": name, "borough": borough,
                                        "score": s.score if s else None, "rank": s.rank if s else None}})
    return {"type": "FeatureCollection", "features": features}


@router.get("/neighborhoods/{code}")
def neighborhood_detail(code: str, session: Session = Depends(db)):
    n = session.get(Neighborhood, code)
    if not n:
        raise HTTPException(404, "Neighborhood not found")
    s = session.get(NeighborhoodScore, code)
    as_of = {m.metric: {"as_of": m.as_of, "source": m.source}
             for m in session.query(NeighborhoodMetric).filter(NeighborhoodMetric.nta_code == code,
                                                               ~NeighborhoodMetric.metric.like("hist_%"))}
    history = sorted(
        (int(m.metric[-4:]), m.value) for m in session.query(NeighborhoodMetric)
        .filter(NeighborhoodMetric.nta_code == code, NeighborhoodMetric.metric.like("hist_zhvi_%")))
    geom = shape(n.geometry)
    catalysts = []
    for c in load_catalysts():
        radius = float(c.get("radius_km", 0.8)) / 111.0
        if any(geom.distance(shapely.Point(lon, lat)) <= radius for lon, lat in c["points"]):
            catalysts.append({k: c.get(k) for k in ("name", "type", "status", "weight")})
    return {
        "code": n.code, "name": n.name, "borough": n.borough, "area_km2": n.area_km2,
        "score": s.score if s else None, "rank": s.rank if s else None, "coverage": s.coverage if s else None,
        "total_ranked": session.query(func.count(NeighborhoodScore.score)).scalar(),
        "pillars": s.pillars if s else {}, "metric_sources": as_of,
        "value_history": [{"year": y, "value": v} for y, v in history],
        "catalysts": catalysts, "sales": neighborhood_sales_stats(session, code),
        "active_listings": session.query(func.count(Listing.id)).filter(Listing.nta_code == code, Listing.status == "active").scalar(),
    }


# ---------------------------------------------------------------- scoring settings


@router.get("/weights")
def read_weights(session: Session = Depends(db)):
    return {"weights": get_weights(session), "defaults": DEFAULT_WEIGHTS,
            "pillars": {k: {"label": v["label"], "description": v["description"]} for k, v in PILLARS.items()}}


@router.put("/weights")
def write_weights(weights: dict[str, float], session: Session = Depends(db)):
    result = set_weights(session, weights)
    recompute_scores(session)
    return {"weights": result}


@router.get("/backtest")
def backtest(session: Session = Depends(db)):
    return run_backtest(session)


# ---------------------------------------------------------------- data sources


@router.get("/sources")
def list_sources(session: Session = Depends(db)):
    settings = get_settings()
    out = []
    for e in load_sources():
        last = session.query(SourceRun).filter(SourceRun.source == e.name).order_by(SourceRun.id.desc()).first()
        last_ok = (session.query(SourceRun).filter(SourceRun.source == e.name, SourceRun.status == "ok")
                   .order_by(SourceRun.id.desc()).first())
        out.append({
            "name": e.name, "kind": e.source.kind, "description": e.source.description, "enabled": e.enabled,
            "schedule": e.schedule, "missing_settings": [k.upper() for k in e.source.missing_requirements(settings)],
            "last_run": _run_json(last), "last_success": last_ok.finished_at.isoformat() if last_ok and last_ok.finished_at else None,
        })
    return {"sources": out, "refreshing": is_running()}


def _run_json(run: SourceRun | None):
    if not run:
        return None
    return {"status": run.status, "records": run.records, "message": run.message,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None}


class RefreshIn(BaseModel):
    sources: list[str] | None = None


@router.post("/refresh")
def refresh(body: RefreshIn | None = None):
    if is_running():
        raise HTTPException(409, "A refresh is already running.")
    names = body.sources if body else None
    threading.Thread(target=_safe_pipeline, args=(names,), daemon=True).start()
    return {"started": True, "sources": names or "all enabled"}


def _safe_pipeline(names):
    try:
        run_pipeline(names)
    except RuntimeError:
        pass

