"""Valuation API: save a property, look up an address, run the cash-flow engine, explore
scenarios/sensitivity/a two-factor data table/Monte Carlo against it, and export it as a live
Excel model.
"""

import json
from dataclasses import asdict

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Listing, ListingStatus, Neighborhood, ValuationProperty
from app.pipeline.listings import ownership_type
from app.services import MarketContext
from app.valuation import engine
from app.valuation import scenarios as scenarios_mod
from app.valuation.factors import FACTOR_DEFS, PropertyProfile
from app.valuation.property import lookup_address

router = APIRouter(prefix="/api/valuation")


def db():
    with SessionLocal() as session:
        yield session


@router.get("/factors")
def list_factors():
    return [{"key": f.key, "label": f.label} for f in FACTOR_DEFS]


class LookupIn(BaseModel):
    address: str


@router.post("/lookup")
def lookup(body: LookupIn, session: Session = Depends(db)):
    with httpx.Client() as http:
        result = lookup_address(session, body.address, http)
    if result is None:
        raise HTTPException(404, "Couldn't geocode that address")
    return {
        "address": result.address,
        "latitude": result.latitude,
        "longitude": result.longitude,
        "nta_code": result.nta_code,
        "neighborhood_name": result.neighborhood_name,
    }


class PropertyIn(BaseModel):
    label: str
    property_type: str = "condo"
    address: str | None = None
    nta_code: str | None = None
    price: float = Field(gt=0)
    sqft: float | None = None
    bedrooms: float | None = None
    common_charges: float | None = None
    property_taxes: float | None = None
    rent_estimate: float | None = None
    assumption_overrides: dict[str, float] = {}


class PropertyPatch(BaseModel):
    """Same fields as PropertyIn, all optional - PATCH only touches fields the caller actually sent
    (`exclude_unset`), so omitting a field leaves it as-is instead of wiping it to `None`."""

    label: str | None = None
    property_type: str | None = None
    address: str | None = None
    nta_code: str | None = None
    price: float | None = Field(default=None, gt=0)
    sqft: float | None = None
    bedrooms: float | None = None
    common_charges: float | None = None
    property_taxes: float | None = None
    rent_estimate: float | None = None
    assumption_overrides: dict[str, float] | None = None


def _check_nta_code(session: Session, nta_code: str | None) -> None:
    if nta_code and session.get(Neighborhood, nta_code) is None:
        raise HTTPException(422, f"Unknown neighborhood code: {nta_code}")


def _to_profile(row: ValuationProperty) -> PropertyProfile:
    return PropertyProfile(
        price=row.price,
        property_type=row.property_type,
        address=row.address,
        nta_code=row.nta_code,
        sqft=row.sqft,
        bedrooms=row.bedrooms,
        common_charges=row.common_charges,
        property_taxes=row.property_taxes,
        rent_estimate=row.rent_estimate,
    )


