"""Run the project's own checks and report trimmed results.

Every command is a fixed `list[str]` argv chosen from `CHECKS` by name. Nothing the caller sends
reaches a shell, an argument, or a path: the API takes a check *key*, and an unknown key is a 404.
`shell=False` throughout, so there is no string for a caller to inject into.

That strictness is the point. This module exists to let a local Workbench press "run the tests", and
the naive version — accept a command and run it — would turn a localhost dev convenience into
arbitrary code execution reachable from any page the developer happens to have open.
"""

import subprocess
import time
from dataclasses import dataclass, field

from app.config import BACKEND_DIR, PROJECT_DIR

MAX_OUTPUT_LINES = 60  # a full pytest log is not a UI; the tail is where the failure is
DEFAULT_TIMEOUT = 900


@dataclass(frozen=True)
class CheckDef:
    key: str
    label: str
    argv: tuple[str, ...]
    cwd: str  # "backend" | "frontend" | "root"
    description: str = ""
    timeout: int = DEFAULT_TIMEOUT


CHECKS: dict[str, CheckDef] = {
    c.key: c
    for c in [
        CheckDef("ruff", "Lint (ruff)", ("uv", "run", "ruff", "check", "."), "backend"),
        CheckDef("pytest", "Backend tests", ("uv", "run", "pytest", "-q"), "backend"),
        CheckDef("tsc", "Types (tsc)", ("npx", "tsc", "--noEmit"), "frontend"),
        CheckDef("lint", "Lint (eslint)", ("npm", "run", "lint"), "frontend"),
        CheckDef("build", "Frontend build", ("npm", "run", "build"), "frontend"),
        CheckDef(
            "valuation-eval",
            "Valuation accuracy gate",
            ("uv", "run", "python", "-m", "app.cli", "valuation-eval"),
            "backend",
            "Fails if median error regressed against research/evals/baseline.json",
        ),
        CheckDef("backtest", "Growth-score backtest", ("uv", "run", "python", "-m", "app.cli", "backtest"), "backend"),
        CheckDef("status", "Phase status", ("uv", "run", "python", "-m", "app.cli", "status"), "backend"),
        CheckDef("diagnose", "Data health", ("uv", "run", "python", "-m", "app.cli", "diagnose"), "backend"),
    ]
}

_CWDS = {"backend": BACKEND_DIR, "frontend": PROJECT_DIR / "frontend", "root": PROJECT_DIR}


@dataclass
class CheckResult:
    key: str
    label: str
    ok: bool
    exit_code: int | None
    duration_seconds: float
    output: str
    truncated: bool = False
    command: list[str] = field(default_factory=list)


def _trim(text: str) -> tuple[str, bool]:
    lines = text.strip().splitlines()
    if len(lines) <= MAX_OUTPUT_LINES:
        return "\n".join(lines), False
    return "\n".join(lines[-MAX_OUTPUT_LINES:]), True


def run_check(key: str) -> CheckResult:
    check = CHECKS.get(key)
    if check is None:
        raise KeyError(key)
    started = time.monotonic()
    try:
        completed = subprocess.run(  # noqa: S603 - argv is a fixed tuple from CHECKS, never caller input
            list(check.argv),
            cwd=_CWDS[check.cwd],
            capture_output=True,
            text=True,
            timeout=check.timeout,
            shell=False,
        )
        output, truncated = _trim(f"{completed.stdout}\n{completed.stderr}")
        exit_code: int | None = completed.returncode
    except subprocess.TimeoutExpired:
        output, truncated, exit_code = f"Timed out after {check.timeout}s", False, None
    except FileNotFoundError as e:
        # e.g. npx/uv missing on PATH — a real condition worth reporting, not a crash.
        output, truncated, exit_code = f"Command not found: {e}", False, None
    return CheckResult(
        key=check.key,
        label=check.label,
        ok=exit_code == 0,
        exit_code=exit_code,
        duration_seconds=round(time.monotonic() - started, 2),
        output=output,
        truncated=truncated,
        command=list(check.argv),
    )


def list_checks() -> list[dict]:
    return [
        {"key": c.key, "label": c.label, "description": c.description, "cwd": c.cwd, "command": list(c.argv)}
        for c in CHECKS.values()
    ]
