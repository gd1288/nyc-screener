"""Read GitHub state through the `gh` CLI, cached.

Read-only by design: this module lists issues, pull requests and checks, and does not create,
comment, merge or close anything. Opening a PR is a deliberate act that belongs in a session where
someone reviews the diff, not behind a button that a stale browser tab can press.

Like `checks.py`, every command is a fixed argv with `shell=False`. Caller input reaches only
tightly-validated slots — a state enum and a bounded integer — never the argv as a raw string.

Results are cached for 60s because the Workbench polls, and `gh` hits the network on every call.
"""

import json
import subprocess
import time
from typing import Any

from app.config import PROJECT_DIR

CACHE_SECONDS = 60
TIMEOUT = 30
MAX_LIMIT = 100
ISSUE_FIELDS = "number,title,state,labels,updatedAt,url,author"
PR_FIELDS = "number,title,state,isDraft,labels,updatedAt,url,headRefName,statusCheckRollup"

_cache: dict[tuple, tuple[float, Any]] = {}


class GhUnavailable(RuntimeError):
    """`gh` is missing, unauthenticated, or the directory isn't a GitHub repo."""


def _run_json(argv: tuple[str, ...]) -> Any:
    key = argv
    now = time.monotonic()
    if key in _cache:
        cached_at, value = _cache[key]
        if now - cached_at < CACHE_SECONDS:
            return value
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv built from validated enums/ints
            list(argv), cwd=PROJECT_DIR, capture_output=True, text=True, timeout=TIMEOUT, shell=False
        )
    except FileNotFoundError as e:
        raise GhUnavailable("the `gh` CLI is not installed or not on PATH") from e
    except subprocess.TimeoutExpired as e:
        raise GhUnavailable(f"`gh` timed out after {TIMEOUT}s") from e
    if completed.returncode != 0:
        raise GhUnavailable((completed.stderr or completed.stdout).strip()[:400] or "gh failed")
    try:
        value = json.loads(completed.stdout or "[]")
    except ValueError as e:
        raise GhUnavailable("gh returned output that isn't JSON") from e
    _cache[key] = (now, value)
    return value


def _clean_limit(limit: int) -> str:
    return str(max(1, min(int(limit), MAX_LIMIT)))


def _clean_state(state: str, allowed: tuple[str, ...]) -> str:
    if state not in allowed:
        raise ValueError(f"state must be one of {allowed}")
    return state


def list_issues(state: str = "open", limit: int = 50) -> list[dict]:
    return _run_json(
        (
            "gh",
            "issue",
            "list",
            "--state",
            _clean_state(state, ("open", "closed", "all")),
            "--limit",
            _clean_limit(limit),
            "--json",
            ISSUE_FIELDS,
        )
    )


def list_pull_requests(state: str = "open", limit: int = 50) -> list[dict]:
    return _run_json(
        (
            "gh",
            "pr",
            "list",
            "--state",
            _clean_state(state, ("open", "closed", "merged", "all")),
            "--limit",
            _clean_limit(limit),
            "--json",
            PR_FIELDS,
        )
    )


def board(issues: list[dict]) -> dict[str, list[dict]]:
    """Group issues into roadmap columns by label, mirroring the plan's board.

    An issue with no recognised label lands in Backlog rather than being dropped — a board that
    silently hides work is worse than one with an untidy first column.
    """
    columns: dict[str, list[dict]] = {c: [] for c in ("Backlog", "Planned", "In progress", "In review", "Done")}
    by_label = {"planned": "Planned", "in-progress": "In progress", "in-review": "In review"}
    for issue in issues:
        if issue.get("state") == "CLOSED":
            columns["Done"].append(issue)
            continue
        labels = {label.get("name", "") for label in issue.get("labels") or []}
        column = next((by_label[name] for name in by_label if name in labels), "Backlog")
        columns[column].append(issue)
    return columns


def clear_cache() -> None:
    _cache.clear()
