"""Start a headless `claude -p` run from the Workbench, bounded and isolated.

Two limits are structural here, not configuration, because they are the difference between a useful
button and an expensive accident:

1. **`MAX_BUDGET_USD` is a ceiling the API cannot exceed.** A request asking for more is rejected
   rather than clamped — silently lowering a caller's budget would make a run stop halfway and look
   like the model gave up. A default alone would not help: the danger is a UI bug or a double-click
   sending a large number, not a human choosing one.
2. **Every run gets its own git worktree.** The main working tree is never a target, so an
   unattended run cannot overwrite uncommitted work, and a bad run is discarded by deleting a
   directory rather than by unpicking commits.

Runs never merge, never push, and never touch the main branch. The output is a branch to review.
"""

import json
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import PROJECT_DIR
from app.models import AgentRun

MAX_BUDGET_USD = 0.50  # hard ceiling; requests above this are refused, not clamped
DEFAULT_BUDGET_USD = 0.25
DEFAULT_TIMEOUT = 1800
WORKTREE_ROOT = PROJECT_DIR / ".claude" / "worktrees"
SAFE_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,48}$")
MAX_PROMPT_CHARS = 8000

# Runs get the project's own checks and editing tools, never a shell escape hatch and never network
# write access. `Bash` is deliberately absent: a headless run that can shell out can also push.
ALLOWED_TOOLS = ("Read", "Write", "Edit", "Glob", "Grep")

KINDS = ("plan", "implement", "debug", "research")


class RunnerError(RuntimeError):
    pass


@dataclass
class RunSpec:
    kind: str
    prompt: str
    name: str  # worktree/branch suffix, e.g. "issue-12"
    budget_usd: float = DEFAULT_BUDGET_USD
    goal: str | None = None
    issue_number: int | None = None
    timeout: int = DEFAULT_TIMEOUT
    plan_mode: bool = False

    def validate(self) -> None:
        if self.kind not in KINDS:
            raise RunnerError(f"kind must be one of {KINDS}")
        if not SAFE_NAME.match(self.name):
            raise RunnerError("name must be lowercase letters, digits and hyphens")
        if not self.prompt.strip():
            raise RunnerError("prompt is empty")
        if len(self.prompt) > MAX_PROMPT_CHARS:
            raise RunnerError(f"prompt exceeds {MAX_PROMPT_CHARS} characters")
        if not 0 < self.budget_usd <= MAX_BUDGET_USD:
            raise RunnerError(f"budget must be >0 and <= {MAX_BUDGET_USD:.2f} USD")


def claude_available() -> bool:
    return shutil.which("claude") is not None


def _git(*args: str, cwd: Path = PROJECT_DIR) -> str:
    completed = subprocess.run(  # noqa: S603 - fixed argv; `name` is validated against SAFE_NAME
        ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=120, shell=False
    )
    if completed.returncode != 0:
        raise RunnerError(f"git {' '.join(args)}: {(completed.stderr or completed.stdout).strip()[:300]}")
    return completed.stdout.strip()


def create_worktree(name: str) -> tuple[Path, str]:
    """A fresh worktree and branch for this run. Never the main tree — see the module docstring."""
    if not SAFE_NAME.match(name):
        raise RunnerError("unsafe worktree name")
    WORKTREE_ROOT.mkdir(parents=True, exist_ok=True)
    path = WORKTREE_ROOT / name
    branch = f"agent/{name}"
    if path.exists():
        raise RunnerError(f"worktree {name} already exists at {path}; remove it before rerunning")
    _git("worktree", "add", "-b", branch, str(path))
    return path, branch


def remove_worktree(name: str) -> None:
    path = WORKTREE_ROOT / name
    if path.exists():
        _git("worktree", "remove", "--force", str(path))


def build_argv(spec: RunSpec) -> list[str]:
    prompt = spec.prompt if not spec.goal else f"{spec.prompt}\n\n/goal {spec.goal}"
    return [
        "claude",
        "-p",
        prompt,
        "--output-format",
        "json",
        "--allowedTools",
        ",".join(ALLOWED_TOOLS),
        "--permission-mode",
        "plan" if spec.plan_mode else "acceptEdits",
        "--max-budget-usd",
        f"{spec.budget_usd:.2f}",
    ]


def _parse_output(stdout: str) -> dict:
    """`--output-format json` emits one object; be tolerant of anything else rather than losing the
    run's record because the shape changed."""
    try:
        payload = json.loads(stdout)
    except ValueError:
        return {"result": stdout[-4000:]}
    if isinstance(payload, list):
        payload = payload[-1] if payload else {}
    return payload if isinstance(payload, dict) else {"result": str(payload)[:4000]}


def start_run(session: Session, spec: RunSpec) -> AgentRun:
    """Run to completion, recording the attempt before it starts so a crash still leaves evidence."""
    spec.validate()
    if not claude_available():
        raise RunnerError("the `claude` CLI is not on PATH")

    path, branch = create_worktree(spec.name)
    run = AgentRun(
        kind=spec.kind,
        issue_number=spec.issue_number,
        prompt=spec.prompt,
        branch=branch,
        worktree_path=str(path),
        budget_usd=spec.budget_usd,
        status="running",
    )
    session.add(run)
    session.commit()

    started = time.monotonic()
    try:
        completed = subprocess.run(  # noqa: S603 - argv built above; prompt is an argv element, not a shell string
            build_argv(spec), cwd=path, capture_output=True, text=True, timeout=spec.timeout, shell=False
        )
        payload = _parse_output(completed.stdout)
        run.status = "ok" if completed.returncode == 0 else "error"
        run.result = (payload.get("result") or completed.stderr or "")[:8000]
        run.cost_usd = payload.get("total_cost_usd") or payload.get("cost_usd")
        run.turns = payload.get("num_turns")
    except subprocess.TimeoutExpired:
        run.status = "timeout"
        run.result = f"Timed out after {spec.timeout}s. The worktree is left in place for inspection."
    finally:
        run.duration_seconds = round(time.monotonic() - started, 2)
        run.finished_at = datetime.now()
        session.commit()
    return run


def recent_runs(session: Session, limit: int = 25) -> list[AgentRun]:
    return session.query(AgentRun).order_by(AgentRun.id.desc()).limit(min(max(limit, 1), 100)).all()


def usage_summary(session: Session) -> dict:
    """What the Workbench shows to keep the cost of unattended work visible rather than incidental."""
    runs = session.query(AgentRun).all()
    spent = sum(r.cost_usd or 0.0 for r in runs)
    by_kind: dict[str, dict] = {}
    for run in runs:
        bucket = by_kind.setdefault(run.kind, {"runs": 0, "cost_usd": 0.0})
        bucket["runs"] += 1
        bucket["cost_usd"] = round(bucket["cost_usd"] + (run.cost_usd or 0.0), 4)
    return {
        "runs": len(runs),
        "total_cost_usd": round(spent, 4),
        "by_kind": by_kind,
        "max_budget_usd": MAX_BUDGET_USD,
    }
