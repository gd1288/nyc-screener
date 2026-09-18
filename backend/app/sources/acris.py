"""Confirms sales of tracked listings from ACRIS deed records (NYC Open Data, no key needed).

A condo unit's deeds are found by borough + tax block + unit number (ACRIS legals), then filtered to
DEED documents dated on/after the listing date (ACRIS master). A match moves the listing to Sold with the
recorded price. Listings off market for 90+ days with no deed become Withdrawn.
"""

from datetime import datetime, timedelta

from app.models import Listing, ListingStatus
from app.pipeline.geocode import normalize_unit
from app.pipeline.listings import expire_stale_off_market, mark_sold, ownership_type
from app.sources import socrata
from app.sources.base import Source, SourceContext

LEGALS = "8h5j-fqxa"
MASTER = "bnx9-e6tj"
# A deed recorded before the listing date is the seller's own purchase, never this sale. (This used to allow 14 days
# before the listing and produced a false 'sold' for a listing whose seller had bought three days earlier.)
LOOKBACK_BEFORE_LISTING = timedelta(0)
MIN_DEED_AMOUNT = 10_000  # skip nominal-consideration transfers


class AcrisSoldCheck(Source):
    kind = "sold_check"
    description = "ACRIS recorded deeds: confirms which tracked listings sold, and for how much"
    probe_socrata = ("data.cityofnewyork.us", LEGALS)

    def run(self, ctx: SourceContext) -> int:
        candidates = (
            ctx.session.query(Listing)
            .filter(
                Listing.status.in_([ListingStatus.ACTIVE, ListingStatus.OFF_MARKET]),
                Listing.bbl.is_not(None),
                Listing.unit.is_not(None),
            )
            .all()
        )
        # A co-op is not a deeded unit: its ordinary tax lot has no per-unit deed, so a match is another property's.
        candidates = [c for c in candidates if ownership_type(c.bbl) != "likely_coop"]
        sold = 0
        for listing in candidates:
            deed = find_deed(ctx, listing)
            if deed:
                mark_sold(listing, deed["price"], deed["date"], deed["document_id"])
                sold += 1
        ctx.session.commit()
        expire_stale_off_market(ctx.session)
        return sold


def find_deed(ctx: SourceContext, listing: Listing) -> dict | None:
    token = ctx.settings.socrata_app_token
    borough, block = listing.bbl[0], str(int(listing.bbl[1:6]))
    unit = normalize_unit(listing.unit)
    if not unit or not unit.replace("-", "").isalnum():
        return None
    # Filter by unit on the server (big condo blocks have tens of thousands of documents), then match exactly.
    legals = socrata.nyc(
        ctx.http,
        LEGALS,
        token,
        select="document_id,unit",
        order="document_id desc",
        limit=5_000,
        where=f"borough='{borough}' and block='{block}' and upper(unit) like '%{unit}%'",
    )
    doc_ids = sorted({r["document_id"] for r in legals if normalize_unit(r.get("unit")) == unit})
    if not doc_ids:
        return None
    since = (listing.listed_date - LOOKBACK_BEFORE_LISTING).isoformat()
    ids = ",".join(f"'{d}'" for d in doc_ids[-50:])  # most recent documents; ids start with the year
    masters = socrata.nyc(
        ctx.http,
        MASTER,
        token,
        select="document_id,doc_type,document_date,document_amt",
        where=f"document_id in ({ids}) and doc_type in ('DEED','DEEDO') and document_date >= '{since}'",
        order="document_date desc",
    )
    for m in masters:
        amount = float(m.get("document_amt") or 0)
        if amount >= MIN_DEED_AMOUNT and m.get("document_date"):
            return {
                "document_id": m["document_id"],
                "price": amount,
                "date": datetime.fromisoformat(m["document_date"][:10]).date(),
            }
    return None
