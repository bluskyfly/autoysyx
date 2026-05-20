"""Tests for the 3-tier escalation flow: needs_debug + bundle + inject-hint."""
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from orchestrator.db import Database
from orchestrator.main import cli


def _write_minimal_project(tmp_path: Path, task_id: str = "D1") -> None:
    """Lay out a single-task project with a trivially-failing verifier.

    The verifier exits non-zero so every worker attempt fails verification
    until max_attempts is exhausted — which is what we want to test.
    """
    (tmp_path / "tasks.yaml").write_text(f"""tasks:
  - id: {task_id}
    title: a debug-heavy task
    stage: phaseD
    deps: []
    max_attempts: 2
    verification:
      type: multi_step
      steps:
        - {{ cmd: "false", expect_exit: 0 }}
""")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "_template.md").write_text(
        "# {{ task_id }} {{ title }}\nhint:{{ escalation_hint }}\n"
    )
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)


def _fake_worker_envelope_passing_contract(task_id: str) -> str:
    """Worker returns a valid contract; verifier still rejects it (we want
    attempt_failed-from-verifier, not contract_invalid)."""
    from orchestrator.contract import CONTRACT_BEGIN, CONTRACT_END
    body = (
        f"{CONTRACT_BEGIN}\n"
        f'{{"task_id":"{task_id}","files_changed":[],"key_decisions":[],'
        f'"run_commands":["false"],"artifacts":[],"known_risks":[],'
        f'"open_issues":[],"self_test_passed":true,'
        f'"self_test_output_tail":"ok"}}'
        f"\n{CONTRACT_END}"
    )
    return json.dumps({
        "type": "result", "is_error": False, "result": body,
        "session_id": "s", "total_cost_usd": 0.01, "duration_ms": 1,
    })


def test_exhausted_attempts_park_task_in_needs_debug_not_failed(tmp_path, monkeypatch):
    """After max_attempts the task enters `needs_debug`, NOT `failed`.

    The orchestrator must also write an escalation bundle and stop scheduling
    work that depends on this task (deps are not satisfied by `needs_debug`).
    """
    monkeypatch.chdir(tmp_path)
    _write_minimal_project(tmp_path)

    with patch("orchestrator.worker._spawn_claude") as ws, \
         patch("orchestrator.reviewer._run_codex") as rc:
        ws.return_value = (0, _fake_worker_envelope_passing_contract("D1"), "")
        rc.return_value = (0, "Looks good. No issues.", "")
        result = CliRunner().invoke(cli, ["run", "--max-tasks", "1"])

    assert result.exit_code == 0, result.output
    assert "NEEDS DEBUG" in result.output
    assert "bundle" in result.output

    db = Database(tmp_path / "orchestrator" / "state.db")
    assert db.task_status("D1") == "needs_debug"

    # Bundle must be on disk with the required artifacts.
    bundles = list((tmp_path / "escalations").glob("D1-*"))
    assert len(bundles) == 1, f"expected one bundle dir, got {bundles}"
    bundle = bundles[0]
    assert (bundle / "attempts.log").exists()
    assert (bundle / "staged.patch").exists()
    assert (bundle / "git-status.txt").exists()
    meta = json.loads((bundle / "meta.json").read_text())
    assert meta["task_id"] == "D1"
    assert meta["attempts_used"] == 2
    assert meta["max_attempts"] == 2


def test_needs_debug_blocks_dependents(tmp_path, monkeypatch):
    """A task in `needs_debug` must block downstream tasks (deps unsatisfied)."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "tasks.yaml").write_text("""tasks:
  - id: A
    title: parent
    stage: x
    deps: []
    max_attempts: 1
    verification:
      type: multi_step
      steps:
        - { cmd: "false", expect_exit: 0 }
  - id: B
    title: child
    stage: x
    deps: [A]
    max_attempts: 1
    verification:
      type: multi_step
      steps:
        - { cmd: "true", expect_exit: 0 }
