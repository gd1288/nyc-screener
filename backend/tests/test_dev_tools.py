"""Workbench dev tooling.

Most of these are security tests. This module runs commands and spends money, and it is reachable
from a browser on the developer's own machine — so the tests that matter are the ones proving what
it *refuses*.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import dev as dev_api
from app.dev import checks, github, runner

ALLOWED_ORIGIN = "http://localhost:3000"
CLIENT_HEADER = dev_api.CLIENT_HEADER
CLIENT_HEADERS = {CLIENT_HEADER: dev_api.CLIENT_HEADER_VALUE}


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(dev_api.router)
    # TestClient reports a client host of "testclient" unless told otherwise, which the loopback
    # guard correctly refuses — so say explicitly that these requests come from the local machine.
    return TestClient(app, client=("127.0.0.1", 50000))


# ------------------------------------------------------------------ the guard


def test_a_request_without_the_client_header_is_refused(client):
    """curl, scripts, and any page that isn't ours. Origin cannot carry this check on its own:
    browsers omit Origin on same-origin GETs, so requiring it rejected the real Workbench page —
    found by loading the page, not by reasoning about it."""
    response = client.get("/api/dev/checks")
    assert response.status_code == 403
    assert "own client" in response.json()["detail"]


def test_the_client_header_must_match_exactly(client):
    for value in ("", "nope", "nyc-screener", "NYC-SCREENER-WORKBENCH "):
        assert client.get("/api/dev/checks", headers={CLIENT_HEADER: value}).status_code == 403


@pytest.mark.parametrize("origin", ["http://evil.example", "null", "http://localhost:3001"])
def test_a_request_from_a_disallowed_origin_is_refused_even_with_the_header(client, origin):
    """A cross-origin page in the developer's browser does send Origin, so this is the guard that
    stops it driving the Workbench."""
    response = client.get("/api/dev/checks", headers={**CLIENT_HEADERS, "origin": origin})
    assert response.status_code == 403
    assert "origin" in response.json()["detail"].lower()


def test_a_same_origin_request_with_no_origin_header_is_accepted(client):
    """The real Workbench path: a same-origin GET through the Next proxy carries no Origin."""
    assert client.get("/api/dev/checks", headers=CLIENT_HEADERS).status_code == 200


def test_an_allowed_browser_origin_on_loopback_is_accepted(client):
    assert client.get("/api/dev/checks", headers={**CLIENT_HEADERS, "origin": ALLOWED_ORIGIN}).status_code == 200


@pytest.mark.parametrize("host", ["10.0.0.5", "203.0.113.9", None])
def test_a_non_loopback_client_is_refused(host):
    """Defence in depth: if the server is ever bound publicly by mistake, the origin check alone
    would not stop a request that forges the header. The guard is exercised directly here rather
    than through TestClient, so the refusal is asserted on the rule itself."""
    from fastapi import HTTPException

    class _Request:
        client = type("C", (), {"host": host})() if host else None
        headers = {**CLIENT_HEADERS, "origin": ALLOWED_ORIGIN}

    with pytest.raises(HTTPException) as excinfo:
        dev_api.guard(_Request())
    assert excinfo.value.status_code == 403
    assert "this machine only" in excinfo.value.detail


def test_the_dev_router_is_not_registered_unless_dev_tools_is_enabled():
    """Registration, not a per-request guard, is the real gate — an unregistered router can't be
    reached and can't show up in /docs."""
    from app.config import get_settings
    from app.main import app

    assert get_settings().dev_tools is False
    assert not [r for r in app.routes if str(getattr(r, "path", "")).startswith("/api/dev")]


# ------------------------------------------------------------------ checks


def test_every_check_is_a_fixed_argv_with_no_shell():
    """Nothing a caller sends may become part of a command."""
    for check in checks.CHECKS.values():
        assert isinstance(check.argv, tuple)
        assert all(isinstance(part, str) for part in check.argv)
        assert not any(";" in part or "|" in part or "&&" in part for part in check.argv)
        assert check.cwd in {"backend", "frontend", "root"}


def test_an_unknown_check_key_is_a_404_not_a_command(client):
    response = client.post("/api/dev/checks/rm-rf", headers=CLIENT_HEADERS)
    assert response.status_code == 404


