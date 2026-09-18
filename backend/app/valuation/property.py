"""Property lookup: resolve an address to a neighborhood before a valuation run has one manually."""

from dataclasses import dataclass

import httpx
from sqlalchemy.orm import Session

from app.geo import NeighborhoodIndex
from app.pipeline.geocode import geocode


@dataclass
class AddressLookup:
    address: str
    latitude: float
    longitude: float
    nta_code: str | None
    neighborhood_name: str | None


def lookup_address(session: Session, address: str, http: httpx.Client | None = None) -> AddressLookup | None:
    """Geocode a free-text NYC address and resolve its neighborhood. Returns None if it can't be found."""
    owns_client = http is None
    http = http or httpx.Client()
    try:
        result = geocode(http, address)
    finally:
        if owns_client:
            http.close()
    if result is None:
        return None
    nta_code = NeighborhoodIndex.load(session).lookup(result.longitude, result.latitude)
    name = None
    if nta_code:
        from app.models import Neighborhood

        n = session.get(Neighborhood, nta_code)
        name = n.name if n else None
    return AddressLookup(
        address=result.label or address,
        latitude=result.latitude,
        longitude=result.longitude,
        nta_code=nta_code,
        neighborhood_name=name,
    )
