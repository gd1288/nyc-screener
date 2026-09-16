"""Loads data sources from sources.yaml and runs them, logging each run to source_runs."""

import importlib
import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx
import yaml

from app.config import get_settings
from app.db import SessionLocal
from app.models import SourceRun
from app.sources.base import Source, SourceContext, SourceSkipped

log = logging.getLogger(__name__)


@dataclass
class SourceEntry:
    name: str
    source: Source
    enabled: bool
    schedule: str | None  # cron expression, or None for manual-only
    order: int


def load_config() -> dict[str, Any]:
    with open(get_settings().sources_file) as f:
        return yaml.safe_load(f)


def load_sources() -> list[SourceEntry]:
    entries = []
    for i, (name, cfg) in enumerate(load_config()["sources"].items()):
        module_name, class_name = cfg["adapter"].rsplit(".", 1)
        cls = getattr(importlib.import_module(module_name), class_name)
        entries.append(
            SourceEntry(
                name=name,
                source=cls(name, **cfg.get("options", {})),
                enabled=cfg.get("enabled", True),
                schedule=cfg.get("schedule"),
                order=i,
            )
        )
    return entries


def get_source(name: str) -> SourceEntry:
    for entry in load_sources():
        if entry.name == name:
            return entry
    raise KeyError(name)


_run_lock = threading.Lock()


def is_running() -> bool:
    return _run_lock.locked()


def run_source(entry: SourceEntry) -> SourceRun:
    settings = get_settings()
    with SessionLocal() as session:
        run = SourceRun(source=entry.name, status="running")
        session.add(run)
        session.commit()
        missing = entry.source.missing_requirements(settings)
        try:
            if missing:
                raise SourceSkipped(f"Missing settings: {', '.join(k.upper() for k in missing)}")
            with httpx.Client(follow_redirects=True, headers={"User-Agent": "nyc-screener/0.1"}) as http:
                run.records = entry.source.run(SourceContext(session=session, settings=settings, http=http))
            run.status = "ok"
        except SourceSkipped as e:
            session.rollback()
            run.status, run.message = "skipped", str(e)
        except Exception as e:  # keep other sources running
            session.rollback()
            log.exception("Source %s failed", entry.name)
            run.status, run.message = "error", f"{type(e).__name__}: {e}"[:2000]
        run.finished_at = datetime.now()
        session.add(run)
        session.commit()
        return run


def run_pipeline(names: list[str] | None = None) -> list[SourceRun]:
    """Run sources (all enabled ones by default) in config order, then recompute scores."""
    from app.scoring.neighborhood import recompute_scores

    if not _run_lock.acquire(blocking=False):
        raise RuntimeError("A refresh is already running.")
    try:
        entries = [e for e in load_sources() if e.enabled and (names is None or e.name in names)]
        runs = [run_source(e) for e in entries]
        with SessionLocal() as session:
            recompute_scores(session)
        return runs
    finally:
        _run_lock.release()
