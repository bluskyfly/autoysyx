#!/bin/bash
# run-difftest.sh - 调用 ysyx-workbench/npc 与 nemu 跑 difftest
#
# Usage: run-difftest.sh <test-image.bin>
#
# Required env:
#   YSYX_WORKBENCH: ysyx-workbench 仓库根
#   NEMU_HOME:      $YSYX_WORKBENCH/nemu
#   NPC_HOME:       $YSYX_WORKBENCH/npc
set -euo pipefail

WORKBENCH="${YSYX_WORKBENCH:?must set YSYX_WORKBENCH}"
NEMU_HOME="${NEMU_HOME:-$WORKBENCH/nemu}"
NPC_HOME="${NPC_HOME:-$WORKBENCH/npc}"

IMAGE="${1:-${NPC_HOME}/build/cpu-tests.bin}"
if [[ ! -f "$IMAGE" ]]; then
    echo "DIFFTEST: image not found: $IMAGE" >&2
    exit 2
fi

# Build NEMU as reference (so library).
echo "==> building NEMU as difftest reference"
make -C "$NEMU_HOME" ARCH=riscv32-nemu SHARE=1 clean
make -C "$NEMU_HOME" ARCH=riscv32-nemu SHARE=1

REF_SO="$(find "$NEMU_HOME/build" -name 'riscv32-nemu-interpreter-so' | head -1)"
if [[ -z "$REF_SO" || ! -f "$REF_SO" ]]; then
    echo "DIFFTEST: reference .so not found in $NEMU_HOME/build" >&2
    exit 2
fi

# Run NPC simulator with --diff.
# B5b: forward PIPELINE env var so PIPELINE=1 picks the cpu_pipeline top
# (instead of single-cycle cpu.v). Default PIPELINE=0 keeps old D5 behaviour.
PIPELINE="${PIPELINE:-0}"
echo "==> running NPC with difftest against $REF_SO (PIPELINE=$PIPELINE)"
cd "$NPC_HOME"
rm -rf build/obj_dir build/npc
make sim PIPELINE="$PIPELINE" ARGS="--diff=$REF_SO --image=$IMAGE" \
    > /tmp/difftest-run.log 2>&1 || true

if grep -q "DIFFTEST: failed" /tmp/difftest-run.log; then
    echo "DIFFTEST: failed" >&2
    tail -100 /tmp/difftest-run.log >&2
    exit 1
fi

if grep -q "HIT GOOD TRAP" /tmp/difftest-run.log; then
    echo "DIFFTEST: passed"
    exit 0
fi

echo "DIFFTEST: ambiguous outcome — neither GOOD TRAP nor failed marker" >&2
tail -50 /tmp/difftest-run.log >&2
exit 1