def _row_dict(row: ValuationProperty, listing: Listing | None = None) -> dict:
    return {
        "id": row.id,
        "label": row.label,
        "property_type": row.property_type,
        "address": row.address,
        "nta_code": row.nta_code,
        "price": row.price,
        "sqft": row.sqft,
        "bedrooms": row.bedrooms,
        "common_charges": row.common_charges,
        "property_taxes": row.property_taxes,
        "rent_estimate": row.rent_estimate,
        "assumption_overrides": row.assumption_overrides,
        "listing_id": row.listing_id,
        # Live state of the screener listing this came from, so a saved valuation can say "the ask
        # has dropped 4% since you imported this" rather than quietly analysing a stale price.
        "listing": (
            {
                "id": listing.id,
                "status": listing.status,
                "price": listing.price,
                "url": listing.url,
                "price_drift_pct": (listing.price / row.price - 1) if row.price else None,
            }
            if listing is not None
            else None
        ),
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _listings_for(session: Session, rows: list[ValuationProperty]) -> dict[int, Listing]:
    ids = {r.listing_id for r in rows if r.listing_id}
    if not ids:
        return {}
    return {listing.id: listing for listing in session.query(Listing).filter(Listing.id.in_(ids))}


def _get(session: Session, property_id: int) -> ValuationProperty:
    row = session.get(ValuationProperty, property_id)
    if row is None:
        raise HTTPException(404, "No such valuation property")
    return row


@router.get("/properties")
def list_properties(session: Session = Depends(db)):
    rows = session.query(ValuationProperty).order_by(ValuationProperty.updated_at.desc()).all()
    listings = _listings_for(session, rows)
    return [_row_dict(r, listings.get(r.listing_id) if r.listing_id else None) for r in rows]


@router.get("/importable-listings")
def importable_listings(q: str | None = None, limit: int = 25, session: Session = Depends(db)):
    """Active screener listings that can be pulled into the valuation tab, newest first.

    Co-ops are included here (unlike the screener's default view, which hides them): if you've
    gone to the trouble of opening the import picker, you're choosing a specific property to
    analyse, and the engine handles a co-op's economics the same way.
    """
    query = session.query(Listing).filter(Listing.status == ListingStatus.ACTIVE)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(Listing.address.ilike(like))
    rows = query.order_by(Listing.first_seen.desc()).limit(min(max(limit, 1), 100)).all()
    imported = {
        listing_id
        for (listing_id,) in session.query(ValuationProperty.listing_id).filter(
            ValuationProperty.listing_id.isnot(None)
        )
    }
    return [
        {
            "id": listing.id,
            "address": listing.address,
            "unit": listing.unit,
            "neighborhood_code": listing.nta_code,
            "price": listing.price,
            "bedrooms": listing.bedrooms,
            "sqft": listing.sqft,
            "ownership": ownership_type(listing.bbl),
            "already_imported": listing.id in imported,
        }
        for listing in rows
    ]


@router.post("/properties/from-listing/{listing_id}")
def create_from_listing(listing_id: int, session: Session = Depends(db)):
    """Create a valuation property from a screener listing, carrying over everything the engine
    can use. Keeps `listing_id` so the valuation stays linked to the live listing."""
    listing = session.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(404, "No such listing")
    label = f"{listing.address}{f' #{listing.unit}' if listing.unit else ''}"
    row = ValuationProperty(
        label=label[:120],
        property_type="coop" if ownership_type(listing.bbl) == "likely_coop" else "condo",
        listing_id=listing.id,
        address=listing.address,
        nta_code=listing.nta_code,
        price=listing.price,
        sqft=listing.sqft,
        bedrooms=listing.bedrooms,
        common_charges=listing.common_charges,
        property_taxes=listing.property_taxes,
        rent_estimate=listing.rent_estimate,
        assumption_overrides={},
    )
    session.add(row)
    session.commit()
    return _row_dict(row, listing)


@router.post("/properties/{property_id}/resync-from-listing")
def resync_from_listing(property_id: int, session: Session = Depends(db)):
    """Pull the linked listing's current facts back onto the saved property. Only refreshes the
    property's own facts - assumption overrides (your scenario work) are left alone."""
    row = _get(session, property_id)
    if not row.listing_id:
        raise HTTPException(422, "This valuation isn't linked to a screener listing")
    listing = session.get(Listing, row.listing_id)
    if listing is None:
        raise HTTPException(404, "The linked listing no longer exists")
    row.price = listing.price
    row.sqft = listing.sqft
    row.bedrooms = listing.bedrooms
    row.common_charges = listing.common_charges
    row.property_taxes = listing.property_taxes
    row.rent_estimate = listing.rent_estimate
    row.nta_code = listing.nta_code
    session.commit()
    return _row_dict(row, listing)


@router.post("/properties")
def create_property(body: PropertyIn, session: Session = Depends(db)):
    _check_nta_code(session, body.nta_code)
    row = ValuationProperty(**body.model_dump())
    session.add(row)
    session.commit()
    return _row_dict(row)


@router.get("/properties/{property_id}")
def get_property(property_id: int, session: Session = Depends(db)):
    row = _get(session, property_id)
    return _row_dict(row, session.get(Listing, row.listing_id) if row.listing_id else None)


@router.patch("/properties/{property_id}")
def update_property(property_id: int, body: PropertyPatch, session: Session = Depends(db)):
    row = _get(session, property_id)
    fields = body.model_dump(exclude_unset=True)
    if "nta_code" in fields:
        _check_nta_code(session, fields["nta_code"])
    for k, v in fields.items():
        setattr(row, k, v)
    session.commit()
    return _row_dict(row, session.get(Listing, row.listing_id) if row.listing_id else None)


@router.delete("/properties/{property_id}")
def delete_property(property_id: int, session: Session = Depends(db)):
    session.delete(_get(session, property_id))
    session.commit()
    return {"ok": True}


PROFILE_OVERRIDE_FIELDS = {"price", "sqft", "bedrooms", "common_charges", "property_taxes", "rent_estimate"}


class RunIn(BaseModel):
    overrides: dict[str, float] = {}  # Assumptions fields, e.g. interest_rate, appreciation_override
    property_overrides: dict[
        str, float
    ] = {}  # PropertyProfile fields, e.g. price, rent_estimate - "what if" only, not saved


def _resolve_run_inputs(
    session: Session, property_id: int, overrides: dict[str, float], property_overrides: dict[str, float]
) -> tuple[PropertyProfile, MarketContext, dict[str, float]]:
    if unknown := set(property_overrides) - PROFILE_OVERRIDE_FIELDS:
        raise HTTPException(422, f"Unknown property override field(s): {sorted(unknown)}")
    row = _get(session, property_id)
    ctx = MarketContext.load(session)
    profile = _to_profile(row)
    for k, v in property_overrides.items():
        setattr(profile, k, v)
    merged_overrides = {**row.assumption_overrides, **overrides}
    return profile, ctx, merged_overrides


@router.post("/properties/{property_id}/run")
def run_property(property_id: int, body: RunIn, session: Session = Depends(db)):
    profile, ctx, merged_overrides = _resolve_run_inputs(session, property_id, body.overrides, body.property_overrides)
    try:
        return engine.run(profile, ctx, merged_overrides)
    except engine.UnknownOverrideError as e:
        raise HTTPException(422, str(e)) from e


class ScenarioIn(BaseModel):
    name: str
    deltas: dict[str, float] = {}


class CompareIn(BaseModel):
    overrides: dict[str, float] = {}
    property_overrides: dict[str, float] = {}
    scenarios: list[ScenarioIn] | None = (
        None  # omit to use the built-in presets (Bear/Base/Bull/Higher rates/Recession)
    )


@router.post("/properties/{property_id}/scenarios/compare")
def compare_scenarios(property_id: int, body: CompareIn, session: Session = Depends(db)):
    profile, ctx, merged_overrides = _resolve_run_inputs(session, property_id, body.overrides, body.property_overrides)
    scenario_dicts = [s.model_dump() for s in body.scenarios] if body.scenarios is not None else None
    try:
        results = scenarios_mod.compare(profile, ctx, merged_overrides, scenario_dicts)
    except engine.UnknownOverrideError as e:
        raise HTTPException(422, str(e)) from e
    return [asdict(r) for r in results]


class SensitivityIn(BaseModel):
    overrides: dict[str, float] = {}
    property_overrides: dict[str, float] = {}
    horizon: str = "10"


@router.post("/properties/{property_id}/sensitivity")
def sensitivity(property_id: int, body: SensitivityIn, session: Session = Depends(db)):
    if body.horizon not in ("10", "20"):
        raise HTTPException(422, "horizon must be '10' or '20'")
    profile, ctx, merged_overrides = _resolve_run_inputs(session, property_id, body.overrides, body.property_overrides)
    return scenarios_mod.sensitivity(profile, ctx, merged_overrides, body.horizon)


class DataTableIn(BaseModel):
    overrides: dict[str, float] = {}
    property_overrides: dict[str, float] = {}
    x_factor: str = "interest_rate"
    y_factor: str = "appreciation_override"
    steps: int = 5
    horizon: str = "10"


@router.post("/properties/{property_id}/data-table")
def data_table(property_id: int, body: DataTableIn, session: Session = Depends(db)):
    if body.horizon not in ("10", "20"):
        raise HTTPException(422, "horizon must be '10' or '20'")
    if unknown := {body.x_factor, body.y_factor} - engine.ASSUMPTION_FIELDS:
        raise HTTPException(422, f"Unknown Assumptions field(s): {sorted(unknown)}")
    steps = min(max(body.steps, 3), 9)
    profile, ctx, merged_overrides = _resolve_run_inputs(session, property_id, body.overrides, body.property_overrides)
    x_values = scenarios_mod.default_data_table_axis(profile, ctx, merged_overrides, body.x_factor, steps)
    y_values = scenarios_mod.default_data_table_axis(profile, ctx, merged_overrides, body.y_factor, steps)
    return scenarios_mod.data_table(
        profile, ctx, merged_overrides, body.x_factor, body.y_factor, x_values, y_values, body.horizon
    )


XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _safe_filename(label: str) -> str:
    """ASCII, no quotes or separators - a label goes into a Content-Disposition header, and labels
    are free text the user typed."""
    cleaned = "".join(c if c.isalnum() or c in " -_" else "_" for c in label).strip() or "valuation"
    return f"{cleaned[:60].replace(' ', '-')}.xlsx"


def _parse_override_param(raw: str | None, allowed: set[str], what: str) -> dict[str, float]:
    """Decode an `overrides` query parameter. It is a GET (not a POST) so the export can stay a
    plain `<a download>` link, which means the on-screen scenario has to travel in the URL."""
    if not raw:
        return {}
    if len(raw) > 4000:
        raise HTTPException(422, f"{what} parameter is too large")
    try:
        parsed = json.loads(raw)
    except ValueError as e:
        raise HTTPException(422, f"{what} must be JSON") from e
    if not isinstance(parsed, dict):
        raise HTTPException(422, f"{what} must be a JSON object")
    if unknown := set(parsed) - allowed:
        raise HTTPException(422, f"Unknown {what} field(s): {sorted(unknown)}")
    try:
        return {key: float(value) for key, value in parsed.items()}
    except (TypeError, ValueError) as e:
        raise HTTPException(422, f"{what} values must be numbers") from e


@router.get("/properties/{property_id}/export.xlsx")
def export_property_xlsx(
    property_id: int,
    overrides: str | None = None,
    property_overrides: str | None = None,
    session: Session = Depends(db),
):
    """The scenario on screen as a live Excel model - formulas, not a snapshot of the numbers.

    Without the override parameters this exports the property's *saved* assumptions, which would
    quietly disagree with whatever the user currently has on the sliders.
    """
    from app.valuation import export_xlsx

    row = _get(session, property_id)
    profile, ctx, merged_overrides = _resolve_run_inputs(
        session,
        property_id,
        _parse_override_param(overrides, engine.ASSUMPTION_FIELDS, "overrides"),
        _parse_override_param(property_overrides, PROFILE_OVERRIDE_FIELDS, "property_overrides"),
    )
    try:
        workbook = export_xlsx.build_workbook(profile, ctx, merged_overrides, label=row.label)
    except engine.UnknownOverrideError as e:
        raise HTTPException(422, str(e)) from e
    return Response(
        content=export_xlsx.to_bytes(workbook),
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{_safe_filename(row.label)}"'},
    )


class MonteCarloIn(BaseModel):
    overrides: dict[str, float] = {}
    property_overrides: dict[str, float] = {}
    n: int = 1000
    seed: int | None = None
    horizon: str = "10"


@router.post("/properties/{property_id}/monte-carlo")
def run_monte_carlo(property_id: int, body: MonteCarloIn, session: Session = Depends(db)):
    if body.horizon not in ("10", "20"):
        raise HTTPException(422, "horizon must be '10' or '20'")
    profile, ctx, merged_overrides = _resolve_run_inputs(session, property_id, body.overrides, body.property_overrides)
    return scenarios_mod.monte_carlo(profile, ctx, merged_overrides, body.n, body.seed, body.horizon)
