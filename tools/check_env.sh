#!/bin/bash
# check_env.sh - 校验 tools/env-lock.yaml 描述的工具链没漂移
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCK="${SCRIPT_DIR}/env-lock.yaml"
if [[ ! -f "$LOCK" ]]; then
    echo "env-lock.yaml not found — run bootstrap first" >&2
    exit 2
fi

# Delegate to Python (pyyaml is a project dep)
python3 - "$LOCK" <<'PY'
import subprocess
import sys

import yaml

lock_path = sys.argv[1]
with open(lock_path) as f:
    parsed = yaml.safe_load(f)

fail = 0
for entry in parsed.get("tools", []):
    if not entry.get("available"):
        continue
    name = entry["name"]
    locked = entry.get("version", "")
    try:
        result = subprocess.run(
            [name, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            stdin=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print(f"ENV DRIFT: {name} not callable", file=sys.stderr)
        fail = 1
        continue
    current = result.stdout.splitlines()[0].strip() if result.stdout else ""
    if current != locked:
        print(f"ENV DRIFT: {name} expected {locked!r}, got: {current!r}", file=sys.stderr)
        fail = 1

if fail:
    sys.exit(1)
print("env check OK")
PY
