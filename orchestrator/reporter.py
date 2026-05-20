"""Generate markdown reports from the SQLite event stream."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .db import Database
from .tasks import Task


def _utc_now_iso() -> str:
    """Return a naive UTC ISO timestamp (seconds precision) without offset.

    Equivalent to the deprecated datetime.utcnow().isoformat(timespec='seconds'),
    so we can append a literal 'Z' suffix without ending up with '+00:00Z'.
    """
    return (
        datetime.now(timezone.utc)
        .replace(tzinfo=None)
        .isoformat(timespec="seconds")
    )


def generate_task_report(
    db: Database,
    task: Task,
    reports_dir: Path,
) -> Path:
    """Generate reports/<task_id>.md or reports/<task_id>-FAILED.md from events."""
    events = db.list_events(task_id=task.id)
    status = db.task_status(task.id)

    is_failed = status == "failed"
    fname = f"{task.id}-FAILED.md" if is_failed else f"{task.id}.md"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / fname

    lines: list[str] = []
    lines.append(f"# {task.id} — {task.title}")
    lines.append("")
    lines.append(f"**Stage**: {task.stage}")
    lines.append(f"**Status**: {'❌ 失败' if is_failed else '✅ 通过'}")
    lines.append(f"**Generated**: {_utc_now_iso()}Z")
    lines.append("")

    attempts = [e for e in events if e["type"].startswith("attempt_")]
    if attempts:
        started_count = sum(1 for e in attempts if e["type"] == "attempt_started")
        lines.append(f"## 共 {started_count} 次尝试")
        lines.append("")
        for ev in attempts:
            n = ev["payload"].get("attempt_num", "?")
            if ev["type"] == "attempt_started":
                lines.append(f"### attempt {n} 开始 — {ev['ts']}")
            elif ev["type"] == "attempt_passed":
                d = ev["payload"].get("duration_sec", 0)
                lines.append(f"  - ✅ 通过 (耗时 {d:.0f}s)")
            elif ev["type"] == "attempt_failed":
                cat = ev["payload"].get("fail_category", "?")
                excerpt = ev["payload"].get("log_excerpt", "")
                lines.append(f"  - ❌ 失败 (类别: {cat})")
                if excerpt:
                    lines.append("    ```")
                    lines.append(f"    {excerpt}")
                    lines.append("    ```")
        lines.append("")

    codex_events = [e for e in events if e["type"] == "codex_passed"]
    if codex_events:
        last = codex_events[-1]
        lines.append("## Codex Review")
        lines.append("")
        lines.append(last["payload"].get("summary", ""))
        lines.append("")

    done_events = [e for e in events if e["type"] == "task_done"]
    if done_events:
        commit = done_events[-1]["payload"].get("commit", "?")
        lines.append("## Commit")
        lines.append("")
        lines.append(f"`{commit}`")
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
