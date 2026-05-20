#!/bin/bash
# check_env.sh - 校验 tools/env-lock.yaml 描述的工具链没漂移
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCK="${SCRIPT_DIR}/env-lock.yaml"
if [[ ! -f "$LOCK" ]]; then
    echo "env-lock.yaml not found — run bootstrap first" >&2
    exit 2
fi

fail=0
while IFS=': ' read -r key value; do
    [[ "$key" =~ ^- ]] || continue
    tool=$(echo "$value" | awk -F: '{print $1}')
    locked=$(grep -A1 "name: $tool" "$LOCK" | awk '/version:/ {print $2}')
    [[ -z "$locked" ]] && continue
    current=$(${tool} --version 2>&1 | head -1)
    if ! echo "$current" | grep -qF "$locked"; then
        echo "ENV DRIFT: $tool expected $locked, got: $current" >&2
        fail=1
    fi
done < "$LOCK"

if [[ $fail -ne 0 ]]; then
    exit 1
fi
echo "env check OK"
