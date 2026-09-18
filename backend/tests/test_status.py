"""`app.cli status` must report what is on disk, not what a manifest hopes is there.

These tests exist because Phase 2a was twice described as complete while `export_xlsx.py` had
never been written — a missing file must show up as missing, and a file that exists but lacks the
deliverable inside it must not count as present.
"""

import json

import pytest
import yaml

from app.cli import cmd_status


@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    """A repo root with a two-check manifest: one deliverable present, one missing."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "present.py").write_text("def build_export():\n    ...\n")
    manifest = {
        "phases": [
            {
                "id": "x",
                "name": "Test phase",
                "checks": [{"path": "present.py"}, {"path": "absent.py"}],
                "manual": ["something only a human can confirm"],
            }
        ]
    }
    (tmp_path / "docs" / "phases.yaml").write_text(yaml.safe_dump(manifest))
    monkeypatch.setattr("app.cli.PROJECT_ROOT", tmp_path)
    return tmp_path


def test_reports_missing_file(fake_repo, capsys):
    assert cmd_status(as_json=True) == 0
    phase = json.loads(capsys.readouterr().out)["phases"][0]
    assert phase["present"] == 1
    assert phase["total"] == 2
    assert phase["missing"] == ["absent.py"]


def test_existing_file_without_the_deliverable_counts_as_missing(fake_repo, capsys):
    """The `contains` check is the guard against a module that exists but is a stub."""
    manifest = yaml.safe_load((fake_repo / "docs" / "phases.yaml").read_text())
    manifest["phases"][0]["checks"] = [{"path": "present.py", "contains": "def export_xlsx"}]
    (fake_repo / "docs" / "phases.yaml").write_text(yaml.safe_dump(manifest))

    cmd_status(as_json=True)
    phase = json.loads(capsys.readouterr().out)["phases"][0]
    assert phase["present"] == 0
    assert phase["missing"] == ["present.py (no 'def export_xlsx')"]


def test_manual_items_are_never_counted_as_delivered(fake_repo, capsys):
    cmd_status(as_json=True)
    phase = json.loads(capsys.readouterr().out)["phases"][0]
    assert phase["total"] == 2, "manual notes must not inflate the delivered count"
    assert phase["manual"] == ["something only a human can confirm"]


def test_missing_manifest_is_an_error_not_a_clean_report(tmp_path, monkeypatch, capsys):
    """Absent manifest must fail loudly — silently reporting 'nothing missing' is the exact
    failure mode this command was added to prevent."""
    monkeypatch.setattr("app.cli.PROJECT_ROOT", tmp_path)
    assert cmd_status(as_json=True) == 1
    assert "cannot report status" in capsys.readouterr().err


def test_real_manifest_parses_and_every_check_is_well_formed():
    from app.cli import PROJECT_ROOT

    phases = yaml.safe_load((PROJECT_ROOT / "docs" / "phases.yaml").read_text())["phases"]
    assert phases, "docs/phases.yaml must declare at least one phase"
    for phase in phases:
        assert phase.get("checks"), f"phase {phase['id']} declares no checks"
        for check in phase["checks"]:
            assert "path" in check, f"phase {phase['id']} has a check with no path"
            assert not check["path"].startswith("/"), "paths are repo-relative"
