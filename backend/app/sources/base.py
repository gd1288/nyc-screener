"""Plug-in contract for data sources.

To add a source: subclass `Source`, implement `run`, and add an entry to sources.yaml.
"""

from dataclasses import dataclass, field
from typing import Any, ClassVar

import httpx
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import Settings
from app.geo import NeighborhoodIndex
from app.models import NeighborhoodMetric


@dataclass
class SourceContext:
    session: Session
    settings: Settings
    http: httpx.Client
    _geo: NeighborhoodIndex | None = field(default=None, repr=False)

    @property
    def geo(self) -> NeighborhoodIndex:
        if self._geo is None:
            self._geo = NeighborhoodIndex.load(self.session)
        return self._geo


class SourceSkipped(Exception):
    """Raised when a source can't run (e.g. missing API key); recorded as 'skipped', not 'error'."""


class Source:
    #: "boundaries", "neighborhood" (writes metrics), "sales", "listings" or "sold_check"
    kind: ClassVar[str]
    #: env settings that must be non-empty for this source to run, e.g. ["rentcast_api_key"]
    requires: ClassVar[list[str]] = []
    description: ClassVar[str] = ""
    #: (domain, dataset) for a free, no-write `$limit=1` reachability check used by
    #: `app.cli probe-sources`. Set this whenever the source is backed by a single Socrata
    #: dataset. Leave both this and `probe_url` unset (the default `probe()` then reports
    #: "not probed", not a failure) when there's no cheap safe check, or override `probe()`
    #: directly — see `RentCastListings`, whose probe is disabled on purpose to protect its
    #: request budget (this is the one case `app.cli probe-sources` must never bypass).
    probe_socrata: ClassVar[tuple[str, str] | None] = None
    #: A plain URL for a HEAD-request reachability check, for non-Socrata HTTP sources.
    probe_url: ClassVar[str | None] = None

    def __init__(self, name: str, **options: Any):
        self.name = name
        self.options = options

    def missing_requirements(self, settings: Settings) -> list[str]:
        return [key for key in self.requires if not getattr(settings, key, "")]

    def run(self, ctx: SourceContext) -> int:
        """Fetch and store data. Returns the number of records written."""
        raise NotImplementedError

    def probe(self, ctx: SourceContext) -> tuple[bool | None, str]:
        """Cheap, side-effect-free reachability check independent of `run`, used by
        `app.cli probe-sources`. Returns (ok, detail); ok=None means "not probed" (no probe
        configured for this source) — that's a gap to close, not a failure."""
        from app.sources import socrata  # local import: avoid a module cycle at import time

        if self.probe_socrata is not None:
            domain, dataset = self.probe_socrata
            try:
                rows = list(socrata.query(ctx.http, domain, dataset, limit=1))
                return True, f"{domain}/{dataset}: reachable ({len(rows)} row fetched)"
            except Exception as e:  # noqa: BLE001 - report any failure, don't crash the probe run
                return False, f"{domain}/{dataset}: {type(e).__name__}: {e}"
        if self.probe_url is not None:
            try:
                resp = ctx.http.head(self.probe_url, timeout=15, follow_redirects=True)
                if resp.status_code >= 400:  # some hosts reject HEAD; retry with a real GET
                    resp = ctx.http.get(self.probe_url, timeout=15, follow_redirects=True)
                return resp.status_code < 400, f"{self.probe_url}: HTTP {resp.status_code}"
            except Exception as e:  # noqa: BLE001
                return False, f"{self.probe_url}: {type(e).__name__}: {e}"
        return None, "no probe configured (see the add-data-source skill)"

    # ---- helpers for neighborhood sources ----
    def write_metrics(
        self, ctx: SourceContext, metrics: dict[str, dict[str, float | None]], as_of: dict[str, str]
    ) -> int:
        """Replace this source's metrics. `metrics` maps metric name -> {nta_code: value}."""
        ctx.session.execute(
            delete(NeighborhoodMetric).where(
                NeighborhoodMetric.source == self.name, NeighborhoodMetric.metric.in_(list(metrics))
            )
        )
        n = 0
        for metric, by_nta in metrics.items():
            for nta, value in by_nta.items():
                if value is None or value != value:  # skip None/NaN
                    continue
                ctx.session.add(
                    NeighborhoodMetric(
                        nta_code=nta, metric=metric, value=float(value), source=self.name, as_of=as_of.get(metric, "")
                    )
                )
                n += 1
        ctx.session.commit()
        return n
