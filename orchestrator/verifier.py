"""Run verification steps for a task and classify failures."""
from __future__ import annotations

import shlex
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class VerifyResult:
    passed: bool
    fail_category: str | None = None
    log_path: str | None = None
    grep_misses: list[str] = field(default_factory=list)
    failing_step: dict | None = None
    duration_sec: float = 0.0


def _run_step(
    step: dict[str, Any],
    cwd: Path,
    log_file: Path,
) -> tuple[int, str, bool]:
    """Run one step. Return (exit_code, combined_output, timed_out)."""
    cmd = step["cmd"]
    timeout = int(step.get("timeout_sec", 1800))
    with log_file.open("a", encoding="utf-8") as fh:
        fh.write(f"\n$ {cmd}\n")
        fh.flush()
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            fh.write(f"\n[TIMEOUT after {timeout}s]\n")
            output = (e.stdout or "") + (e.stderr or "")
            fh.write(output)
            return 124, output, True
        out = proc.stdout + proc.stderr
        fh.write(out)
        return proc.returncode, out, False


def run_verification_steps(
    steps: list[dict[str, Any]],
    cwd: Path,
    log_path: Path | None = None,
) -> VerifyResult:
    """Execute each step in order; bail on first failure."""
    start = time.monotonic()
    if log_path is None:
        log_path = Path(tempfile.mktemp(suffix=".verify.log"))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(f"# verifier log @ {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

    for step in steps:
        rc, out, timed_out = _run_step(step, cwd, log_path)
        if timed_out:
            return VerifyResult(
                passed=False,
                fail_category="timeout",
                log_path=str(log_path),
                failing_step=step,
                duration_sec=time.monotonic() - start,
            )
        expect_exit = int(step.get("expect_exit", 0))
        if rc != expect_exit:
            return VerifyResult(
                passed=False,
                fail_category="exit_mismatch",
                log_path=str(log_path),
                failing_step={**step, "actual_exit": rc},
                duration_sec=time.monotonic() - start,
            )
        misses = [g for g in step.get("expect_grep", []) if g not in out]
        if misses:
            return VerifyResult(
                passed=False,
                fail_category="grep_miss",
                grep_misses=misses,
                log_path=str(log_path),
                failing_step=step,
                duration_sec=time.monotonic() - start,
            )

    return VerifyResult(
        passed=True,
        log_path=str(log_path),
        duration_sec=time.monotonic() - start,
    )
