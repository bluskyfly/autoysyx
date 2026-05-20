"""Tests for orchestrator.worker."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from orchestrator.tasks import Task
from orchestrator.worker import (
    WorkerResult,
    WorkerTimeout,
    assemble_prompt,
    run_worker,
)


def test_run_worker_returns_parsed_contract_on_success(tmp_path: Path):
    fake_stdout = json.dumps({
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": (
            "====TASK_CONTRACT_BEGIN====\n"
            '{"task_id":"F1","files_changed":[],"key_decisions":[],'
            '"run_commands":["ls"],"artifacts":[],"known_risks":[],'
            '"open_issues":[],"self_test_passed":true,'
            '"self_test_output_tail":"ok"}\n'
            "====TASK_CONTRACT_END===="
        ),
        "session_id": "abc-123",
        "total_cost_usd": 0.05,
        "duration_ms": 1234,
    })

    with patch("orchestrator.worker._spawn_claude") as spawn:
        spawn.return_value = (0, fake_stdout, "")
        result = run_worker(prompt="test prompt", work_dir=tmp_path)

    assert isinstance(result, WorkerResult)
    assert result.contract["task_id"] == "F1"
    assert result.session_id == "abc-123"
    assert result.cost_usd == 0.05
    assert result.exit_code == 0


def test_run_worker_treats_missing_contract_as_failure(tmp_path: Path):
    fake_stdout = json.dumps({
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": "I forgot to emit a contract!",
        "session_id": "x",
        "total_cost_usd": 0.01,
        "duration_ms": 1,
    })
    with patch("orchestrator.worker._spawn_claude") as spawn:
        spawn.return_value = (0, fake_stdout, "")
        result = run_worker(prompt="x", work_dir=tmp_path)
    assert result.contract is None
    assert result.contract_error is not None
    assert "markers not found" in result.contract_error


def test_run_worker_propagates_claude_api_error(tmp_path: Path):
    fake_stdout = json.dumps({
        "type": "result",
        "is_error": True,
        "result": "Rate limit exceeded",
        "session_id": "",
        "total_cost_usd": 0,
        "duration_ms": 5,
    })
    with patch("orchestrator.worker._spawn_claude") as spawn:
        spawn.return_value = (0, fake_stdout, "")
        result = run_worker(prompt="x", work_dir=tmp_path)
    assert result.api_error == "Rate limit exceeded"
    assert result.contract is None


def test_run_worker_kills_on_timeout(tmp_path: Path):
    with patch("orchestrator.worker._spawn_claude", side_effect=WorkerTimeout("timed out at 1s")):
        with pytest.raises(WorkerTimeout):
            run_worker(prompt="x", work_dir=tmp_path, timeout_sec=1)


def test_run_worker_handles_null_cost_in_envelope(tmp_path: Path):
    """Envelope with null total_cost_usd/duration_ms must not crash run_worker."""
    fake_stdout = json.dumps({
        "type": "result",
        "is_error": False,
        "result": "no contract markers here",
        "session_id": "x",
        "total_cost_usd": None,
        "duration_ms": None,
    })
    with patch("orchestrator.worker._spawn_claude") as spawn:
        spawn.return_value = (0, fake_stdout, "")
        result = run_worker(prompt="x", work_dir=tmp_path)
    assert result.cost_usd == 0.0
    assert result.duration_ms == 0


def test_assemble_prompt_substitutes_basic_vars(tmp_path):
    template = "Task: {{ task_id }} - {{ title }}\nDocs:\n{{ docs_content }}\n"
    tmpl_file = tmp_path / "tpl.md"
    tmpl_file.write_text(template)

    doc1 = tmp_path / "doc1.md"
    doc1.write_text("# Doc One\nbody\n")

    task = Task(id="F1", title="x", stage="F", doc_refs=[str(doc1)])
    out = assemble_prompt(template_path=tmpl_file, task=task,
                          project_root=tmp_path, prior_errors=[])
    assert "Task: F1 - x" in out
    assert "# Doc One" in out


def test_assemble_prompt_includes_prior_errors(tmp_path):
    tmpl_file = tmp_path / "tpl.md"
    tmpl_file.write_text("{{ task_id }}\n{{ previous_error_excerpt }}")

    task = Task(id="F1", title="x", stage="F")
    out = assemble_prompt(template_path=tmpl_file, task=task,
                          project_root=tmp_path,
                          prior_errors=["compile failed: undefined symbol foo"])
    assert "undefined symbol foo" in out


def test_assemble_prompt_handles_empty_doc_refs(tmp_path):
    tmpl_file = tmp_path / "tpl.md"
    tmpl_file.write_text("{{ task_id }}\n{{ docs_content }}")
    task = Task(id="F1", title="x", stage="F", doc_refs=[])
    out = assemble_prompt(template_path=tmpl_file, task=task,
                          project_root=tmp_path, prior_errors=[])
    assert "F1" in out
