#!/bin/bash
# bootstrap.sh - 一次性装齐 YSYX 所需工具链
#
# 期望 sudo 权限 (passwordless or via SUDO_ASKPASS).
# 装完后调 check_env.sh 校验, 通过后由 orchestrator 写 tools/env-lock.yaml.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="${SCRIPT_DIR}/bootstrap.log"
: > "$LOG"

log() { echo "[bootstrap] $*" | tee -a "$LOG"; }

ensure_apt() {
    log "apt update + install: $*"
    sudo apt-get update -qq 2>&1 | tee -a "$LOG"
    sudo apt-get install -y -qq "$@" 2>&1 | tee -a "$LOG"
}

# 1. 基本依赖
ensure_apt build-essential git curl ca-certificates \
           bsdmainutils device-tree-compiler libreadline-dev libsdl2-dev

# 2. RISC-V cross compilers
ensure_apt gcc-riscv64-linux-gnu g++-riscv64-linux-gnu \
           gcc-riscv64-unknown-elf || log "gcc-riscv64-unknown-elf not in repos, will use riscv32 only"

# 3. QEMU (用于 cross-check 某些 PA)
ensure_apt qemu-system-misc qemu-user

# 4. mill (Chisel build tool)
if ! command -v mill >/dev/null; then
    log "installing mill..."
    sudo curl -sL https://github.com/com-lihaoyi/mill/releases/download/0.11.7/0.11.7 \
        -o /usr/local/bin/mill
    sudo chmod +x /usr/local/bin/mill
fi

# 5. ysyx-workbench + ysyxSoC clone (子模块 init)
WORKBENCH_DIR="${SCRIPT_DIR}/../ysyx-workbench"
if [[ ! -d "$WORKBENCH_DIR" ]]; then
    log "cloning ysyx-workbench..."
    git clone --recursive https://github.com/OSCPU/ysyx-workbench.git "$WORKBENCH_DIR" \
        2>&1 | tee -a "$LOG"
fi
SOC_DIR="${WORKBENCH_DIR}/ysyxSoC"
if [[ ! -d "$SOC_DIR" ]]; then
    log "cloning ysyxSoC..."
    git clone https://github.com/OSCPU/ysyxSoC.git "$SOC_DIR" 2>&1 | tee -a "$LOG"
fi

# 6. smoke test
log "smoke: verilator + yosys"
verilator --version | tee -a "$LOG"
yosys --version | tee -a "$LOG"
log "smoke: riscv32-unknown-elf-gcc"
riscv32-unknown-elf-gcc --version | head -1 | tee -a "$LOG"

log "bootstrap done."
