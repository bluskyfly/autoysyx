"""Tests for orchestrator.verifier."""
from pathlib import Path

import pytest

from orchestrator.verifier import VerifyResult, run_verification_steps


def test_passes_when_all_steps_succeed(tmp_path: Path):
    steps = [
        {"cmd": "echo HELLO; exit 0", "expect_exit": 0, "expect_grep": ["HELLO"]},
        {"cmd": "true", "expect_exit": 0},
    ]
    result = run_verification_steps(steps, cwd=tmp_path)
    assert result.passed
    assert result.fail_category is None


def test_fails_on_non_zero_exit(tmp_path: Path):
    steps = [{"cmd": "false", "expect_exit": 0}]
    result = run_verification_steps(steps, cwd=tmp_path)
    assert not result.passed
    assert result.fail_category == "exit_mismatch"


def test_fails_when_expected_grep_missing(tmp_path: Path):
    steps = [{"cmd": "echo WRONG", "expect_exit": 0, "expect_grep": ["RIGHT"]}]
    result = run_verification_steps(steps, cwd=tmp_path)
    assert not result.passed
    assert result.fail_category == "grep_miss"
    assert "RIGHT" in result.grep_misses


def test_timeout_kills_step(tmp_path: Path):
    steps = [{"cmd": "sleep 10", "expect_exit": 0, "timeout_sec": 1}]
    result = run_verification_steps(steps, cwd=tmp_path)
    assert not result.passed
    assert result.fail_category == "timeout"


def test_log_path_records_full_output(tmp_path: Path):
    steps = [{"cmd": "echo line1; echo line2 >&2; exit 0", "expect_exit": 0}]
    result = run_verification_steps(steps, cwd=tmp_path)
    assert result.passed
    assert result.log_path is not None
    text = Path(result.log_path).read_text()
    assert "line1" in text and "line2" in text
