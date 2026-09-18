"""Find the public listing page for a property, for the UI's links menu. Only ever *links*.

How it stays on the right side of each site's terms (details in docs/DATA_LICENSES.md):
  - The only automated party is Perplexity's Search API, called under our own key. This code never fetches
    zillow.com, streeteasy.com, redfin.com or any other listing site (their terms forbid automated queries).
  - Only the URL is kept. Perplexity's result text (which is extracted listing-page content: price, photos
    descriptions) is discarded immediately, never stored, logged or shown.
  - Only https URLs on a fixed domain allowlist are accepted, and the URL must actually contain the property's
    street number and street name, so a wrong property is dropped instead of linked.
  - Usage is capped per month (each request costs about $0.005) and counted before it is sent.
  - The API key travels in a header, not the URL, and errors are re-raised without request details.
Results live in `app_settings` under `listing_urls`, keyed by listing id: no schema change.
"""

import logging
import re
from datetime import date, datetime
from urllib.parse import urlparse

import httpx

from app.models import AppSetting

log = logging.getLogger(__name__)

API = "https://api.perplexity.ai/search"
URLS_KEY = "listing_urls"
USAGE_KEY = "perplexity_usage"
MONTHLY_LIMIT = 300  # about $1.50 at $5 per 1,000 requests
#: Perplexity's domain filter takes up to 20. Sale-listing sites for NYC condos.
ALLOWED_DOMAINS = [
    "zillow.com", "streeteasy.com", "redfin.com", "realtor.com", "trulia.com",
    "compass.com", "corcoran.com", "elliman.com", "bhsusa.com", "halstead.com",
]
_DIRECTIONS = {"n", "s", "e", "w", "north", "south", "east", "west"}
_SUFFIXES = {
    "st", "street", "ave", "avenue", "av", "pl", "place", "rd", "road", "blvd", "boulevard", "dr", "drive",
    "pkwy", "parkway", "ln", "lane", "ct", "court", "sq", "square", "ter", "terrace", "way", "hwy", "plz", "plaza",
}
_ORDINAL = re.compile(r"\b(\d+)(?:st|nd|rd|th)\b")


def _tokens(text: str) -> list[str]:
    return [t for t in re.sub(r"[^a-z0-9]+", " ", _ORDINAL.sub(r"\1", text.lower())).split() if t]


def is_allowed_url(url: str) -> bool:
    try:
        u = urlparse(url)
    except ValueError:
        return False
    host = (u.hostname or "").lower()
    return u.scheme == "https" and any(host == d or host.endswith("." + d) for d in ALLOWED_DOMAINS)


def _is_building_page(url: str) -> bool:
    """True for URL shapes that are a building's page rather than one unit's. Deliberately narrow: an unknown shape is
    refused, because a link to a different unit (or a rental) labelled 'the building' would mislead."""
    u = urlparse(url)
    host = (u.hostname or "").lower()
    segs = [x for x in u.path.split("/") if x]
    path = [t for t in _tokens(u.path)]
    if "unit" in path or "apt" in path or "ste" in path:
        return False
    if host.endswith("streeteasy.com"):
        return len(segs) == 2 and segs[0] == "building"
    if host.endswith("zillow.com"):
        return bool(segs) and segs[0] == "b"
    if host.endswith("compass.com") or host.endswith("corcoran.com"):
        return "building" in segs
    if host.endswith("redfin.com"):
        return "home" in segs
    return False


def match_level(address: str, unit: str | None, url: str) -> str | None:
    """'unit' when the URL names this unit, 'building' when it names this street address, else None."""
    if not is_allowed_url(url):
        return None
    parts = _tokens(address)
    number = next((t for t in parts if t.isdigit()), None)
    core = [t for t in parts if t != number and t not in _DIRECTIONS and t not in _SUFFIXES]
    if number is None or not core:
        return None
    path = _tokens(urlparse(url).path)
    for i, tok in enumerate(path):
        window = path[i + 1 : i + 5]
        if tok == number and all(c in window for c in core):
            u = re.sub(r"[^a-z0-9]", "", (unit or "").lower())
            u = re.sub(r"^(apt|unit|ste|no)", "", u)
            if len(u) >= 2 and u in "".join(path):
                return "unit"
            # Not this unit. Only a real building page may stand in for it; another unit's page must not.
            return "building" if _is_building_page(url) else None
    return None


