"""Patch orchestrator/{worker,main}.py so that claude session-limit errors
sleep through the announced reset window (no attempt burned), with:

- live Shanghai-time countdown on a TTY (in-place line refresh)
- state/waiting.json for external visibility
- a NOTICE appended to prior_errors so the resuming attempt knows it's a
  continuation rather than a fresh start

Run from the autoysyx repo root:

    python3 apply_session_limit_patch.py

The script is idempotent-by-assertion: if the source files don't match the
expected pre-patch shape (e.g. you've already applied this, or the file has
been edited elsewhere), an `assert` fires immediately and nothing is written.
Recover with `git checkout orchestrator/worker.py orchestrator/main.py` and
re-run.
"""
from pathlib import Path

ROOT = Path(__file__).parent
worker_py = ROOT / "orchestrator" / "worker.py"
main_py = ROOT / "orchestrator" / "main.py"

# ============================================================================
# worker.py
# ============================================================================
w = worker_py.read_text()

# --- 1. Extend the stdlib import block. ------------------------------------
old_imports = "import json\nimport os\nimport resource\nimport shlex\nimport subprocess"
new_imports = (
    "import json\nimport os\nimport re\nimport resource\nimport shlex\n"
    "import subprocess\nimport time\n"
    "from datetime import datetime, timedelta, timezone\n"
    "from zoneinfo import ZoneInfo"
)
assert old_imports in w, "worker.py: import block not found"
w = w.replace(old_imports, new_imports)

# --- 2. Add SessionLimitError + parser right after WorkerTimeout. ----------
old_marker = ('class WorkerTimeout(Exception):\n'
              '    """Raised when the claude CLI subprocess exceeds its timeout."""\n')
addition = old_marker + '''

class SessionLimitError(Exception):
    """Raised when claude session quota is exhausted. Carries the UTC datetime
    at which the orchestrator should retry the same attempt."""

    def __init__(self, message: str, retry_at: datetime):
        super().__init__(message)
        self.retry_at = retry_at


# Matches e.g.  "session limit · resets 6am (Asia/Shanghai)"
#               "session limit. resets 11:30pm (UTC)"
#               "session limit - resets at 6 AM"
_SESSION_LIMIT_RE = re.compile(
    r"session limit.{0,40}?resets(?:\\s+at)?\\s+"
    r"(\\d{1,2})(?::(\\d{2}))?\\s*([ap]m)?(?:\\s*\\(([^)]+)\\))?",
    re.IGNORECASE,
)


def _parse_session_limit(text: str) -> datetime | None:
    """Detect claude's session-limit notice; return the UTC retry instant.

    None if the text isn't a session-limit message at all. Falls back to
    now+30min if it's recognised as session-limit but the time can't be
    parsed, so a wording change doesn't turn into a tight retry loop."""
    if not text or "session limit" not in text.lower():
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

'''
assert w.count(old_marker) == 1, "worker.py: WorkerTimeout marker not unique"
w = w.replace(old_marker, addition)

# --- 3. Before the final `return WorkerResult(...)`, raise on session limit.
sniff_block = '''    # Session-limit detection: claude refused us due to quota exhaustion.
    # Raise so the main loop can sleep instead of burning an attempt.
    _haystack = " ".join(filter(None, [api_error, result_text]))
    _retry_at = _parse_session_limit(_haystack)
    if _retry_at is not None:
        raise SessionLimitError(
            f"claude session limit hit; retry at {_retry_at.isoformat()}",
            retry_at=_retry_at,
        )

    return WorkerResult('''
old_ret = "    return WorkerResult(\n        exit_code=exit_code,\n        raw_stdout=stdout,"
assert old_ret in w, "worker.py: final return not found"
w = w.replace(
    old_ret,
    sniff_block + "\n        exit_code=exit_code,\n        raw_stdout=stdout,",
    1,
)

worker_py.write_text(w)
print(f"patched {worker_py}")

# ============================================================================
# main.py
# ============================================================================
m = main_py.read_text()

# --- 1. Extend the worker import to include SessionLimitError. -------------
old_imp = "    from .worker import run_worker, assemble_prompt"
new_imp = "    from .worker import run_worker, assemble_prompt, SessionLimitError"
assert old_imp in m, "main.py: worker import not found"
m = m.replace(old_imp, new_imp)

