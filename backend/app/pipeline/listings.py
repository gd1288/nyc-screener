"""Listing lifecycle: upsert fetched listings, log price/status changes, detect listings that disappeared.

    active --(price differs)--> active + price_change snapshot
    active --(missing from N complete fetches)--> off_market
    off_market --(seen again)--> active (relisted)
    off_market --(ACRIS deed recorded)--> sold          [app.sources.acris]
    off_market --(no deed after WITHDRAWN_AFTER_DAYS)--> withdrawn
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import httpx
from sqlalchemy.orm import Session

from app.geo import NeighborhoodIndex
from app.models import Listing, ListingSnapshot, ListingStatus
from app.pipeline.geocode import geocode, normalize_unit

MISSED_FETCHES_BEFORE_OFF_MARKET = 2
WITHDRAWN_AFTER_DAYS = 90


@dataclass
class RawListing:
    external_id: str
    address: str
    price: float
    listed_date: date
    unit: str | None = None
    zip_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    url: str | None = None
    bedrooms: float | None = None
    bathrooms: float | None = None
    sqft: float | None = None
    year_built: int | None = None
    common_charges: float | None = None
    property_taxes: float | None = None
    rent_estimate: float | None = None
    notes: str | None = None
    status: str = ListingStatus.ACTIVE  # sources that report sales directly can pass "sold"
    sold_price: float | None = None
    sold_date: date | None = None
    price_history: list[tuple[date, float]] = field(default_factory=list)  # earlier prices, if known


@dataclass
class SyncStats:
    new: int = 0
    updated: int = 0
    price_changes: int = 0
    off_market: int = 0
    relisted: int = 0
    sold: int = 0

    @property
    def total(self) -> int:
        return self.new + self.updated


def _snapshot(listing: Listing, event: str, when: datetime | None = None) -> None:
    listing.snapshots.append(
        ListingSnapshot(event=event, price=listing.price, status=listing.status, observed_at=when or datetime.now())
    )


def _apply_fields(listing: Listing, raw: RawListing) -> None:
    for attr in ("url", "zip_code", "bedrooms", "bathrooms", "sqft", "year_built", "common_charges",
                 "property_taxes", "rent_estimate", "notes"):
        value = getattr(raw, attr)
        if value is not None:
            setattr(listing, attr, value)


def sync_listings(
    session: Session,
    source: str,
    raws: list[RawListing],
    *,
    complete: bool,
    geo: NeighborhoodIndex,
    http: httpx.Client | None = None,
) -> SyncStats:
    """Upsert `raws`. If `complete` (the fetch covered every active listing for this source), listings
    not seen count as a missed fetch and eventually move to off_market."""
    stats = SyncStats()
    now = datetime.now()
    existing = {row.external_id: row for row in session.query(Listing).filter(Listing.source == source)}
    # Feeds sometimes list one unit under several ids (e.g. two MLS entries); match those by address + unit.
    by_unit = {unit_key(row.address, row.unit): row for row in existing.values() if row.status != ListingStatus.SOLD}
    seen: set[str] = set()

    for raw in raws:
        listing = existing.get(raw.external_id) or by_unit.get(unit_key(raw.address, raw.unit))
        if listing is None:
            listing = _create(session, source, raw, geo, http)
            existing[raw.external_id] = by_unit[unit_key(raw.address, raw.unit)] = listing
            seen.add(raw.external_id)
            stats.new += 1
            continue
        seen.add(listing.external_id)
        stats.updated += 1
        _apply_fields(listing, raw)
        listing.last_seen, listing.missed_fetches = now, 0
        if listing.status in (ListingStatus.OFF_MARKET, ListingStatus.WITHDRAWN) and raw.status == ListingStatus.ACTIVE:
            listing.status, listing.off_market_date = ListingStatus.ACTIVE, None
            _snapshot(listing, "relisted")
            stats.relisted += 1
        if raw.price and abs(raw.price - listing.price) >= 1 and listing.status == ListingStatus.ACTIVE:
            listing.price = raw.price
            _snapshot(listing, "price_change")
            stats.price_changes += 1
        if raw.status == ListingStatus.SOLD and listing.status != ListingStatus.SOLD:
            mark_sold(listing, raw.sold_price, raw.sold_date or date.today())
            stats.sold += 1

    if complete:
        for ext_id, listing in existing.items():
            if ext_id in seen or listing.status != ListingStatus.ACTIVE:
                continue
            listing.missed_fetches += 1
            if listing.missed_fetches >= MISSED_FETCHES_BEFORE_OFF_MARKET:
                listing.status, listing.off_market_date = ListingStatus.OFF_MARKET, date.today()
                _snapshot(listing, "off_market")
                stats.off_market += 1
    session.commit()
    return stats


def unit_key(address: str, unit: str | None) -> tuple[str, str]:
    return " ".join(address.upper().replace(".", " ").replace(",", " ").split()), normalize_unit(unit) or ""


CONDO_UNIT_LOTS = range(1001, 7000)  # individual condo units
CONDO_BILLING_LOTS = range(7501, 10000)  # a condo building's billing lot (what address lookups return)


def ownership_type(bbl: str | None) -> str:
    """NYC assigns condo buildings special tax lots; co-ops and rentals keep an ordinary lot.
    Returns "condo", "likely_coop" (ordinary lot, so probably a co-op mislabeled by the feed) or "unknown"."""
    if not bbl or len(bbl) != 10 or not bbl.isdigit():
        return "unknown"
    lot = int(bbl[6:])
    return "condo" if lot in CONDO_UNIT_LOTS or lot in CONDO_BILLING_LOTS else "likely_coop"


def _create(session: Session, source: str, raw: RawListing, geo: NeighborhoodIndex, http: httpx.Client | None) -> Listing:
    listing = Listing(
        source=source, external_id=raw.external_id, address=raw.address.strip(), unit=normalize_unit(raw.unit),
        latitude=raw.latitude, longitude=raw.longitude, price=raw.price, original_price=raw.price,
        listed_date=raw.listed_date, status=ListingStatus.ACTIVE, first_seen=datetime.now(), last_seen=datetime.now(),
        missed_fetches=0,
    )
    _apply_fields(listing, raw)
    if http is not None:
        g = geocode(http, raw.address)
        if g:
            listing.bbl = g.bbl
            if listing.latitude is None:
                listing.latitude, listing.longitude = g.latitude, g.longitude
    listing.nta_code = geo.lookup(listing.longitude, listing.latitude)
    session.add(listing)

    # Seed history so price cuts before we first saw the listing still count.
    history = sorted(raw.price_history)
    if history:
        listing.original_price = history[0][1]
        for when, price in history:
            listing.snapshots.append(ListingSnapshot(event="listed" if when == history[0][0] else "price_change",
                                                     price=price, status=ListingStatus.ACTIVE,
                                                     observed_at=datetime.combine(when, datetime.min.time())))
        if abs(history[-1][1] - raw.price) >= 1:
            _snapshot(listing, "price_change")
    else:
        _snapshot(listing, "listed", datetime.combine(raw.listed_date, datetime.min.time()))
    return listing


def mark_sold(listing: Listing, price: float | None, sold_date: date, document_id: str | None = None) -> None:
    listing.status = ListingStatus.SOLD
    listing.sold_price = price
    listing.sold_date = sold_date
    listing.sold_document_id = document_id
    listing.off_market_date = listing.off_market_date or sold_date
    listing.snapshots.append(ListingSnapshot(event="sold", price=price, status=ListingStatus.SOLD,
                                             observed_at=datetime.combine(sold_date, datetime.min.time())))


def expire_stale_off_market(session: Session) -> int:
    cutoff = date.today() - timedelta(days=WITHDRAWN_AFTER_DAYS)
    stale = session.query(Listing).filter(Listing.status == ListingStatus.OFF_MARKET, Listing.off_market_date <= cutoff).all()
    for listing in stale:
        listing.status = ListingStatus.WITHDRAWN
        _snapshot(listing, "withdrawn")
    session.commit()
    return len(stale)


def days_on_market(listing: Listing, today: date | None = None) -> int:
    end = listing.sold_date or listing.off_market_date or today or date.today()
    return max((end - listing.listed_date).days, 0)
