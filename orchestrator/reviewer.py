"""Independent code review via the OpenAI `codex` CLI.

The diff is piped to `codex exec` over stdin so we never hit execve()'s
ARG_MAX, and codex doesn't need disk-read permission inside its sandbox —
everything it needs is in the prompt.
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

CODEX_BIN = os.environ.get("AUTOYSYX_CODEX_BIN", "codex")

# Truncated diff is inlined directly in the codex prompt. Codex runs under
# bwrap and can't always read disk files, so we don't spill — we just keep
# the diff small enough to fit safely inside argv/stdin and the model context.
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

# Inconclusive markers: codex says it can't form a judgment because the diff
# is empty / missing. Worker-side tasks that only touch .gitignore'd paths
# (e.g. ysyx-workbench/) produce an empty staged diff. Codex sometimes prefixes
# its "I can't review nothing" reply with `必须修复:` which would otherwise
# trip the reject heuristic above. Treat any of these as a skipped review
# (same outcome as codex CLI failure), NOT a rejection.
_INCONCLUSIVE_PATTERNS = [
    r"diff 为空",
    r"\(no diff yet\)",
    r"\bno diff\b",
    r"diff is empty",
    r"无法对.{0,20}改动",
    r"无法.{0,10}review",
    r"请提供.{0,20}diff",
    r"give me .{0,20}changes",
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
        [
            CODEX_BIN, "exec",
            "--sandbox", "read-only",
            "--skip-git-repo-check",
            "--ephemeral",
            "-",
        ],
        input=question,
        capture_output=True,
        text=True,
        cwd=str(cwd),
        timeout=timeout_sec + 60,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _question_template(diff_text: str, task_id: str) -> str:
    return f"""你是独立 reviewer。下面是本次 task {task_id} 的 git diff（可能被截断，标记会写明）。请基于 diff 内容回答:

1. 这次改动有没有"看起来通过但实际错误"的迹象?
2. 有没有改了测试代码/Makefile/官方约束的痕迹?
3. 有没有用未定义行为/碰运气的写法?
4. 异常/CSR/访存边界/RTL 初始化等晚爆雷点有没有遗漏?

如果发现严重问题, 请在开头明确写 "FATAL:" 或 "必须修复" 等关键字, 后续说明.
没有问题就直接说 "Looks good. No issues." 中文回复, 简洁.

=== diff 开始 ===
{diff_text}
=== diff 结束 ===
"""


def review_diff(
    diff_text: str,
    task_id: str,
    project_root: Path,
    timeout_sec: int = 600,
) -> ReviewResult:
    truncated = _maybe_truncate_diff(diff_text)
    question = _question_template(truncated, task_id)
    exit_code, stdout, stderr = _run_codex(question, cwd=project_root, timeout_sec=timeout_sec)

    if exit_code != 0:
        return ReviewResult(
            approved=False,
            skipped=True,
            summary=stderr.strip() or "codex returned non-zero exit",
        )

    summary = stdout.strip()
    inconclusive = any(
        re.search(pat, summary, re.IGNORECASE) for pat in _INCONCLUSIVE_PATTERNS
    )
    if inconclusive:
        # Codex is complaining about missing input, not condemning the code.
        # Fall back to "review skipped" so the task isn't killed unfairly.
        return ReviewResult(approved=False, skipped=True, summary=summary)
    rejected = any(re.search(pat, summary, re.IGNORECASE) for pat in _REJECT_PATTERNS)
    return ReviewResult(approved=not rejected, skipped=False, summary=summary)
