"""Tests for orchestrator.verifier."""
from pathlib import Path

import pytest

from orchestrator.tasks import Task
from orchestrator.verifier import (
    ImmutableViolation,
    VerifyResult,
    check_immutable_files,
    run_difftest,
    run_verification_steps,
    snapshot_immutable_files,
    verify_task,
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


def test_verify_task_runs_pre_steps_then_verify(tmp_path: Path):
    """A task with a 'pre' step (e.g., make clean) should run it before verify."""
    task = Task(
        id="X", title="x", stage="X",
        verification={
            "type": "multi_step",
            "pre_steps": [{"cmd": f"echo PRE > {tmp_path}/marker.txt"}],
            "steps": [{"cmd": f"cat {tmp_path}/marker.txt",
                       "expect_exit": 0, "expect_grep": ["PRE"]}],
        },
    )
    result = verify_task(task, cwd=tmp_path)
    assert result.passed


def test_verify_task_returns_immutable_violation(tmp_path: Path):
    """If immutable files were modified during worker run, fail before steps."""
    locked = tmp_path / "test_runner" / "F1.sh"
    locked.parent.mkdir(parents=True)
    locked.write_text("baseline\n")

    task = Task(
        id="F1", title="x", stage="F",
        immutable_files=[str(locked)],
        verification={"type": "multi_step", "steps": [{"cmd": "true"}]},
    )

    baseline = snapshot_immutable_files([locked])
    # Worker "modified" the locked file
    locked.write_text("MODIFIED\n")

    result = verify_task(task, cwd=tmp_path, immutable_baseline=baseline)
    assert not result.passed
    assert result.fail_category == "immutable_modified"


def test_run_difftest_calls_script_and_parses_output(tmp_path: Path):
    """difftest script must return exit 0 + emit 'DIFFTEST: passed'."""
    fake_script = tmp_path / "df.sh"
    fake_script.write_text("#!/bin/bash\necho DIFFTEST: passed\nexit 0\n")
    fake_script.chmod(0o755)
    result = run_difftest(script_path=fake_script, cwd=tmp_path)
    assert result.passed


def test_run_difftest_fails_when_diff_marker_missing(tmp_path: Path):
    fake_script = tmp_path / "df.sh"
    fake_script.write_text("#!/bin/bash\necho silent success\nexit 0\n")
    fake_script.chmod(0o755)
    result = run_difftest(script_path=fake_script, cwd=tmp_path)
    assert not result.passed
    assert result.fail_category == "grep_miss"


def test_run_difftest_fails_on_nonzero_exit(tmp_path: Path):
    fake_script = tmp_path / "df.sh"
    fake_script.write_text("#!/bin/bash\necho DIFFTEST: passed\nexit 1\n")
    fake_script.chmod(0o755)
    result = run_difftest(script_path=fake_script, cwd=tmp_path)
    assert not result.passed
    assert result.fail_category == "exit_mismatch"
