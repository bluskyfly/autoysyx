"""Independent code review via Codex (humanize:ask-codex)."""
from __future__ import annotations

import os
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

ASK_CODEX_SCRIPT = os.environ.get(
    "AUTOYSYX_ASK_CODEX",
    "/home/curry/.claude/plugins/cache/humania/humanize/1.15.0/scripts/ask-codex.sh",
)

# Diff is spilled to this path (relative to project_root) so codex can read it
# itself — passing a multi-megabyte diff via argv hits execve()'s ARG_MAX.
_DIFF_FILE_RELPATH = ".autoysyx/codex-diff-{task_id}.patch"

# Codex can't usefully digest a multi-hundred-megabyte diff. Above this size we
# write head+tail of the raw diff plus a `--stat` summary, marked truncated.
_DIFF_MAX_BYTES = 256 * 1024
_DIFF_HEAD_BYTES = 96 * 1024
_DIFF_TAIL_BYTES = 32 * 1024


def _maybe_truncate_diff(diff_text: str) -> str:
    raw = diff_text.encode("utf-8", errors="replace")
    if len(raw) <= _DIFF_MAX_BYTES:
        return diff_text
    head = raw[:_DIFF_HEAD_BYTES].decode("utf-8", errors="replace")
    tail = raw[-_DIFF_TAIL_BYTES:].decode("utf-8", errors="replace")
    omitted = len(raw) - _DIFF_HEAD_BYTES - _DIFF_TAIL_BYTES
    return (
        f"[diff truncated: {len(raw)} bytes total, "
        f"omitted middle {omitted} bytes]\n"
        f"=== first {_DIFF_HEAD_BYTES} bytes ===\n{head}\n"
        f"=== last {_DIFF_TAIL_BYTES} bytes ===\n{tail}\n"
    )

# Heuristic: codex flagging serious problems usually surfaces one of these keywords.
_REJECT_PATTERNS = [
    r"FATAL", r"严重", r"必须修复", r"must fix", r"critical bug",
    r"不能合并", r"do not merge", r"反对", r"reject",
]


@dataclass
class ReviewResult:
    approved: bool
    skipped: bool
    summary: str
    log_path: str | None = None
    cost_usd: float = 0.0


def _run_codex(question: str, cwd: Path, timeout_sec: int) -> tuple[int, str, str]:
    proc = subprocess.run(
        [ASK_CODEX_SCRIPT, "--codex-timeout", str(timeout_sec), question],
        capture_output=True,
        text=True,
        cwd=str(cwd),
        timeout=timeout_sec + 60,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _question_template(diff_relpath: str, task_id: str) -> str:
    return f"""你是独立 reviewer。本次 task {task_id} 的完整 git diff 已写入 `{diff_relpath}` (相对当前工作目录)。请先读取该文件，然后回答:

1. 这次改动有没有"看起来通过但实际错误"的迹象?
2. 有没有改了测试代码/Makefile/官方约束的痕迹?
3. 有没有用未定义行为/碰运气的写法?
4. 异常/CSR/访存边界/RTL 初始化等晚爆雷点有没有遗漏?

如果发现严重问题, 请在开头明确写 "FATAL:" 或 "必须修复" 等关键字, 后续说明.
没有问题就直接说 "Looks good. No issues." 中文回复, 简洁.
"""


def review_diff(
    diff_text: str,
    task_id: str,
    project_root: Path,
    timeout_sec: int = 600,
) -> ReviewResult:
    diff_relpath = _DIFF_FILE_RELPATH.format(task_id=task_id)
    diff_path = project_root / diff_relpath
    diff_path.parent.mkdir(parents=True, exist_ok=True)
    diff_path.write_text(_maybe_truncate_diff(diff_text))
    question = _question_template(diff_relpath, task_id)
    exit_code, stdout, stderr = _run_codex(question, cwd=project_root, timeout_sec=timeout_sec)

    if exit_code != 0:
        return ReviewResult(
            approved=False,
            skipped=True,
            summary=stderr.strip() or "codex returned non-zero exit",
        )

    summary = stdout.strip()
    rejected = any(re.search(pat, summary, re.IGNORECASE) for pat in _REJECT_PATTERNS)
    return ReviewResult(approved=not rejected, skipped=False, summary=summary)
