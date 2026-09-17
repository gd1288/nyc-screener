"""RentCast sale listings (https://developers.rentcast.io). Requires RENTCAST_API_KEY.

A request returns at most 500 listings, nearest the search center first, so one citywide circle fills up
with Manhattan and New Jersey. Instead each run searches one of `areas` (roughly a borough each): the one
searched longest ago, asking for everything listed since that search (plus a 2-day overlap).

The free tier allows 50 requests/month, so usage is capped three ways (all set in sources.yaml):
  - `max_requests_per_run`: requests per run (default 1)
  - `min_hours_between_requests`: runs this soon after a successful request are skipped (incl. "Refresh now")
  - `monthly_request_limit`: hard stop per calendar month, kept well under the plan limit
Every attempted request is counted, even if it fails, since RentCast doesn't document whether errors are billed.
Each response's total match count (X-Total-Count) is saved so truncated areas are visible.

With a paid plan, set `mode: full` and raise the limits to page through every active listing, which also lets
the pipeline detect listings that went off market.
"""

import logging
from datetime import date, datetime, timedelta

from app.models import AppSetting
from app.pipeline.listings import RawListing, sync_listings
from app.sources.base import Source, SourceContext, SourceSkipped

log = logging.getLogger(__name__)

API = "https://api.rentcast.io/v1/listings/sale"
USAGE_KEY = "rentcast_usage"
DEFAULT_AREAS = [
    {"name": "manhattan", "latitude": 40.7831, "longitude": -73.9712, "radius": 6},
    {"name": "brooklyn", "latitude": 40.6500, "longitude": -73.9500, "radius": 6},
    {"name": "queens", "latitude": 40.7282, "longitude": -73.8300, "radius": 7},
    {"name": "bronx", "latitude": 40.8448, "longitude": -73.8648, "radius": 5},
    {"name": "staten_island", "latitude": 40.5795, "longitude": -74.1502, "radius": 6},
]
OVERLAP_DAYS = 2


def read_usage(ctx: SourceContext) -> dict:
    row = ctx.session.get(AppSetting, USAGE_KEY)
    value = dict(row.value) if row else {}
    if "months" not in value:  # older format: {"YYYY-MM": count}
        value = {"months": {k: v for k, v in value.items() if k[:2] == "20"}, "last_request_at": None}
    value.setdefault("areas", {})
    return value


def pick_area(areas: list[dict], last_fetched: dict[str, str]) -> dict:
    """The area never searched, else the one searched longest ago (config order breaks ties)."""
    return min(areas, key=lambda a: last_fetched.get(a["name"], ""))


def days_old_for(area: dict, last_fetched: dict[str, str], seed_days: int, max_days: int) -> int:
    last = last_fetched.get(area["name"])
    if not last:
        return seed_days
    return max(1, min((date.today() - date.fromisoformat(last)).days + OVERLAP_DAYS, max_days))


class RentCastListings(Source):
    kind = "listings"
    requires = ["rentcast_api_key"]
    description = "RentCast condo sale listings, one borough per run (free tier: request budget enforced)"

    def probe(self, ctx: SourceContext) -> tuple[bool | None, str]:
        # Deliberately not probed: any authenticated hit — even a HEAD — spends against the
        # monthly request budget this module exists to protect. `app.cli diagnose` already
        # reports this source's last real run from source_runs; that's the health signal to use.
        return None, "probing disabled to protect the RentCast request budget; see source_runs for its last real run"

    def run(self, ctx: SourceContext) -> int:
        mode = self.options.get("mode", "new")
        page_size = int(self.options.get("page_size", 500))
        max_requests = int(self.options.get("max_requests_per_run", 1))
        monthly_limit = int(self.options.get("monthly_request_limit", 31))
        min_gap = timedelta(hours=float(self.options.get("min_hours_between_requests", 24)))
        areas = self.options.get("areas") or DEFAULT_AREAS

        usage = read_usage(ctx)
        month = date.today().strftime("%Y-%m")
        used = usage["months"].get(month, 0)
        last = datetime.fromisoformat(usage["last_request_at"]) if usage.get("last_request_at") else None
        if last and datetime.now() - last < min_gap:
            raise SourceSkipped(f"Saving RentCast requests: last request {last:%b %d %H:%M}, "
                                f"next allowed after {last + min_gap:%b %d %H:%M}.")
        if used >= monthly_limit:
            raise SourceSkipped(f"Monthly RentCast budget used ({used}/{monthly_limit}).")

        area = pick_area(areas, usage["areas"])
        params = {"latitude": area["latitude"], "longitude": area["longitude"], "radius": area["radius"],
                  "propertyType": "Condo", "status": "Active", "limit": page_size, "includeTotalCount": "true"}
        if mode == "new":
            params["daysOld"] = days_old_for(area, usage["areas"], int(self.options.get("seed_days_old", 30)),
                                             int(self.options.get("max_days_old", 30)))

        raws, requests_made, exhausted, succeeded, returned, total = [], 0, False, False, 0, None
        try:
            while requests_made < max_requests and used + requests_made < monthly_limit:
                requests_made += 1  # count before sending: a failed request may still be billed
                resp = ctx.http.get(API, params={**params, "offset": (requests_made - 1) * page_size},
                                    headers={"X-Api-Key": ctx.settings.rentcast_api_key}, timeout=60)
                resp.raise_for_status()
                succeeded = True
                page = resp.json()
                returned += len(page)
                total = resp.headers.get("X-Total-Count", total)
                raws += [r for r in (to_raw(item) for item in page) if r]
                if len(page) < page_size:
                    exhausted = True
                    break
        finally:
            if requests_made:
                usage["months"][month] = used + requests_made
                if succeeded:  # a rejected key shouldn't block retrying for days once it's fixed
                    usage["last_request_at"] = datetime.now().isoformat(timespec="seconds")
                    usage["areas"][area["name"]] = date.today().isoformat()
                ctx.session.merge(AppSetting(key=USAGE_KEY, value=usage))
                ctx.session.commit()

        # Keep only listings inside NYC neighborhoods; search circles also reach NJ, Westchester and Nassau.
        codes = ctx.geo.lookup_many([r.longitude if r.longitude is not None else float("nan") for r in raws],
                                    [r.latitude if r.latitude is not None else float("nan") for r in raws])
        raws = [r for r, code in zip(raws, codes, strict=True) if code]
        usage["last_result"] = {"area": area["name"], "days_old": params.get("daysOld"), "returned": returned,
                                "total_matches": int(total) if total is not None else None, "kept_in_nyc": len(raws),
                                "truncated": total is not None and int(total) > returned}
        ctx.session.merge(AppSetting(key=USAGE_KEY, value=usage))
        ctx.session.commit()
        if usage["last_result"]["truncated"]:
            log.warning("RentCast %s: %s matches but only %s returned; shorten the schedule or add areas",
                        area["name"], total, returned)
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
