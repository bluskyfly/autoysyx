"""Same fix as apply_session_limit_hoist_patch.py but uses regex-based
substitution so small whitespace / line-ending differences in worker.py
don't break the match. Idempotent: re-runs are no-ops with a clear print.

Run from autoysyx repo root:
    python3 apply_session_limit_hoist_patch_v2.py
"""
import re
from pathlib import Path

ROOT = Path(__file__).parent
worker_py = ROOT / "orchestrator" / "worker.py"

src = worker_py.read_text()
changed = False

# ----------------------------------------------------------------------
# 1. Replace the entire _SESSION_LIMIT_RE assignment block. Whitespace-tolerant.
# ----------------------------------------------------------------------
re_block_pat = re.compile(
    r'_SESSION_LIMIT_RE\s*=\s*re\.compile\([^)]*?'
    r'session limit[^)]*?\)\s*,\s*re\.IGNORECASE\s*,?\s*\)',
    re.DOTALL,
)
new_re_block = (
    '_SESSION_LIMIT_TRIGGERS = ("session limit", "usage limit")\n'
    '# Time extractor used after trigger fires. DOTALL so a newline between\n'
    '# the trigger phrase and the reset time does not break the match.\n'
    '_SESSION_LIMIT_RE = re.compile(\n'
    '    r"reset(?:s)?(?:\\s+at)?\\s+"\n'
    '    r"(\\d{1,2})(?::(\\d{2}))?\\s*([ap]m)?(?:\\s*\\(([^)]+)\\))?",\n'
    '    re.IGNORECASE | re.DOTALL,\n'
    ')'
)

if "_SESSION_LIMIT_TRIGGERS" in src:
    print("[skip] _SESSION_LIMIT_TRIGGERS already defined — step 1 done")
else:
    m = re_block_pat.search(src)
    if not m:
        raise SystemExit(
            "step 1 FAILED: could not find _SESSION_LIMIT_RE assignment in worker.py.\n"
            "Inspect with:  grep -n _SESSION_LIMIT_RE orchestrator/worker.py"
        )
    src = src[: m.start()] + new_re_block + src[m.end():]
    changed = True
    print("[ok] step 1: rewrote _SESSION_LIMIT_RE block")

# ----------------------------------------------------------------------
# 2. Widen the trigger check inside _parse_session_limit.
# ----------------------------------------------------------------------
trigger_pat = re.compile(
    r'if\s+not\s+text\s+or\s+"session limit"\s+not\s+in\s+text\.lower\(\)\s*:\s*\n'
    r'\s+return\s+None'
)
new_trigger = (
    'low = (text or "").lower()\n'
    '    if not low:\n'
    '        return None\n'
    '    if not any(t in low for t in _SESSION_LIMIT_TRIGGERS):\n'
    '        return None'
)
if "_SESSION_LIMIT_TRIGGERS" in src and "any(t in low for t in _SESSION_LIMIT_TRIGGERS)" in src:
    print("[skip] trigger check already widened — step 2 done")
else:
    m = trigger_pat.search(src)
    if not m:
        raise SystemExit(
            "step 2 FAILED: could not find old trigger check.\n"
            "Inspect with:  grep -n 'session limit\\\" not in' orchestrator/worker.py"
        )
    src = src[: m.start()] + new_trigger + src[m.end():]
    changed = True
    print("[ok] step 2: widened trigger check")

# ----------------------------------------------------------------------
# 3. Hoist a raw-output check to right after _spawn_claude returns.
# ----------------------------------------------------------------------
anchor_pat = re.compile(
    r'(\s+)exit_code,\s*stdout,\s*stderr\s*=\s*_spawn_claude\([^)]*\)\s*\n'
)
hoist_marker = "Early session-limit detection on raw output"

if hoist_marker in src:
    print("[skip] raw-output hoist already present — step 3 done")
else:
    m = anchor_pat.search(src)
    if not m:
        raise SystemExit(
            "step 3 FAILED: could not find _spawn_claude call site.\n"
            "Inspect with:  grep -n _spawn_claude orchestrator/worker.py"
        )
    indent = m.group(1).lstrip("\n").rstrip(" ") or "    "
    # Recover the leading indent (likely 4 spaces) from the matched whitespace.
    indent = "    "
    injection = (
        m.group(0)
        + f'\n{indent}# {hoist_marker}. Claude sometimes prints the limit notice\n'
        + f'{indent}# as plain text (non-JSON), which would bypass the post-parse\n'
        + f'{indent}# detection further down. Check raw stdout+stderr first.\n'
        + f'{indent}_early_haystack = " ".join(filter(None, [stdout, stderr]))\n'
        + f'{indent}_early_retry_at = _parse_session_limit(_early_haystack)\n'
        + f'{indent}if _early_retry_at is not None:\n'
        + f'{indent}    raise SessionLimitError(\n'
        + f'{indent}        f"claude session limit hit; retry at {{_early_retry_at.isoformat()}}",\n'
        + f'{indent}        retry_at=_early_retry_at,\n'
        + f'{indent}    )\n\n'
    )
    src = src[: m.start()] + injection + src[m.end():]
    changed = True
    print("[ok] step 3: hoisted raw-output session-limit check")

# ----------------------------------------------------------------------
if changed:
    worker_py.write_text(src)
    print(f"\nwrote {worker_py}")
else:
    print("\nno changes needed — file already up to date")

print("\nVerify:")
print("  grep -n 'Early session-limit\\|_SESSION_LIMIT_TRIGGERS' orchestrator/worker.py")
print("  python3 -c \"from orchestrator.worker import _parse_session_limit; \"\\")
print("    \"print(_parse_session_limit(\\\"You've hit your session limit \u00b7 resets 11:30pm (Asia/Shanghai)\\\"))\"")
