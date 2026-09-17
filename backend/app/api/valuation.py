"""Valuation API: save a property, look up an address, and run the cash-flow engine against it.

Scenarios, sensitivity, Monte Carlo, and the Excel export aren't here yet (see the plan's Phase 2a
scope) - this is the vertical slice: a saved property and a single run with overridable factors.
"""

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import ValuationProperty
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
    price: float
    sqft: float | None = None
    bedrooms: float | None = None
    common_charges: float | None = None
    property_taxes: float | None = None
    rent_estimate: float | None = None
    assumption_overrides: dict[str, float] = {}


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
    row = ValuationProperty(**body.model_dump())
    session.add(row)
    session.commit()
    return _row_dict(row)


@router.get("/properties/{property_id}")
def get_property(property_id: int, session: Session = Depends(db)):
    return _row_dict(_get(session, property_id))


@router.patch("/properties/{property_id}")
def update_property(property_id: int, body: PropertyIn, session: Session = Depends(db)):
    row = _get(session, property_id)
    for k, v in body.model_dump().items():
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
    row = _get(session, property_id)
    ctx = MarketContext.load(session)
    profile = _to_profile(row)
    for k, v in body.property_overrides.items():
        if k in PROFILE_OVERRIDE_FIELDS:
            setattr(profile, k, v)
    merged_overrides = {**row.assumption_overrides, **body.overrides}
    return engine.run(profile, ctx, merged_overrides)
