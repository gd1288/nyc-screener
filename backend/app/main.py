"""FastAPI app. Run with: uv run uvicorn app.main:app --reload"""

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings
from app.db import init_db
from app.sources.registry import load_sources, run_pipeline

log = logging.getLogger("app")


def _scheduled_run(name: str) -> None:
    try:
        run_pipeline([name])
    except RuntimeError:
        log.info("Skipped scheduled run of %s: another refresh is running", name)


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="America/New_York")
    for entry in load_sources():
        if entry.enabled and entry.schedule:
            scheduler.add_job(_scheduled_run, CronTrigger.from_crontab(entry.schedule, timezone="America/New_York"),
                              args=[entry.name], id=entry.name, misfire_grace_time=3600, coalesce=True)
    scheduler.start()
    return scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    init_db()
    scheduler = start_scheduler() if get_settings().scheduler_enabled else None
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(title="NYC Condo Screener", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
