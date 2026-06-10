"""Harden session-limit detection in orchestrator/worker.py.

Root cause being fixed:
  When claude hits its session quota, it prints plain text to stdout
  (e.g. "You've hit your session limit · resets 11:30pm (Asia/Shanghai)")
  instead of a JSON envelope. The current code path:

      try: envelope = json.loads(stdout)
      except json.JSONDecodeError:
          return WorkerResult(api_error="claude returned non-JSON envelope ...")

  This early-return bypasses the existing session-limit check that lives
  near the end of run_worker, so SessionLimitError is never raised and
  the attempt is wasted.

Fix:
  Insert a session-limit check on the raw (stdout + stderr) string
  immediately after _spawn_claude returns, before any JSON parsing.
  Also widen the trigger to accept "usage limit" (used by newer claude
  CLI builds) and add re.DOTALL so newlines between trigger phrase
  and reset time don't kill the regex match.

Idempotent-by-assertion: re-running on a tree that already has the
hoist will assert-fail (or the patched block is recognised and skipped)
without writing.

Run from the autoysyx repo root:

    python3 apply_session_limit_hoist_patch.py
"""
from pathlib import Path

ROOT = Path(__file__).parent
worker_py = ROOT / "orchestrator" / "worker.py"

src = worker_py.read_text()

# ---- 1. Widen _parse_session_limit triggers + add DOTALL. ----
old_parse_head = '''_SESSION_LIMIT_RE = re.compile(
    r"session limit.{0,40}?resets(?:\\s+at)?\\s+"
    r"(\\d{1,2})(?::(\\d{2}))?\\s*([ap]m)?(?:\\s*\\(([^)]+)\\))?",
    re.IGNORECASE,
)'''
new_parse_head = '''# Trigger phrases that mean "claude is rate-limited". Match any.
_SESSION_LIMIT_TRIGGERS = ("session limit", "usage limit")
# Time extractor used after trigger fires. DOTALL so a newline between the
# trigger phrase and the reset time doesn't break the match.
_SESSION_LIMIT_RE = re.compile(
    r"reset(?:s)?(?:\\s+at)?\\s+"
    r"(\\d{1,2})(?::(\\d{2}))?\\s*([ap]m)?(?:\\s*\\(([^)]+)\\))?",
    re.IGNORECASE | re.DOTALL,
)'''
assert old_parse_head in src, "worker.py: _SESSION_LIMIT_RE block not in expected shape"
src = src.replace(old_parse_head, new_parse_head, 1)

# ---- 2. Widen the trigger check in _parse_session_limit. ----
old_trigger = 'if not text or "session limit" not in text.lower():\n        return None'
new_trigger = ('low = (text or "").lower()\n'
               '    if not low:\n'
               '        return None\n'
               '    if not any(t in low for t in _SESSION_LIMIT_TRIGGERS):\n'
               '        return None')
assert old_trigger in src, "worker.py: trigger check not in expected shape"
src = src.replace(old_trigger, new_trigger, 1)

# ---- 3. Hoist a raw-output check to right after _spawn_claude returns. ----
anchor = '    exit_code, stdout, stderr = _spawn_claude(args, "", work_dir, timeout_sec)\n'
injection = anchor + '''
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

'''
assert src.count(anchor) == 1, "worker.py: _spawn_claude anchor not unique"
assert "Early session-limit detection on raw output" not in src, (
    "worker.py: hoist already applied; nothing to do"
)
src = src.replace(anchor, injection, 1)

worker_py.write_text(src)
print(f"patched {worker_py}")
print()
print("Verify with:")
print('  grep -n "Early session-limit\\|_SESSION_LIMIT_TRIGGERS" orchestrator/worker.py')
print('  python3 -c "from orchestrator.worker import _parse_session_limit; '
      'print(_parse_session_limit(chr(34)+chr(34)+\\"You\u2019ve hit your session limit \u00b7 resets 11:30pm (Asia/Shanghai)\\"))"')
