"""RentCast sale listings (https://developers.rentcast.io). Requires RENTCAST_API_KEY.

The free tier allows ~50 requests/month, so by default each run makes one request for condos listed in the
last `days_old` days (new-listing discovery). With a paid plan set `mode: full` and raise the limits to page
through every active listing, which also lets the pipeline detect listings that went off market.
"""

from datetime import date, datetime

from app.models import AppSetting
from app.pipeline.listings import RawListing, sync_listings
from app.sources.base import Source, SourceContext, SourceSkipped

API = "https://api.rentcast.io/v1/listings/sale"
NYC_CENTER = (40.7128, -74.0060)
NYC_RADIUS_MILES = 17  # reaches the far corners of Staten Island, the Bronx and eastern Queens
USAGE_KEY = "rentcast_usage"


class RentCastListings(Source):
    kind = "listings"
    requires = ["rentcast_api_key"]
    description = "RentCast active condo sale listings (free tier: new listings only)"

    def run(self, ctx: SourceContext) -> int:
        mode = self.options.get("mode", "new")
        page_size = int(self.options.get("page_size", 500))
        max_requests = int(self.options.get("max_requests_per_run", 1))
        monthly_limit = int(self.options.get("monthly_request_limit", 45))

        usage = ctx.session.get(AppSetting, USAGE_KEY)
        usage_by_month = dict(usage.value) if usage else {}
        month = date.today().strftime("%Y-%m")
        used = usage_by_month.get(month, 0)

        params = {"latitude": NYC_CENTER[0], "longitude": NYC_CENTER[1], "radius": NYC_RADIUS_MILES,
                  "propertyType": "Condo", "status": "Active", "limit": page_size}
        if mode == "new":
            params["daysOld"] = int(self.options.get("days_old", 7))

        raws, requests_made, exhausted = [], 0, False
        try:
            while requests_made < max_requests:
                if used + requests_made >= monthly_limit:
                    if requests_made == 0:
                        raise SourceSkipped(f"Monthly RentCast request budget reached ({monthly_limit}).")
                    break
                resp = ctx.http.get(API, params={**params, "offset": requests_made * page_size},
                                    headers={"X-Api-Key": ctx.settings.rentcast_api_key}, timeout=60)
                requests_made += 1
                resp.raise_for_status()
                page = resp.json()
                raws += [r for r in (to_raw(item) for item in page) if r]
                if len(page) < page_size:
                    exhausted = True
                    break
        finally:
            usage_by_month[month] = used + requests_made
            ctx.session.merge(AppSetting(key=USAGE_KEY, value=usage_by_month))
            ctx.session.commit()

        # Keep only listings inside NYC neighborhoods; the search radius also reaches NJ and Westchester.
        codes = ctx.geo.lookup_many([r.longitude if r.longitude is not None else float("nan") for r in raws],
                                    [r.latitude if r.latitude is not None else float("nan") for r in raws])
        raws = [r for r, code in zip(raws, codes) if code]
        stats = sync_listings(ctx.session, self.name, raws, complete=(mode == "full" and exhausted),
                              geo=ctx.geo, http=ctx.http)
        return stats.total


def to_raw(item: dict) -> RawListing | None:
    price = item.get("price")
    if not price or not item.get("id"):
        return None
    listed = _date(item.get("listedDate")) or date.today()
    history = []
    for when, h in (item.get("history") or {}).items():
        d = _date(h.get("listedDate")) or _date(when)
        if h.get("price") and d and d >= listed:
            history.append((d, float(h["price"])))
    hoa = (item.get("hoa") or {}).get("fee")
    return RawListing(
        external_id=item["id"],
        address=item.get("addressLine1") or item.get("formattedAddress", ""),
        unit=item.get("addressLine2"),
        zip_code=item.get("zipCode"),
        latitude=item.get("latitude"),
        longitude=item.get("longitude"),
        price=float(price),
        listed_date=listed,
        bedrooms=item.get("bedrooms"),
        bathrooms=item.get("bathrooms"),
        sqft=item.get("squareFootage"),
        year_built=item.get("yearBuilt"),
        common_charges=float(hoa) if hoa else None,
        notes=" / ".join(filter(None, [item.get("mlsName"), (item.get("listingOffice") or {}).get("name")])) or None,
        price_history=history,
    )


def _date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None
