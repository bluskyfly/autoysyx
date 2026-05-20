#!/bin/bash
# test_runner/_common.sh — Shared utilities sourced by per-task verifier scripts.
# Verifier scripts should `source` this and use the helpers below.

set -euo pipefail

# Path helpers (always relative to repo root).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKBENCH="${YSYX_WORKBENCH:-$REPO_ROOT/ysyx-workbench}"

# expect_grep <keyword> <file>: fail if keyword not in file.
expect_grep() {
    local kw="$1"; local file="$2"
    if ! grep -q -- "$kw" "$file"; then
        echo "expect_grep MISS: '$kw' not in $file" >&2
        return 1
    fi
}

# clean_build <dir>: cd then make clean (used to defeat cache poisoning).
clean_build() {
    (cd "$1" && make clean)
}

# require_file <path>: fail with clear msg if path missing.
require_file() {
    if [[ ! -f "$1" ]]; then
        echo "missing required file: $1" >&2
        return 2
    fi
}

# require_artifact <path>: like require_file but more meaningful name for tasks.
require_artifact() { require_file "$@"; }
