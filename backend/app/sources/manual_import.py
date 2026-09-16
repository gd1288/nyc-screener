"""Manual listings: added through the UI form or a CSV upload. Not scheduled.

CSV columns (header row required; only address and price are mandatory):
  address, unit, price, listed_date (YYYY-MM-DD), bedrooms, bathrooms, sqft, year_built,
  common_charges (monthly), property_taxes (monthly), rent_estimate (monthly), url, notes, external_id
"""

import csv
import hashlib
import io
from datetime import date

from app.pipeline.listings import RawListing

SOURCE_NAME = "manual"


def raw_from_dict(d: dict) -> RawListing:
    def num(key):
        v = str(d.get(key) or "").replace("$", "").replace(",", "").strip()
        return float(v) if v else None

    address = str(d.get("address") or "").strip()
    price = num("price")
    if not address or not price:
        raise ValueError("address and price are required")
    unit = (str(d.get("unit") or "").strip()) or None
    listed = d.get("listed_date")
    listed_date = listed if isinstance(listed, date) else (date.fromisoformat(str(listed)) if listed else date.today())
    external_id = str(d.get("external_id") or "").strip() or _stable_id(address, unit)
    year = num("year_built")
    return RawListing(
        external_id=external_id, address=address, unit=unit, price=price, listed_date=listed_date,
        bedrooms=num("bedrooms"), bathrooms=num("bathrooms"), sqft=num("sqft"),
        year_built=int(year) if year else None, common_charges=num("common_charges"),
        property_taxes=num("property_taxes"), rent_estimate=num("rent_estimate"),
        url=(str(d.get("url") or "").strip() or None), notes=(str(d.get("notes") or "").strip() or None),
    )


def raws_from_csv(text: str) -> tuple[list[RawListing], list[str]]:
    raws, errors = [], []
    for i, row in enumerate(csv.DictReader(io.StringIO(text)), start=2):
        try:
            raws.append(raw_from_dict({k.strip().lower(): v for k, v in row.items() if k}))
        except ValueError as e:
            errors.append(f"row {i}: {e}")
    return raws, errors


def _stable_id(address: str, unit: str | None) -> str:
    key = f"{' '.join(address.upper().split())}|{(unit or '').upper()}"
    return "m-" + hashlib.sha1(key.encode()).hexdigest()[:16]
