"""Tests for orchestrator.main CLI."""
import json
import subprocess
import sys
from unittest.mock import patch

from click.testing import CliRunner

from orchestrator.contract import CONTRACT_BEGIN, CONTRACT_END
from orchestrator.main import cli


def test_cli_help_lists_commands():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    for cmd in ("run", "status", "resume", "skip", "retry", "bootstrap"):
        assert cmd in result.output


def test_module_entrypoint_invokes_cli():
    """`python -m orchestrator.main --help` must print help (Makefile depends on this)."""
    result = subprocess.run(
        [sys.executable, "-m", "orchestrator.main", "--help"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, f"stderr={result.stderr}"
    assert "status" in result.stdout
    assert "run" in result.stdout


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


def test_run_loops_through_pending_tasks(tmp_path, monkeypatch):
    """A full mocked run should: pick task, spawn worker, verify, review, commit."""
    monkeypatch.chdir(tmp_path)
    # Minimal task that should pass a trivial echo verifier.
    (tmp_path / "tasks.yaml").write_text("""tasks:
  - id: ECHO
    title: trivial echo task
    stage: phase0
    deps: []
    verification:
      type: multi_step
      steps:
        - { cmd: "echo HELLO", expect_exit: 0, expect_grep: ["HELLO"] }
""")
    # The run command's assemble_prompt step needs a template file.
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "_template.md").write_text(
        "# {{ task_id }}: {{ title }}\n"
    )
    # Need a git repo so commits work
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)

    fake_envelope = json.dumps({
        "type": "result", "is_error": False,
        "result": f"{CONTRACT_BEGIN}\n"
                  '{"task_id":"ECHO","files_changed":[],"key_decisions":[],'
                  '"run_commands":[],"artifacts":[],"known_risks":[],'
                  '"open_issues":[],"self_test_passed":true,'
                  '"self_test_output_tail":"ok"}'
                  f"\n{CONTRACT_END}",
        "session_id": "s", "total_cost_usd": 0.01, "duration_ms": 100,
    })

    with patch("orchestrator.worker._spawn_claude") as ws, \
         patch("orchestrator.reviewer._run_codex") as rc:
        ws.return_value = (0, fake_envelope, "")
        rc.return_value = (0, "Looks good. No issues.", "")

        runner = CliRunner()
        result = runner.invoke(cli, ["run"])

    assert result.exit_code == 0, result.output

    # Check that ECHO is now completed
    from orchestrator.db import Database
    db = Database(tmp_path / "orchestrator" / "state.db")
    assert db.task_status("ECHO") == "completed"
