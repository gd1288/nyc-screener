"""FHFA annual house price index by census tract — national, free, keyless.

This is the appreciation signal that makes every metro measurable on the same basis. NYC's own
momentum metrics come from DOF repeat sales and Zillow, neither of which exists for Austin; FHFA's
tract index does, so `hpi_cagr_5y`/`hpi_cagr_10y` are what let two metros be compared at all — and
what the generalized backtest scores itself against.

The published file is ~90MB of national tract-years. It is never downloaded whole or held in memory:
the response is streamed and rows are discarded as they arrive unless they belong to a tract we have
actually loaded and fall inside the year window. Peak memory is therefore set by the number of
loaded tracts (thousands), not by the file (millions of rows).

Rows are filtered against the `areas` table rather than by state, so loading a new region
automatically widens what this source collects with no change here.

**Coverage is uneven by design of the underlying index, and that is not a bug to chase.** Measured on
the 2026 file: Austin 321/503 tracts (64%), NYC 532/2,327 (23%). FHFA builds this index from repeat
sales carrying conforming (Fannie/Freddie) mortgages, which NYC's co-op-dominated market largely does
not generate — of 1,752 NYC tracts with no value, only 6 appear in the file at all, and those are
published blank. Scoring treats a missing metric as neutral and records the shortfall in `coverage`,
so the honest answer surfaces as low confidence rather than as a confident wrong number.
"""

import csv
from collections.abc import Iterable, Iterator
from datetime import date

from app.models import Area
from app.sources.base import Source, SourceContext, SourceSkipped

HPI_URL = "https://www.fhfa.gov/hpi/download/annual/hpi_at_tract.csv"
# Columns: tract,state_abbr,year,annual_change,hpi,hpi1990,hpi2000
YEAR_WINDOW = 15  # enough for a 10-year CAGR plus slack for tracts whose latest year lags
HORIZONS = {"hpi_cagr_5y": 5, "hpi_cagr_10y": 10}


def stream_rows(ctx: SourceContext, url: str = HPI_URL) -> Iterator[dict[str, str]]:
    """Yield the CSV a row at a time straight off the socket, so the 90MB file never lands on disk
    or in memory in full."""
    with ctx.http.stream("GET", url, timeout=600, follow_redirects=True) as response:
        response.raise_for_status()
        yield from csv.DictReader(response.iter_lines())


def collect_index(rows: Iterable[dict[str, str]], wanted: set[str], min_year: int) -> dict[str, dict[int, float]]:
    """tract -> {year: index}, keeping only loaded tracts inside the year window."""
    by_tract: dict[str, dict[int, float]] = {}
    for row in rows:
        tract = (row.get("tract") or "").strip()
        if tract not in wanted:
            continue
        try:
            year = int(row["year"])
            index = float(row["hpi"])
        except (TypeError, ValueError, KeyError):
            continue  # suppressed or malformed tract-years are published as blanks
        if year >= min_year and index > 0:
            by_tract.setdefault(tract, {})[year] = index
    return by_tract


def compute_cagrs(by_tract: dict[str, dict[int, float]]) -> dict[str, dict[str, float]]:
    """Compound annual growth between each tract's latest year and that year minus the horizon.

    The baseline year must be present exactly — interpolating across a gap would invent an index
    value and report it with the same confidence as a measured one.
    """
    metrics: dict[str, dict[str, float]] = {metric: {} for metric in HORIZONS}
    metrics["hpi_annual_change"] = {}
    for tract, series in by_tract.items():
        latest_year = max(series)
        latest = series[latest_year]
        for metric, years in HORIZONS.items():
            start = series.get(latest_year - years)
            if start:
                metrics[metric][tract] = round((latest / start) ** (1 / years) - 1, 6)
        previous = series.get(latest_year - 1)
        if previous:
            metrics["hpi_annual_change"][tract] = round(latest / previous - 1, 6)
    return metrics


class FhfaTractHpi(Source):
    kind = "neighborhood"
    coverage = "national"
    granularity = "tract"
    description = "FHFA annual house price index by census tract (developmental, not seasonally adjusted)"
    probe_url = HPI_URL

    def run(self, ctx: SourceContext) -> int:
        wanted = {code for (code,) in ctx.session.query(Area.code).filter(Area.kind == "tract")}
        if not wanted:
            raise SourceSkipped("no tracts loaded; run `app.cli add-region <metro>` first")
        min_year = date.today().year - YEAR_WINDOW
        by_tract = collect_index(stream_rows(ctx), wanted, min_year)
        if not by_tract:
            raise SourceSkipped("no matching tract-years in the FHFA file")
        metrics = compute_cagrs(by_tract)
        latest_year = max(max(series) for series in by_tract.values())
        as_of = dict.fromkeys(metrics, str(latest_year))
        return self.write_area_metrics(ctx, metrics, as_of, kind="tract")
