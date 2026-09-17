"""Valuation API: save a property, look up an address, and run the cash-flow engine against it.

Scenarios, sensitivity, Monte Carlo, and the Excel export aren't here yet (see the plan's Phase 2a
scope) - this is the vertical slice: a saved property and a single run with overridable factors.
"""

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Neighborhood, ValuationProperty
from app.services import MarketContext
from app.valuation import engine
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


def _row_dict(row: ValuationProperty) -> dict:
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
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _get(session: Session, property_id: int) -> ValuationProperty:
    row = session.get(ValuationProperty, property_id)
    if row is None:
        raise HTTPException(404, "No such valuation property")
    return row


@router.get("/properties")
def list_properties(session: Session = Depends(db)):
    rows = session.query(ValuationProperty).order_by(ValuationProperty.updated_at.desc()).all()
    return [_row_dict(r) for r in rows]


@router.post("/properties")
def create_property(body: PropertyIn, session: Session = Depends(db)):
    _check_nta_code(session, body.nta_code)
    row = ValuationProperty(**body.model_dump())
    session.add(row)
    session.commit()
    return _row_dict(row)


@router.get("/properties/{property_id}")
def get_property(property_id: int, session: Session = Depends(db)):
    return _row_dict(_get(session, property_id))


@router.patch("/properties/{property_id}")
def update_property(property_id: int, body: PropertyPatch, session: Session = Depends(db)):
    row = _get(session, property_id)
    fields = body.model_dump(exclude_unset=True)
    if "nta_code" in fields:
        _check_nta_code(session, fields["nta_code"])
    for k, v in fields.items():
        setattr(row, k, v)
    session.commit()
    return _row_dict(row)


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


@router.post("/properties/{property_id}/run")
def run_property(property_id: int, body: RunIn, session: Session = Depends(db)):
    if unknown := set(body.property_overrides) - PROFILE_OVERRIDE_FIELDS:
        raise HTTPException(422, f"Unknown property override field(s): {sorted(unknown)}")
    row = _get(session, property_id)
    ctx = MarketContext.load(session)
    profile = _to_profile(row)
    for k, v in body.property_overrides.items():
        setattr(profile, k, v)
    merged_overrides = {**row.assumption_overrides, **body.overrides}
    try:
        return engine.run(profile, ctx, merged_overrides)
    except engine.UnknownOverrideError as e:
        raise HTTPException(422, str(e)) from e