def test_running_a_real_check_reports_its_result(client):
    """`status` reads only the phase manifest and the filesystem, so it is safe and fast here."""
    response = client.post("/api/dev/checks/status", headers=CLIENT_HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert "Phase" in body["output"]
    assert body["command"][0] == "uv"


def test_long_output_is_trimmed_to_the_tail():
    """A full pytest log is not a UI, and the failure is at the end."""
    text = "\n".join(str(i) for i in range(500))
    trimmed, truncated = checks._trim(text)
    assert truncated is True
    assert len(trimmed.splitlines()) == checks.MAX_OUTPUT_LINES
    assert trimmed.endswith("499")


# ------------------------------------------------------------------ github


def test_board_groups_issues_by_label_and_keeps_unlabelled_work_visible():
    """A board that silently drops work is worse than one with an untidy first column."""
    issues = [
        {"number": 1, "state": "OPEN", "labels": [{"name": "planned"}]},
        {"number": 2, "state": "OPEN", "labels": []},
        {"number": 3, "state": "OPEN", "labels": [{"name": "in-progress"}]},
        {"number": 4, "state": "CLOSED", "labels": [{"name": "planned"}]},
        {"number": 5, "state": "OPEN", "labels": [{"name": "some-other-label"}]},
    ]
    board = github.board(issues)
    assert [i["number"] for i in board["Planned"]] == [1]
    assert [i["number"] for i in board["Backlog"]] == [2, 5]
    assert [i["number"] for i in board["In progress"]] == [3]
    assert [i["number"] for i in board["Done"]] == [4]


@pytest.mark.parametrize("state", ["; rm -rf /", "open; echo", "deleted"])
def test_an_invalid_issue_state_is_rejected_before_reaching_gh(state):
    with pytest.raises(ValueError):
        github.list_issues(state=state)


@pytest.mark.parametrize("limit, expected", [(0, "1"), (5, "5"), (99999, "100"), (-3, "1")])
def test_limit_is_clamped_to_a_sane_range(limit, expected):
    assert github._clean_limit(limit) == expected


# ------------------------------------------------------------------ runner


def _spec(**kw):
    defaults = {"kind": "implement", "prompt": "do the thing", "name": "issue-12"}
    return runner.RunSpec(**{**defaults, **kw})


def test_a_budget_above_the_ceiling_is_refused_not_clamped():
    """Clamping would make a run stop halfway and look like the model gave up. The ceiling exists
    for a UI bug or a double-click, not for a human choosing a number."""
    with pytest.raises(runner.RunnerError, match="budget"):
        _spec(budget_usd=runner.MAX_BUDGET_USD + 0.01).validate()


@pytest.mark.parametrize("budget", [0, -1])
def test_a_non_positive_budget_is_refused(budget):
    with pytest.raises(runner.RunnerError):
        _spec(budget_usd=budget).validate()


def test_the_api_rejects_an_over_budget_run_before_creating_a_worktree(client):
    response = client.post(
        "/api/dev/runs",
        headers=CLIENT_HEADERS,
        json={"kind": "implement", "prompt": "x", "name": "issue-1", "budget_usd": 25},
    )
    assert response.status_code == 422


@pytest.mark.parametrize("name", ["../escape", "Issue-12", "a b", "", "x" * 60, "-lead", "issue;rm"])
def test_an_unsafe_worktree_name_is_refused(name):
    """The name becomes a directory and a branch, so it must not be able to climb out of either."""
    with pytest.raises(runner.RunnerError):
        _spec(name=name).validate()
    with pytest.raises(runner.RunnerError):
        runner.create_worktree(name)


def test_an_unknown_kind_is_refused():
    with pytest.raises(runner.RunnerError):
        _spec(kind="deploy").validate()


def test_an_empty_or_oversized_prompt_is_refused():
    with pytest.raises(runner.RunnerError):
        _spec(prompt="   ").validate()
    with pytest.raises(runner.RunnerError):
        _spec(prompt="x" * (runner.MAX_PROMPT_CHARS + 1)).validate()


def test_the_runner_never_grants_a_shell_tool():
    """A headless run that can shell out can also push, merge, or delete a branch."""
    assert "Bash" not in runner.ALLOWED_TOOLS
    argv = runner.build_argv(_spec())
    tools = argv[argv.index("--allowedTools") + 1].split(",")
    assert "Bash" not in tools and set(tools) == set(runner.ALLOWED_TOOLS)


def test_the_budget_flag_is_always_present_and_within_the_ceiling():
    argv = runner.build_argv(_spec(budget_usd=0.4))
    assert float(argv[argv.index("--max-budget-usd") + 1]) <= runner.MAX_BUDGET_USD


def test_a_goal_is_appended_to_the_prompt():
    argv = runner.build_argv(_spec(goal="pytest exits 0"))
    assert "/goal pytest exits 0" in argv[argv.index("-p") + 1]


def test_plan_mode_selects_the_plan_permission_mode():
    assert "plan" in runner.build_argv(_spec(plan_mode=True))
    assert "acceptEdits" in runner.build_argv(_spec(plan_mode=False))


def test_malformed_run_output_still_yields_a_record_rather_than_raising():
    """Losing the run's record because the CLI's output shape changed would hide a run that spent
    real money."""
    assert runner._parse_output("not json")["result"] == "not json"
    assert runner._parse_output('{"result": "ok", "total_cost_usd": 0.12}')["total_cost_usd"] == 0.12
    assert runner._parse_output("[]") == {}


def test_usage_summary_totals_cost_by_kind():
    from datetime import datetime

    from app.models import AgentRun

    class _Session:
        def query(self, _model):
            return self

        def all(self):
            return [
                AgentRun(kind="plan", cost_usd=0.10, budget_usd=0.25, status="ok", started_at=datetime.now()),
                AgentRun(kind="plan", cost_usd=0.05, budget_usd=0.25, status="ok", started_at=datetime.now()),
                AgentRun(kind="implement", cost_usd=None, budget_usd=0.25, status="error", started_at=datetime.now()),
            ]

    summary = runner.usage_summary(_Session())
    assert summary["runs"] == 3
    assert summary["total_cost_usd"] == pytest.approx(0.15)
    assert summary["by_kind"]["plan"] == {"runs": 2, "cost_usd": 0.15}
    assert summary["max_budget_usd"] == runner.MAX_BUDGET_USD
