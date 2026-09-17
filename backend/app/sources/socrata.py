"""Paged queries against Socrata open data portals (NYC Open Data, data.ny.gov)."""

import time
from collections.abc import Iterator

import httpx

PAGE_SIZE = 50_000


def query(
    http: httpx.Client,
    domain: str,
    dataset: str,
    *,
    app_token: str = "",
    select: str | None = None,
    where: str | None = None,
    order: str | None = None,
    limit: int | None = None,
    page_size: int = PAGE_SIZE,
) -> Iterator[dict]:
    """Yield rows, paging with $offset. `order` is required for stable paging on large datasets."""
    headers = {"X-App-Token": app_token} if app_token else {}
    offset = 0
    fetched = 0
    while True:
        size = page_size if limit is None else min(page_size, limit - fetched)
        if size <= 0:
            return
        params = {"$limit": size, "$offset": offset}
        if select:
            params["$select"] = select
        if where:
            params["$where"] = where
        params["$order"] = order or ":id"
        rows = _get(http, f"https://{domain}/resource/{dataset}.json", params, headers)
        yield from rows
        fetched += len(rows)
        if len(rows) < size:
            return
        offset += len(rows)


def _get(http: httpx.Client, url: str, params: dict, headers: dict, attempts: int = 4) -> list[dict]:
    for attempt in range(attempts):
        try:
            resp = http.get(url, params=params, headers=headers, timeout=180)
            if resp.status_code in (429, 500, 502, 503, 504):
                raise httpx.HTTPStatusError("retryable", request=resp.request, response=resp)
            resp.raise_for_status()
            return resp.json()
        except (httpx.TransportError, httpx.HTTPStatusError):
            if attempt == attempts - 1:
                raise
            time.sleep(2 * (attempt + 1))
    return []


def nyc(http: httpx.Client, dataset: str, app_token: str = "", **kw) -> Iterator[dict]:
    return query(http, "data.cityofnewyork.us", dataset, app_token=app_token, **kw)


def nys(http: httpx.Client, dataset: str, app_token: str = "", **kw) -> Iterator[dict]:
    return query(http, "data.ny.gov", dataset, app_token=app_token, **kw)
