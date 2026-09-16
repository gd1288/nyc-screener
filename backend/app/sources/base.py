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

    def __init__(self, name: str, **options: Any):
        self.name = name
        self.options = options

    def missing_requirements(self, settings: Settings) -> list[str]:
        return [key for key in self.requires if not getattr(settings, key, "")]

    def run(self, ctx: SourceContext) -> int:
        """Fetch and store data. Returns the number of records written."""
        raise NotImplementedError

    # ---- helpers for neighborhood sources ----
    def write_metrics(self, ctx: SourceContext, metrics: dict[str, dict[str, float | None]], as_of: dict[str, str]) -> int:
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