""")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "_template.md").write_text("{{ task_id }}{{ escalation_hint }}")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)

    with patch("orchestrator.worker._spawn_claude") as ws, \
         patch("orchestrator.reviewer._run_codex") as rc:
        ws.return_value = (0, _fake_worker_envelope_passing_contract("A"), "")
        rc.return_value = (0, "Looks good. No issues.", "")
        result = CliRunner().invoke(cli, ["run"])

    assert result.exit_code == 0, result.output
    db = Database(tmp_path / "orchestrator" / "state.db")
    assert db.task_status("A") == "needs_debug"
    # B's status stays pending because A's `needs_debug` is not in {completed, skipped}.
    assert db.task_status("B") == "pending"
    # And the run must have stopped with no work to do (B can't run).
    assert "all done or blocked" in result.output


def test_inject_hint_copies_file_and_resets_task(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "tasks.yaml").write_text(
        "tasks:\n  - id: D1\n    title: x\n    stage: x\n    deps: []\n"
        "    verification:\n      type: doc_only\n"
    )

    # Mark D1 as needs_debug first (simulating prior escalation).
    db = Database(tmp_path / "orchestrator" / "state.db")
    (tmp_path / "orchestrator").mkdir(exist_ok=True)
    db.init_schema()
    db.append_event(type="task_needs_debug", task_id="D1",
                    payload={"attempts": 3})
    assert db.task_status("D1") == "needs_debug"

    hint_src = tmp_path / "external-hint.md"
    hint_src.write_text("Look at ALU.scala line 42: carry bit reversed.")

    result = CliRunner().invoke(cli, ["inject-hint", "D1", str(hint_src)])
    assert result.exit_code == 0, result.output

    # Hint file landed in the canonical location.
    placed = tmp_path / "prompts" / "_hints" / "D1.md"
    assert placed.exists()
    assert "ALU.scala line 42" in placed.read_text()

    # And the task is reset to pending so it can be picked up again.
    assert db.task_status("D1") == "pending"


def test_assemble_prompt_inlines_hint_when_present(tmp_path):
    """The worker template's {{ escalation_hint }} must be filled when a hint exists."""
    from orchestrator.tasks import Task
    from orchestrator.worker import assemble_prompt

    (tmp_path / "prompts").mkdir()
    template = tmp_path / "prompts" / "_template.md"
    template.write_text(
        "Task {{ task_id }}\nERR:{{ previous_error_excerpt }}\nHINT:{{ escalation_hint }}\n"
    )
    (tmp_path / "prompts" / "_hints").mkdir()
    (tmp_path / "prompts" / "_hints" / "D1.md").write_text(
        "Check ALU carry-out at PC=0x80000100"
    )

    task = Task(
        id="D1", title="x", stage="x", deps=[],
        verification={"type": "doc_only"}, doc_refs=[],
        immutable_files=[], max_attempts=3, estimated_minutes=0,
    )
    prompt = assemble_prompt(template, task, tmp_path, prior_errors=[])

    assert "HINT:" in prompt
    assert "Check ALU carry-out at PC=0x80000100" in prompt
    assert "协作 debug 提示" in prompt


def test_assemble_prompt_leaves_hint_block_empty_when_absent(tmp_path):
    """Without a hint file the escalation_hint block must collapse to empty."""
    from orchestrator.tasks import Task
    from orchestrator.worker import assemble_prompt

    (tmp_path / "prompts").mkdir()
    template = tmp_path / "prompts" / "_template.md"
    template.write_text("Task {{ task_id }}\nHINT:{{ escalation_hint }}\n")

    task = Task(
        id="D1", title="x", stage="x", deps=[],
        verification={"type": "doc_only"}, doc_refs=[],
        immutable_files=[], max_attempts=3, estimated_minutes=0,
    )
    prompt = assemble_prompt(template, task, tmp_path, prior_errors=[])
    assert "HINT:\n" in prompt  # empty substitution, no debug instructions
    assert "协作 debug" not in prompt
