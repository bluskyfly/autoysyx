"""Spawn the `claude` CLI as a worker subagent and parse its output."""
from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contract import ContractError, extract_contract
from .tasks import Task


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
        args += ["--append-system-prompt-file", str(system_prompt_file)]
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
        cost_usd=float(envelope.get("total_cost_usd") or 0.0),
        duration_ms=int(envelope.get("duration_ms") or 0),
        contract=contract,
        contract_error=contract_error,
    )


def assemble_prompt(
    template_path: Path,
    task: Task,
    project_root: Path,
    prior_errors: list[str],
) -> str:
    """Render a worker prompt by substituting `{{ var }}` slots in a template.

    Variables:
      task_id, title, stage     -- from the Task dataclass.
      docs_content              -- inlined content of every existing doc_refs file.
      immutable_files           -- comma-joined task.immutable_files.
      previous_error_excerpt    -- formatted block from prior_errors (empty if none).
      project_root, work_dir    -- absolute paths shown to the worker.
    """
    template = template_path.read_text(encoding="utf-8")
    docs_content = []
    for ref in task.doc_refs:
        ref_path = (project_root / ref).resolve() if not Path(ref).is_absolute() else Path(ref)
        if ref_path.exists():
            docs_content.append(f"\n### {ref}\n\n{ref_path.read_text(encoding='utf-8')}")

    error_block = ""
    if prior_errors:
        error_block = "\n\n--- 历史错误日志 ---\n" + "\n---\n".join(prior_errors)

    substitutions = {
        "task_id": task.id,
        "title": task.title,
        "stage": task.stage,
        "docs_content": "\n".join(docs_content) or "(no documentation references)",
        "immutable_files": ", ".join(task.immutable_files) or "(none)",
        "previous_error_excerpt": error_block,
        "project_root": str(project_root),
        "work_dir": str(project_root / "ysyx-workbench"),
    }
    out = template
    for key, val in substitutions.items():
        out = out.replace("{{ " + key + " }}", str(val))
    return out


def shell_command_preview(args: list[str]) -> str:
    """Return a copy-pasteable shell command preview for logging."""
    return " ".join(shlex.quote(a) for a in args)
