"""Tests for orchestrator.worker."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from orchestrator.worker import WorkerResult, WorkerTimeout, run_worker


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
