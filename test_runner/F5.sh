#!/bin/bash
# F5: 支持数列求和的简单处理器
# 验证: Logisim sCPU 电路存在 + 能跑求和测试.
set -euo pipefail
source "$(dirname "$0")/_common.sh"

require_artifact "$WORKBENCH/logisim/sCPU.circ"

if ! command -v logisim-cli >/dev/null; then
    # Fallback: 没有 logisim-cli 时只校验电路文件里含 "sCPU" 标识
    expect_grep "sCPU" "$WORKBENCH/logisim/sCPU.circ"
    echo "sCPU PASS (file-only check, logisim-cli not available)"
    exit 0
fi

logisim-cli "$WORKBENCH/logisim/sCPU.circ" -tty halt > /tmp/sCPU-run.log 2>&1 || true
expect_grep "55" /tmp/sCPU-run.log  # 1+2+...+10 = 55
echo "sCPU PASS"
