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


def test_dry_run_marks_failure_and_continues_to_exit_clean(tmp_path, monkeypatch):
    """After max_attempts, task_failed is recorded but the run exits 0 (not hard-exit 1).

    Bug B fix: an exhausted task no longer terminates the orchestrator with sys.exit(1).
    Outer loop calls pick_next_task again; with no other ready task, it returns None
    and exits cleanly via 'all done or blocked'. The operator can `retry` and `resume`.
    """
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

    assert result.exit_code == 0, result.output
    assert "FAILED" in result.output
    assert "all done or blocked" in result.output
    from orchestrator.db import Database
    db = Database(tmp_path / "orchestrator" / "state.db")
    assert db.task_status("A") == "failed"
    assert (tmp_path / "reports" / "A-FAILED.md").exists()


def test_codex_sees_staged_diff_not_empty(tmp_path, monkeypatch):
    """Bug A fix: `git add -A` must run BEFORE the codex review, so codex sees real changes.

    Before the fix, `git diff --cached HEAD` ran before any `git add`, so codex always
    received an empty diff and its reject heuristic was effectively a no-op.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "tasks.yaml").write_text("""tasks:
  - id: T
    title: produce-a-file
    stage: phase0
    deps: []
    verification:
      type: multi_step
      steps:
        - { cmd: "echo 'sentinel-codex-diff' > new_artifact.txt", expect_exit: 0 }
""")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "_template.md").write_text("{{ task_id }} {{ title }}")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    # Initial empty commit so `git diff HEAD` has a reference.
    subprocess.run(
        ["git", "commit", "--allow-empty", "-q", "-m", "init"],
        cwd=tmp_path, check=True,
    )

    captured_questions: list[str] = []

    def capture_codex(question: str, *_a, **_kw):
        captured_questions.append(question)
        return (0, "Looks good. No issues.", "")

    with patch("orchestrator.worker._spawn_claude") as spawn, \
         patch("orchestrator.reviewer._run_codex", side_effect=capture_codex):
        spawn.return_value = (0, _fake_worker_envelope("T"), "")
        result = CliRunner().invoke(cli, ["run", "--max-tasks", "1"])

    assert result.exit_code == 0, result.output
    assert len(captured_questions) == 1
    # Bug A regression: real diff with the worker's sentinel must reach codex.
    # Bug D fix: diff is inlined in the prompt itself (codex sandbox can't read disk).
    q = captured_questions[0]
    assert "new_artifact.txt" in q
    assert "sentinel-codex-diff" in q
    assert not (tmp_path / ".autoysyx").exists(), "reviewer must not spill diff to disk"
