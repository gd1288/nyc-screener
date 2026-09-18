"""Workbench API — local developer tooling.

This router is only registered when `DEV_TOOLS=1` (see `main.py`). Registration, not a per-request
guard, is the gate: an unregistered router cannot be reached, cannot appear in `/docs`, and cannot
be switched on by a refactor that forgets a check.

Three guards apply to every request here:

- **The client must be loopback.** A request from another host is refused even if someone binds the
  server publicly by mistake.
- **An `Origin`, when present, must be allowed.** This is what stops a page on another origin from
  driving the Workbench in a browser where the developer has it running.
- **A custom header must be present.** Origin alone cannot carry the check: browsers omit `Origin`
  on same-origin GETs, so requiring it rejected the real Workbench page (verified in the browser,
  not assumed). A custom header is the standard replacement — a cross-origin page cannot set one on
  a simple request without triggering a preflight, and the preflight is refused for any origin
  outside `cors_origins`. It also keeps out `curl` and anything else that isn't our own client.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.dev import checks, github, runner

router = APIRouter(prefix="/api/dev")

LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
CLIENT_HEADER = "x-requested-with"
CLIENT_HEADER_VALUE = "nyc-screener-workbench"


def _allowed_origins() -> set[str]:
    return {o.strip() for o in get_settings().cors_origins.split(",") if o.strip()}


def guard(request: Request) -> None:
    """Refuse anything that isn't our own client, running on this machine."""
    client_host = request.client.host if request.client else None
    if client_host not in LOOPBACK_HOSTS:
        raise HTTPException(403, "Workbench is available from this machine only")
    # Only checked when present: browsers omit Origin on same-origin GETs, so requiring it would
    # reject the Workbench page itself. When a browser does send one, a foreign origin is refused.
    origin = request.headers.get("origin")
    if origin is not None and origin not in _allowed_origins():
        raise HTTPException(403, "Workbench does not accept requests from that origin")
    # The header that actually carries the check. A cross-origin page cannot set it on a simple
    # request without a preflight, and the preflight is refused for origins outside cors_origins.
    if request.headers.get(CLIENT_HEADER) != CLIENT_HEADER_VALUE:
        raise HTTPException(403, "Workbench requires a request from its own client")


def db():
    with SessionLocal() as session:
        yield session


@router.get("/checks", dependencies=[Depends(guard)])
def list_checks():
    return checks.list_checks()


@router.post("/checks/{key}", dependencies=[Depends(guard)])
def run_check(key: str):
    """Runs one named check. The key selects a fixed argv from `checks.CHECKS`; nothing the caller
    sends becomes part of a command."""
    try:
        result = checks.run_check(key)
    except KeyError as e:
        raise HTTPException(404, f"Unknown check: {key}") from e
    return result


@router.get("/issues", dependencies=[Depends(guard)])
def list_issues(state: str = "open", limit: int = 50):
    try:
        issues = github.list_issues(state, limit)
    except github.GhUnavailable as e:
        raise HTTPException(503, str(e)) from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return {"issues": issues, "board": github.board(issues)}


@router.get("/pull-requests", dependencies=[Depends(guard)])
def list_pull_requests(state: str = "open", limit: int = 50):
    try:
        return github.list_pull_requests(state, limit)
    except github.GhUnavailable as e:
        raise HTTPException(503, str(e)) from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.get("/runs", dependencies=[Depends(guard)])
def list_runs(limit: int = 25, session: Session = Depends(db)):
    return {
        "runs": [
            {
                "id": r.id,
                "kind": r.kind,
                "issue_number": r.issue_number,
                "branch": r.branch,
                "worktree_path": r.worktree_path,
                "budget_usd": r.budget_usd,
                "cost_usd": r.cost_usd,
                "turns": r.turns,
                "duration_seconds": r.duration_seconds,
                "status": r.status,
                "result": (r.result or "")[:2000],
                "started_at": r.started_at.isoformat(),
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            }
            for r in runner.recent_runs(session, limit)
        ],
        "usage": runner.usage_summary(session),
        "claude_available": runner.claude_available(),
    }


class RunIn(BaseModel):
    kind: str
    prompt: str
    name: str
    # The ceiling is enforced in `runner.RunSpec.validate` too; declaring it here as well means an
    # over-budget request is rejected by validation before any worktree is created.
    budget_usd: float = Field(default=runner.DEFAULT_BUDGET_USD, gt=0, le=runner.MAX_BUDGET_USD)
    goal: str | None = None
    issue_number: int | None = None
    plan_mode: bool = False


@router.post("/runs", dependencies=[Depends(guard)])
def start_run(body: RunIn, session: Session = Depends(db)):
    """Start an unattended run in its own worktree. Synchronous: it returns when the run finishes.

    Never merges, never pushes, never touches the main working tree — the output is a branch to
    review.
    """
    spec = runner.RunSpec(
        kind=body.kind,
        prompt=body.prompt,
        name=body.name,
        budget_usd=body.budget_usd,
        goal=body.goal,
        issue_number=body.issue_number,
        plan_mode=body.plan_mode,
    )
    try:
        run = runner.start_run(session, spec)
    except runner.RunnerError as e:
        raise HTTPException(422, str(e)) from e
    return {"id": run.id, "status": run.status, "branch": run.branch, "cost_usd": run.cost_usd}


@router.get("/diagnose", dependencies=[Depends(guard)])
def diagnose():
    """The Debug tab's data: the same health snapshot `app.cli diagnose` prints."""
    return checks.run_check("diagnose")
