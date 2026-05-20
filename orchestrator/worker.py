"""Spawn the `claude` CLI as a worker subagent and parse its output."""
from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contract import ContractError, extract_contract


class WorkerTimeout(Exception):
    """Raised when the claude CLI subprocess exceeds its timeout."""


@dataclass
class WorkerResult:
    exit_code: int
    raw_stdout: str
    raw_stderr: str
    api_error: str | None
    session_id: str | None
    cost_usd: float
    duration_ms: int
    contract: dict[str, Any] | None
    contract_error: str | None


def _spawn_claude(
    args: list[str],
    input_text: str,
    cwd: Path,
    timeout_sec: int,
) -> tuple[int, str, str]:
    """Run claude CLI; return (exit_code, stdout, stderr). Raises WorkerTimeout."""
    try:
        proc = subprocess.run(
            args,
            input=input_text,
            capture_output=True,
            text=True,
            cwd=str(cwd),
            timeout=timeout_sec,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise WorkerTimeout(f"claude CLI timed out after {timeout_sec}s") from e
    return proc.returncode, proc.stdout, proc.stderr


def run_worker(
    prompt: str,
    work_dir: Path,
    model: str = "opus",
    max_budget_usd: float = 5.0,
    allowed_tools: str = "Bash Edit Read Write Glob Grep",
    add_dirs: list[Path] | None = None,
    system_prompt_file: Path | None = None,
    timeout_sec: int = 3600,
) -> WorkerResult:
    """Spawn `claude --print --output-format json` and parse its result."""
    args = [
        "claude",
        "--print",
        "--output-format", "json",
        "--model", model,
        "--max-budget-usd", str(max_budget_usd),
        "--allowedTools", allowed_tools,
    ]
    for d in add_dirs or []:
        args += ["--add-dir", str(d)]
    if system_prompt_file is not None:
        args += ["--append-system-prompt", system_prompt_file.read_text()]
    args += ["-p", prompt]

    exit_code, stdout, stderr = _spawn_claude(args, "", work_dir, timeout_sec)

    # claude CLI JSON wrapper
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError:
        return WorkerResult(
            exit_code=exit_code,
            raw_stdout=stdout,
            raw_stderr=stderr,
            api_error=f"claude returned non-JSON envelope (exit={exit_code})",
            session_id=None,
            cost_usd=0.0,
            duration_ms=0,
            contract=None,
            contract_error=None,
        )

    api_error: str | None = None
    if envelope.get("is_error"):
        api_error = envelope.get("result", "unknown claude API error")

    contract: dict[str, Any] | None = None
    contract_error: str | None = None
    result_text = envelope.get("result", "")
    if not api_error:
        try:
            contract = extract_contract(result_text)
        except ContractError as e:
            contract_error = str(e)

    return WorkerResult(
        exit_code=exit_code,
        raw_stdout=stdout,
        raw_stderr=stderr,
        api_error=api_error,
        session_id=envelope.get("session_id"),
        cost_usd=float(envelope.get("total_cost_usd", 0.0)),
        duration_ms=int(envelope.get("duration_ms", 0)),
        contract=contract,
        contract_error=contract_error,
    )


def shell_command_preview(args: list[str]) -> str:
    """Return a copy-pasteable shell command preview for logging."""
    return " ".join(shlex.quote(a) for a in args)
