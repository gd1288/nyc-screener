"""FRED time series (Federal Reserve Bank of St. Louis), used for macro inputs to the valuation.

Today: `MORTGAGE30US` (Freddie Mac weekly 30-year rate, backs the `interest_rate` factor), `DGS10` (10-year
Treasury, a rate benchmark for context) and `ATNHPIUS35614Q` (FHFA New York metro price index, used to
calibrate how severe the stress scenarios are).

Terms and licensing (reviewed 2026-09-18, see docs/DATA_LICENSES.md):
  - FRED API terms: https://fred.stlouisfed.org/docs/api/terms_of_use.html. Requires a free API key.
    Any product using the API must show: "This product uses the FRED(R) API but is not endorsed or
    certified by the Federal Reserve Bank of St. Louis." The FRED name/logo may not be implied as an
    endorsement, and this may not replicate FRED's own site experience.
  - MORTGAGE30US is owned by Freddie Mac: "Information from this document may be used with proper
    attribution. Alteration ... is strictly prohibited." FRED's terms say third-party series used for
    anything beyond your own personal use need the owner's permission. This app is a personal,
    single-user tool; if it is ever shared or made public, ask Freddie Mac first.
  - Only the documented API is used (never FRED's web pages), at one request per series per run.

The key travels as a query parameter, so any httpx error text would contain it; errors are re-raised
without the URL so the key can never land in `source_runs.message`.
"""

import logging
import re
from datetime import date, datetime, timedelta

import httpx

from app.models import AppSetting
from app.sources.base import Source, SourceContext

log = logging.getLogger(__name__)


class _RedactApiKey(logging.Filter):
    """httpx logs every request URL at INFO, and FRED takes its key as a query parameter, so the raw
    log line would print the key into the console, server logs and any transcript of them."""

    _PATTERN = re.compile(r"(api_key=)[^&\s\"']+")

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._PATTERN.sub(r"\1REDACTED", str(record.msg))
        if record.args:
            record.args = tuple(
                self._PATTERN.sub(r"\1REDACTED", str(a)) if "api_key=" in str(a) else a for a in record.args
            )
        return True


logging.getLogger("httpx").addFilter(_RedactApiKey())

API = "https://api.stlouisfed.org/fred/series/observations"
MACRO_PREFIX = "macro:"
FRED_NOTICE = "This product uses the FRED(R) API but is not endorsed or certified by the Federal Reserve Bank of St. Louis."
DEFAULT_SERIES = [
    {
        "id": "MORTGAGE30US",
        "years": 5,
        "citation": (
            "Freddie Mac, 30-Year Fixed Rate Mortgage Average in the United States [MORTGAGE30US], retrieved from "
            "FRED, Federal Reserve Bank of St. Louis; https://fred.stlouisfed.org/series/MORTGAGE30US"
        ),
    },
    {
        # Public domain, citation requested (checked on FRED 2026-09-18).
        "id": "DGS10",
        "years": 5,
        "citation": (
            "Board of Governors of the Federal Reserve System (US), Market Yield on U.S. Treasury Securities at "
            "10-Year Constant Maturity, Quoted on an Investment Basis [DGS10], retrieved from FRED, Federal Reserve "
            "Bank of St. Louis; https://fred.stlouisfed.org/series/DGS10"
        ),
    },
    {
        # FHFA data, tagged "Public Domain: Citation Requested" on FRED; history starts 1995:Q1, so the whole
        # series is stored (it covers the 2007-2012 downturn that the stress scenarios are calibrated against).
        "id": "ATNHPIUS35614Q",
        "years": 60,
        "citation": (
            "U.S. Federal Housing Finance Agency, All-Transactions House Price Index for New York-Jersey City-White "
            "Plains, NY-NJ (MSAD) [ATNHPIUS35614Q], retrieved from FRED, Federal Reserve Bank of St. Louis; "
            "https://fred.stlouisfed.org/series/ATNHPIUS35614Q"
        ),
    },
]


def parse_observations(payload: dict) -> list[list]:
    """[[iso_date, value], ...] oldest first. FRED marks missing observations with '.', which must
    be dropped rather than coerced to 0 (a 0% mortgage rate would silently corrupt every percentile)."""
    points = []
    for obs in payload.get("observations", []):
        try:
            points.append([obs["date"], float(obs["value"])])
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(points)


class FredSeries(Source):
    kind = "macro"
    coverage = "national"
    granularity = "point"
    requires = ["fred_api_key"]
    description = "FRED macro series (Freddie Mac 30-year mortgage rate). Free API key; attribution required."

    def _fetch(self, ctx: SourceContext, series_id: str, start: date, limit: int | None = None) -> dict:
        params = {
            "series_id": series_id,
            "api_key": ctx.settings.fred_api_key,
            "file_type": "json",
            "observation_start": start.isoformat(),
        }
        if limit:
            params.update(limit=limit, sort_order="desc")
        try:
            resp = ctx.http.get(API, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"FRED {series_id}: HTTP {e.response.status_code}") from None
        except httpx.HTTPError as e:
            raise RuntimeError(f"FRED {series_id}: {type(e).__name__}") from None

    def probe(self, ctx: SourceContext) -> tuple[bool | None, str]:
        if not getattr(ctx.settings, "fred_api_key", ""):
            return None, "not probed: set FRED_API_KEY (free) to enable"
        try:
            self._fetch(ctx, "MORTGAGE30US", date.today() - timedelta(days=30), limit=1)
        except RuntimeError as e:
            return False, str(e)
        return True, "api.stlouisfed.org: reachable"

    def run(self, ctx: SourceContext) -> int:
        series = self.options.get("series") or DEFAULT_SERIES
        default_years = int(self.options.get("history_years", 5))
        written = 0
        for spec in series:
            start = date.today() - timedelta(days=365 * int(spec.get("years", default_years)))
            points = parse_observations(self._fetch(ctx, spec["id"], start))
            if not points:
                raise RuntimeError(f"FRED {spec['id']}: no observations returned")
            ctx.session.merge(
                AppSetting(
                    key=MACRO_PREFIX + spec["id"],
                    value={
                        "series_id": spec["id"],
                        "citation": spec.get("citation", ""),
                        "notice": FRED_NOTICE,
                        "fetched_at": datetime.now().isoformat(timespec="seconds"),
                        "points": points,
                    },
                )
            )
            written += len(points)
        ctx.session.commit()
        return written