def pick_url(address: str, unit: str | None, results: list[dict]) -> tuple[str, str] | None:
    """Best acceptable (url, level) from search results; unit matches beat building matches, then rank order."""
    best = None
    for rank, item in enumerate(results):
        url = str(item.get("url") or "")
        level = match_level(address, unit, url)
        if level is None:
            continue
        score = (0 if level == "unit" else 1, rank)
        if best is None or score < best[0]:
            best = (score, url, level)
    return (best[1], best[2]) if best else None


def build_query(address: str, unit: str | None, borough: str | None) -> str:
    return f"{address}{' ' + unit if unit else ''}, {borough or 'New York'}, NY condo for sale"


def search(http: httpx.Client, api_key: str, query: str) -> list[dict]:
    """Raw results as [{'url','title'}]. The snippet is deliberately dropped here, before anything else sees it."""
    try:
        resp = http.post(
            API,
            json={"query": query, "max_results": 10, "search_domain_filter": ALLOWED_DOMAINS, "country": "US",
                  "max_tokens_per_page": 64},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )
        resp.raise_for_status()
        return [{"url": r.get("url"), "title": r.get("title")} for r in resp.json().get("results", [])]
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"Perplexity search: HTTP {e.response.status_code}") from None
    except httpx.HTTPError as e:
        raise RuntimeError(f"Perplexity search: {type(e).__name__}") from None


def _usage(session) -> dict:
    row = session.get(AppSetting, USAGE_KEY)
    return row.value if row else {"months": {}}


def requests_used(session) -> int:
    return _usage(session)["months"].get(date.today().strftime("%Y-%m"), 0)


def find_urls(session, http: httpx.Client, api_key: str, listings, *, limit: int = 25, monthly_limit: int = MONTHLY_LIMIT,
              refresh_days: int = 30) -> dict:
    """Search for each listing lacking a fresh URL, up to `limit` requests, never past `monthly_limit`.
    `listings` are objects with id, address, unit and borough. Returns counts for the CLI to print."""
    urls_row = session.get(AppSetting, URLS_KEY)
    urls = dict(urls_row.value) if urls_row else {}
    month = date.today().strftime("%Y-%m")
    stats = {"searched": 0, "found_unit": 0, "found_building": 0, "no_match": 0, "stopped": None}
    for lst in listings:
        if stats["searched"] >= limit:
            stats["stopped"] = "per-run limit"
            break
        prev = urls.get(str(lst.id))
        if prev and (date.today() - date.fromisoformat(prev["found_at"])).days < refresh_days:
            continue
        usage = _usage(session)
        if usage["months"].get(month, 0) >= monthly_limit:
            stats["stopped"] = f"monthly budget used ({monthly_limit})"
            break
        usage["months"][month] = usage["months"].get(month, 0) + 1  # counted before sending: a failed call may still bill
        session.merge(AppSetting(key=USAGE_KEY, value=usage))
        session.commit()
        results = search(http, api_key, build_query(lst.address, lst.unit, getattr(lst, "borough", None)))
        stats["searched"] += 1
        picked = pick_url(lst.address, lst.unit, results)
        if picked is None:
            stats["no_match"] += 1
            urls[str(lst.id)] = {"url": None, "level": None, "found_at": date.today().isoformat()}
        else:
            url, level = picked
            stats["found_unit" if level == "unit" else "found_building"] += 1
            urls[str(lst.id)] = {"url": url, "level": level, "found_at": date.today().isoformat(),
                                 "source": "perplexity-search", "checked_at": datetime.now().isoformat(timespec="seconds")}
        session.merge(AppSetting(key=URLS_KEY, value=urls))
        session.commit()
    return stats


def record_found(session, listing_id: int, address: str, unit: str | None, candidates: list[str], source: str) -> tuple[str, str] | None:
    """Store the best acceptable URL among `candidates` for one listing (used for URLs found by hand or by a search
    tool rather than the Perplexity call). Same validation as `find_urls`: allowed https domain, and the street
    number and name must appear in the URL. Returns (url, level) or None when nothing passes."""
    picked = pick_url(address, unit, [{"url": u} for u in candidates])
    row = session.get(AppSetting, URLS_KEY)
    urls = dict(row.value) if row else {}
    if picked is None:
        return None
    url, level = picked
    urls[str(listing_id)] = {"url": url, "level": level, "found_at": date.today().isoformat(), "source": source}
    session.merge(AppSetting(key=URLS_KEY, value=urls))
    session.commit()
    return picked
