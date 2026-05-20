#!/bin/bash
# E4b: 从 C 代码到二进制 — 链接器脚本与运行时
#
# 校验 ysyx-workbench/practice/ 下的裸机 hello 程序：
#   linker.ld + crt0.S + hello.c -> hello_bare.elf
#
# 通过条件：
#   1. linker.ld 存在并指定 ENTRY(_start)
#   2. crt0.S 存在并包含 _start 入口、栈指针初始化、main 调用、ebreak 结束
#   3. Makefile 提供 'bare' target，能产出 hello_bare.elf
#   4. ELF 的 _start 符号位于 0x80000000（RAM 起点）
#   5. ELF 中出现 'ebreak' 指令（运行时退出约定）
#
# 当 riscv32 工具链不可用时降级为 file-only 检查（保留前 3 条静态校验）。

set -euo pipefail
source "$(dirname "$0")/_common.sh"

PRACTICE="$WORKBENCH/practice"

# --- 1. 链接器脚本静态检查 ---
require_artifact "$PRACTICE/linker.ld"
expect_grep "ENTRY(_start)" "$PRACTICE/linker.ld"
# RAM 起点和 _stack_top 必须存在，否则 crt0 跑不起来
expect_grep "ORIGIN" "$PRACTICE/linker.ld"
expect_grep "_stack_top" "$PRACTICE/linker.ld"
expect_grep "_bss_start" "$PRACTICE/linker.ld"
expect_grep "_bss_end" "$PRACTICE/linker.ld"

# --- 2. crt0 启动文件静态检查 ---
require_artifact "$PRACTICE/crt0.S"
expect_grep "_start" "$PRACTICE/crt0.S"
expect_grep "sp" "$PRACTICE/crt0.S"           # 栈指针初始化
expect_grep "call.*main" "$PRACTICE/crt0.S"   # 调用 main
expect_grep "ebreak" "$PRACTICE/crt0.S"       # 退出约定

# --- 3. Makefile 必须能编译裸机目标 ---
require_artifact "$PRACTICE/Makefile"
expect_grep "hello_bare.elf" "$PRACTICE/Makefile"
expect_grep "linker.ld" "$PRACTICE/Makefile"

# --- 4/5. 跑一遍真实构建，校验 _start 落在 RAM 起点 + 含 ebreak 指令 ---
RVCC="${RVCC:-riscv32-unknown-elf-gcc}"
RVOD="${RVOD:-riscv32-unknown-elf-objdump}"
if ! command -v "$RVCC" >/dev/null || ! command -v "$RVOD" >/dev/null; then
    echo "E4b PASS (file-only check, riscv32 toolchain not available)"
    exit 0
fi

clean_build "$PRACTICE"
(cd "$PRACTICE" && make bare) > /tmp/E4b-build.log 2>&1

require_artifact "$PRACTICE/hello_bare.elf"

# _start 应当在 0x80000000——这是 linker.ld 给 RAM 设置的 ORIGIN
START_ADDR=$("$RVOD" -t "$PRACTICE/hello_bare.elf" | awk '/ _start$/{print $1; exit}')
if [[ "$START_ADDR" != "80000000" ]]; then
    echo "E4b FAIL: _start at 0x$START_ADDR, want 0x80000000" >&2
    exit 1
fi

# 反汇编里必须出现 ebreak（程序退出由 crt0 的 ebreak 完成）
"$RVOD" -d "$PRACTICE/hello_bare.elf" > /tmp/E4b-dis.log
expect_grep "ebreak" /tmp/E4b-dis.log

echo "E4b PASS"
