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


def _question_template(diff_text: str, task_id: str) -> str:
    return f"""你是独立 reviewer，请评估下面这次 git diff (针对 task {task_id}):

```diff
{diff_text}
```

请回答:
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
    question = _question_template(diff_text, task_id)
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
