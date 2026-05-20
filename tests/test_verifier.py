"""Tests for orchestrator.verifier."""
from pathlib import Path

import pytest

from orchestrator.verifier import (
    ImmutableViolation,
    VerifyResult,
    check_immutable_files,
    run_verification_steps,
)


def _hash(p: Path) -> str:
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest()


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


def test_check_immutable_files_passes_when_unmodified(tmp_path: Path):
    test_file = tmp_path / "tests" / "guard.sh"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("#!/bin/bash\nexit 0\n")
    baseline = {str(test_file): _hash(test_file)}
    # No modification -> no violation
    violations = check_immutable_files(baseline)
    assert violations == []


def test_check_immutable_files_detects_modification(tmp_path: Path):
    test_file = tmp_path / "tests" / "guard.sh"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("original\n")
    baseline = {str(test_file): _hash(test_file)}
    test_file.write_text("evil tampering\n")
    violations = check_immutable_files(baseline)
    assert violations == [str(test_file)]


def test_check_immutable_files_treats_delete_as_violation(tmp_path: Path):
    f = tmp_path / "f.sh"
    f.write_text("x\n")
    baseline = {str(f): _hash(f)}
    f.unlink()
    assert check_immutable_files(baseline) == [str(f)]
