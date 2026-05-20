"""Tests for orchestrator.main CLI."""
from click.testing import CliRunner

from orchestrator.main import cli


def test_cli_help_lists_commands():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    for cmd in ("run", "status", "resume", "skip", "retry", "bootstrap"):
        assert cmd in result.output


def test_status_command_works_on_fresh_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Need a minimal tasks.yaml fixture
    (tmp_path / "tasks.yaml").write_text(
        "tasks:\n"
        "  - id: PHASE0\n    title: Bootstrap\n    stage: phase0\n    deps: []\n    verification:\n      type: doc_only\n"
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["status"])
    assert result.exit_code == 0
    assert "PHASE0" in result.output
    assert "pending" in result.output


def test_skip_command_marks_task_skipped(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "tasks.yaml").write_text(
        "tasks:\n"
        "  - id: F1\n    title: x\n    stage: F\n    deps: []\n    verification:\n      type: doc_only\n"
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["skip", "F1"])
    assert result.exit_code == 0

    result2 = runner.invoke(cli, ["status"])
    assert "skipped" in result2.output
