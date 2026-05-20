"""End-to-end orchestrator dry run with mocked worker + codex."""
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from orchestrator.main import cli
from orchestrator.contract import CONTRACT_BEGIN, CONTRACT_END


def _fake_worker_envelope(task_id: str) -> str:
    contract = {
        "task_id": task_id,
        "files_changed": [],
        "key_decisions": [],
        "run_commands": ["true"],
        "artifacts": [],
        "known_risks": [],
        "open_issues": [],
        "self_test_passed": True,
        "self_test_output_tail": "ok",
    }
    body = f"{CONTRACT_BEGIN}\n{json.dumps(contract)}\n{CONTRACT_END}"
    return json.dumps({
        "type": "result", "is_error": False, "result": body,
        "session_id": "s", "total_cost_usd": 0.01, "duration_ms": 100,
    })


def test_full_dry_run_completes_two_tasks(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "tasks.yaml").write_text("""tasks:
  - id: A
    title: first
    stage: phase0
    deps: []
    verification:
      type: multi_step
      steps:
        - { cmd: "true", expect_exit: 0 }
  - id: B
    title: second
    stage: phase0
    deps: [A]
    verification:
      type: multi_step
      steps:
        - { cmd: "true", expect_exit: 0 }
""")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "_template.md").write_text(
        "Task: {{ task_id }} {{ title }} {{ docs_content }}"
    )
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)

    def fake_spawn(args, *_a, **_kw):
        task_id = "A" if "A" in " ".join(args) else "B"
        return (0, _fake_worker_envelope(task_id), "")

    with patch("orchestrator.worker._spawn_claude", side_effect=fake_spawn), \
         patch("orchestrator.reviewer._run_codex") as rc:
        rc.return_value = (0, "Looks good. No issues.", "")
        result = CliRunner().invoke(cli, ["run", "--max-tasks", "2"])

    assert result.exit_code == 0, result.output

    from orchestrator.db import Database
    db = Database(tmp_path / "orchestrator" / "state.db")
    assert db.task_status("A") == "completed"
    assert db.task_status("B") == "completed"

    assert (tmp_path / "reports" / "A.md").exists()
    assert (tmp_path / "reports" / "B.md").exists()


def test_dry_run_halts_after_max_attempts(tmp_path, monkeypatch):
    """When worker always returns invalid contract, expect task_failed after 3 attempts."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "tasks.yaml").write_text("""tasks:
  - id: A
    title: first
    stage: phase0
    deps: []
    verification:
      type: multi_step
      steps:
        - { cmd: "true", expect_exit: 0 }
""")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "_template.md").write_text("{{ task_id }}")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)

    bad_envelope = json.dumps({
        "type": "result", "is_error": False,
        "result": "no contract here",  # missing markers -> invalid contract
        "session_id": "s", "total_cost_usd": 0.01, "duration_ms": 1,
    })

    with patch("orchestrator.worker._spawn_claude") as spawn, \
         patch("orchestrator.reviewer._run_codex"):
        spawn.return_value = (0, bad_envelope, "")
        result = CliRunner().invoke(cli, ["run", "--max-tasks", "5"])

    assert result.exit_code == 1
    from orchestrator.db import Database
    db = Database(tmp_path / "orchestrator" / "state.db")
    assert db.task_status("A") == "failed"
    assert (tmp_path / "reports" / "A-FAILED.md").exists()