# --- 2. Insert `except SessionLimitError` BEFORE the existing catch-all. ---
old_except = (
    "            try:\n"
    "                worker_res = run_worker(\n"
    "                    prompt=prompt,\n"
    "                    work_dir=root,\n"
    "                    add_dirs=[root / \"docs-md\", root / \"ysyx-workbench\"],\n"
    "                )\n"
    "            except Exception as e:\n"
)
new_except = (
    "            try:\n"
    "                worker_res = run_worker(\n"
    "                    prompt=prompt,\n"
    "                    work_dir=root,\n"
    "                    add_dirs=[root / \"docs-md\", root / \"ysyx-workbench\"],\n"
    "                )\n"
    "            except SessionLimitError as e:\n"
    "                # Quota exhaustion: don't burn an attempt. Sleep until\n"
    "                # claude's stated reset time, then redo this same attempt.\n"
    "                import time as _t, json as _json, sys as _sys\n"
    "                from datetime import datetime as _dt, timezone as _tz\n"
    "                from zoneinfo import ZoneInfo as _ZI\n"
    "                _SH = _ZI(\"Asia/Shanghai\")\n"
    "                attempt_num -= 1  # cancel this iteration's increment\n"
    "                db.append_event(type=\"session_limit_wait\", task_id=nxt.id,\n"
    "                                payload={\"retry_at\": e.retry_at.isoformat(),\n"
    "                                         \"attempt_num\": attempt_num + 1})\n"
    "                retry_at = e.retry_at\n"
    "                total_sec = max(60.0,\n"
    "                                (retry_at - _dt.now(_tz.utc)).total_seconds() + 60)\n"
    "                local_retry = retry_at.astimezone(_SH)\n"
    "                click.secho(\n"
    "                    f\"\\n  \u23f8  {nxt.id}: claude session limit hit\\n\"\n"
    "                    f\"     attempt {attempt_num + 1}/{nxt.max_attempts} will resume at \"\n"
    "                    f\"{local_retry.strftime('%Y-%m-%d %H:%M:%S')} (Asia/Shanghai)\\n\"\n"
    "                    f\"     ({int(total_sec)//60} min total, +60s buffer)\\n\"\n"
    "                    f\"     orchestrator is SLEEPING, not crashed. Ctrl+C to abort.\",\n"
    "                    fg=\"yellow\",\n"
    "                )\n"
    "                waiting_path = root / \"state\" / \"waiting.json\"\n"
    "                waiting_path.parent.mkdir(exist_ok=True)\n"
    "                waiting_path.write_text(_json.dumps({\n"
    "                    \"task_id\": nxt.id,\n"
    "                    \"reason\": \"session_limit\",\n"
    "                    \"retry_at_utc\": retry_at.isoformat(),\n"
    "                    \"retry_at_shanghai\": local_retry.isoformat(),\n"
    "                    \"sleep_started_utc\": _dt.now(_tz.utc).isoformat(),\n"
    "                    \"total_sec\": int(total_sec),\n"
    "                }, indent=2))\n"
    "                remaining = total_sec\n"
    "                is_tty = _sys.stdout.isatty()\n"
    "                while remaining > 0:\n"
    "                    chunk = min(60.0, remaining)\n"
    "                    if is_tty:\n"
    "                        mins, secs = divmod(int(remaining), 60)\n"
    "                        hrs, mins = divmod(mins, 60)\n"
    "                        click.echo(\n"
    "                            f\"\\r     \u23f3 {hrs:02d}:{mins:02d}:{secs:02d} \"\n"
    "                            f\"remaining (resume at \"\n"
    "                            f\"{local_retry.strftime('%H:%M:%S')} \u4e0a\u6d77\u65f6\u95f4)    \",\n"
    "                            nl=False,\n"
    "                        )\n"
    "                    _t.sleep(chunk)\n"
    "                    remaining -= chunk\n"
    "                if is_tty:\n"
    "                    click.echo(\"\")\n"
    "                try:\n"
    "                    waiting_path.unlink()\n"
    "                except FileNotFoundError:\n"
    "                    pass\n"
    "                db.append_event(type=\"session_limit_resume\", task_id=nxt.id,\n"
    "                                payload={\"attempt_num\": attempt_num + 1})\n"
    "                click.secho(f\"  \u25b6 {nxt.id}: resuming attempt {attempt_num + 1}\",\n"
    "                            fg=\"green\")\n"
    "                # Tell the next iteration's prompt that this isn't a real\n"
    "                # failure but a resumed run, so claude reconnects with WIP\n"
    "                # files in workspace instead of starting from scratch.\n"
    "                prior_errors.append(\n"
    "                    f\"NOTICE: previous run of {nxt.id} was interrupted by \"\n"
    "                    f\"claude session limit (not a real failure). Partial \"\n"
    "                    f\"work-in-progress files may exist in the workspace. \"\n"
    "                    f\"Inspect workspace state first (git status, ls work_dir), \"\n"
    "                    f\"then continue from where you left off rather than \"\n"
    "                    f\"starting from scratch.\"\n"
    "                )\n"
    "                continue\n"
    "            except Exception as e:\n"
)
assert old_except in m, "main.py: try/except worker block not found"
m = m.replace(old_except, new_except)

main_py.write_text(m)
print(f"patched {main_py}")

print()
print("Verify with:")
print("  grep -n 'SessionLimitError\\|local_retry\\|waiting.json' orchestrator/main.py")
print("  python3 -c 'import orchestrator.main; print(\"imports ok\")'")
print("  make test")
