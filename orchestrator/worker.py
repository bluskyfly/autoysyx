"""Spawn the `claude` CLI as a worker subagent and parse its output."""
from __future__ import annotations

import json
import os
import re
import resource
import shlex
import subprocess
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contract import ContractError, extract_contract
from .tasks import Task

# Force true serial recursion. -j 4 still yielded 4^N processes for N-level
# recursive $(MAKE) (PA2 cputest fork-bombed the box to ~330k procs and the
# cgroup pids controller started rejecting forks across the whole user slice,
# crashing GNOME). -j 1 keeps every nested make in lockstep.
_WORKER_MAKEFLAGS = "-j 1"
# Belt-and-suspenders: hard RLIMIT_NPROC for the worker subtree so a runaway
# Makefile gets EAGAIN from fork() instead of taking the user slice down.
# Baseline user procs ~22; 4000 gives huge headroom for legitimate parallel
# tool use while still firing well below the cgroup ceiling.
_WORKER_RLIMIT_NPROC = 4000


def _apply_worker_rlimits() -> None:
    """Set RLIMIT_NPROC on the child after fork(), before exec()."""
    soft, hard = resource.getrlimit(resource.RLIMIT_NPROC)
    target = _WORKER_RLIMIT_NPROC
    new_hard = min(hard, target) if hard != resource.RLIM_INFINITY else target
    resource.setrlimit(resource.RLIMIT_NPROC, (target, new_hard))


class WorkerTimeout(Exception):
    """Raised when the claude CLI subprocess exceeds its timeout."""


class SessionLimitError(Exception):
    """Raised when claude session quota is exhausted. Carries the UTC datetime
    at which the orchestrator should retry the same attempt."""

    def __init__(self, message: str, retry_at: datetime):
        super().__init__(message)
        self.retry_at = retry_at


# Matches e.g.  "session limit · resets 6am (Asia/Shanghai)"
#               "session limit. resets 11:30pm (UTC)"
#               "session limit - resets at 6 AM"
# Trigger phrases that mean "claude is rate-limited". Match any.
_SESSION_LIMIT_TRIGGERS = ("session limit", "usage limit")
# Time extractor used after trigger fires. DOTALL so a newline between the
# trigger phrase and the reset time doesn't break the match.
_SESSION_LIMIT_RE = re.compile(
    r"reset(?:s)?(?:\s+at)?\s+"
    r"(\d{1,2})(?::(\d{2}))?\s*([ap]m)?(?:\s*\(([^)]+)\))?",
    re.IGNORECASE | re.DOTALL,
)


def _parse_session_limit(text: str) -> datetime | None:
    """Detect claude's session-limit notice; return the UTC retry instant.

    None if the text isn't a session-limit message at all. Falls back to
    now+30min if it's recognised as session-limit but the time can't be
    parsed, so a wording change doesn't turn into a tight retry loop."""
    low = (text or "").lower()
    if not low:
        return None
    if not any(t in low for t in _SESSION_LIMIT_TRIGGERS):
        return None
    m = _SESSION_LIMIT_RE.search(text)
    if not m:
        return datetime.now(timezone.utc) + timedelta(minutes=30)
    hour = int(m.group(1))
    minute = int(m.group(2) or 0)
    ampm = (m.group(3) or "").lower()
    tz_name = m.group(4) or "UTC"
    if ampm == "pm" and hour < 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")
    now_local = datetime.now(tz)
    target = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now_local:
        target += timedelta(days=1)
    return target.astimezone(timezone.utc)



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
    env = os.environ.copy()
    env["MAKEFLAGS"] = _WORKER_MAKEFLAGS  # propagates to any nested `make` worker spawns
    try:
        proc = subprocess.run(
            args,
            input=input_text,
            capture_output=True,
            text=True,
            cwd=str(cwd),
            env=env,
            timeout=timeout_sec,
            check=False,
            preexec_fn=_apply_worker_rlimits,
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

    # Early session-limit detection on raw output. Claude sometimes prints
    # the limit notice as plain text (non-JSON), which would bypass the
    # post-parse detection further down. Check raw stdout+stderr first.
    _early_haystack = " ".join(filter(None, [stdout, stderr]))
    _early_retry_at = _parse_session_limit(_early_haystack)
    if _early_retry_at is not None:
        raise SessionLimitError(
            f"claude session limit hit; retry at {_early_retry_at.isoformat()}",
            retry_at=_early_retry_at,
        )


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

    # Session-limit detection: claude refused us due to quota exhaustion.
    # Raise so the main loop can sleep instead of burning an attempt.
    _haystack = " ".join(filter(None, [api_error, result_text]))
    _retry_at = _parse_session_limit(_haystack)
    if _retry_at is not None:
        raise SessionLimitError(
            f"claude session limit hit; retry at {_retry_at.isoformat()}",
            retry_at=_retry_at,
        )

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

    # Collaborative debug hint, dropped by `inject-hint` after an escalation.
    # If prompts/_hints/<task_id>.md exists, inline it so the worker sees the
    # human/AI analysis from the previous round.
    hint_path = project_root / "prompts" / "_hints" / f"{task.id}.md"
    hint_block = ""
    if hint_path.exists():
        hint_block = (
            "\n\n--- 协作 debug 提示 (人工/AI 注入，优先于历史错误) ---\n"
            + hint_path.read_text(encoding="utf-8")
        )

    substitutions = {
        "task_id": task.id,
        "title": task.title,
        "stage": task.stage,
        "docs_content": "\n".join(docs_content) or "(no documentation references)",
        "immutable_files": ", ".join(task.immutable_files) or "(none)",
        "previous_error_excerpt": error_block,
        "escalation_hint": hint_block,
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
