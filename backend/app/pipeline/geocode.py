"""Address -> coordinates + BBL via NYC Planning Labs GeoSearch (free, no key)."""

from dataclasses import dataclass

import httpx


@dataclass
class GeocodeResult:
    longitude: float
    latitude: float
    bbl: str | None
    label: str


def geocode(http: httpx.Client, address: str) -> GeocodeResult | None:
    text = address if "new york" in address.lower() or ", ny" in address.lower() else f"{address}, New York, NY"
    try:
        resp = http.get("https://geosearch.planninglabs.nyc/v2/search", params={"text": text, "size": 1}, timeout=20)
        resp.raise_for_status()
        features = resp.json().get("features", [])
    except (httpx.HTTPError, ValueError):
        return None
    if not features:
        return None
    f = features[0]
    lon, lat = f["geometry"]["coordinates"]
    bbl = (f["properties"].get("addendum") or {}).get("pad", {}).get("bbl")
    return GeocodeResult(longitude=lon, latitude=lat, bbl=bbl, label=f["properties"].get("label", ""))


def normalize_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    u = unit.upper().replace("#", " ").replace(".", " ")
    for prefix in ("APARTMENT", "APT", "UNIT", "RESIDENCE", "NO"):
        if u.strip().startswith(prefix + " ") or u.strip() == prefix:
            u = u.strip()[len(prefix):]
    u = "".join(u.split()).lstrip("-")
    return u or None
