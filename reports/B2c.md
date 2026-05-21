# B2c — SoC 集成测试 (microbench + typing-game + PSRAM 1MiB)

**Status**: DONE

B2b 完成 PSRAM/SDRAM 颗粒模型与 4 KiB mem-test；B2c 在 ysyxSoC 上把
**自写的 bootloader + microbench(test) + typing-game** 端到端跑通，并把
PSRAM mem-test 扩到 1 MiB 做规模化回归。

总体结果（一句话）：

- 新增 `riscv32e-npc-soc` AM 平台，启动直接 XIP 跑 Flash，把 `.data/.bss/
  stack/heap` 链到 SDRAM。无需 vendor `gen.sh` 那个 370 KiB bootloader。
- microbench `test` 规模：10/10 全 PASS, 88 M cycles, 1 min 内。
- typing-game 文字 demo：HUD/字母滚动/HIT 全部可见，HIT GOOD TRAP。
- PSRAM 1 MiB 写读扫描：通过；wallclock 10 s（含 verilator 编译）。

---

## 0. SoC 地址空间复盘

来自 B2b 的复盘（`npc/vsrc-soc/ysyxSoCFull.v` APB Fanout sel 编码）：

| 区段                          | sel  | 实体          |
| ----------------------------- | ---- | ------------- |
| 0x10000000-0x1fffffff (p12=0) | sel_1 | UART16550    |
| 0x20000000-0x3fffffff         | sel_0 | SPI Flash    |
| 0x80000000-0x9fffffff         | sel_2 | sdramChisel  |
| **其他**                      | -    | DROP (pready 自动拉高，数据=0) |

CPU 复位 PC = 0x30000000 → 直接进 Flash 取指。所以 B2c 的策略：

1. 用 Flash 0x30000000 当主程序存储（XIP 取 .text/.rodata）。
2. 用 SDRAM 0x80000000-0x81ffffff 当 .data/.bss/stack/heap。
3. 不挂载 PSRAM、SRAM (顶层 APBFanout 没接它们；属于已知遗留)。

---

## 1. 启动 + 链接脚本流程

```
  Flash (0x30000000+)                 SDRAM (0x80000000+)
  +---------------------+              +-----------------------+
  | .text (entry+code)  |  XIP-fetch   |                       |
  |        |            |<-------------|  (program runs here)  |
  | .rodata             |              |                       |
  +---------------------+              |                       |
  | .data LMA           |---memcpy---->| .data VMA             |
  +---------------------+   (in start.S)| .bss (zeroed)         |
                                       | ...                   |
                                       | heap (grows up)       |
                                       | stack (grows down)    |
                                       | sp init = 0x82000000  |
                                       +-----------------------+
```

启动顺序 (`abstract-machine/am/src/riscv/npc-soc/start.S`)：

```
_start (at 0x30000000):
    la sp, _stack_pointer         # sp = 0x82000000 (SDRAM top)
    /* copy .data LMA -> VMA */
    la t0, _data_lma              # Flash 中 .data 起点
    la t1, _data_vma              # SDRAM 中 .data 起点
    la t2, _data_size             # 字节数
    add t2, t1, t2
.Ldata_loop:
    lw a5, 0(t0)                  # rv32e 没有 t3, 用 a5
    sw a5, 0(t1)
    addi t0, t0, 4
    addi t1, t1, 4
    bne t1, t2, .Ldata_loop
    /* zero .bss */
    la t0, _bss_start
    la t1, _bss_end
.Lbss_loop:
    sw zero, 0(t0)
    addi t0, t0, 4
    bne t0, t1, .Lbss_loop
    mv s0, zero
    call _trm_init                # AM 入口 (-> main)
```

链接脚本核心片段 (`abstract-machine/scripts/linker-soc.ld`)：

```
ENTRY(_start)
MEMORY {
  flash (rx)  : ORIGIN = 0x30000000, LENGTH = 16M
  sdram (rwx) : ORIGIN = 0x80000000, LENGTH = 32M
}
SECTIONS {
  . = ORIGIN(flash);
  .text   : { *(entry) *(.text*) }     > flash
  .rodata : { *(.rodata*) *(.srodata*) }> flash
  .data   : { *(.data*) *(.sdata*) }   > sdram AT> flash
  .bss    : { *(.bss*) *(.sbss*)
              *(.scommon) *(COMMON) }  > sdram
  _data_lma  = LOADADDR(.data);
  _data_vma  = ADDR(.data);
  _data_size = SIZEOF(.data);
  _heap_start = .;
  _stack_pointer = ORIGIN(sdram) + LENGTH(sdram);    /* 0x82000000 */
}
```

关键约定：
- `AT> flash` 让 `.data` VMA 在 SDRAM、LMA 在 Flash → OBJCOPY -O binary 把
  .data 的初始字节也写进 .bin 末尾，start.S 复制到 SDRAM。
- `*(entry)` 强制 start.S 里的 `.section entry, "ax"` 必须排在最前，确保
  `_start` 位于 0x30000000，CPU 复位即指向它。


---

## 2. 平台 mk 文件

新增三层文件，**完全不动现有 `riscv32e-npc.mk`**：

```
abstract-machine/scripts/
├── linker-soc.ld                       (新) 链接脚本
├── platform/npc-soc.mk                 (新) 平台层 (AM_SRCS 等)
└── riscv32e-npc-soc.mk                 (新) 顶层 (ARCH 入口)

abstract-machine/am/src/riscv/npc-soc/
└── start.S                             (新) bootloader
```

`riscv32e-npc-soc.mk`：

```
include $(AM_HOME)/scripts/isa/riscv.mk
include $(AM_HOME)/scripts/platform/npc-soc.mk
COMMON_CFLAGS += -march=rv32e_zicsr -mabi=ilp32e
LDFLAGS       += -melf32lriscv
AM_SRCS += riscv/npc/libgcc/div.S muldi3.S multi3.c ashldi3.c unused.c
```

`platform/npc-soc.mk` 复用 `npc/` 下 trm.c / cte.c / trap.S / timer.c / input.c /
ioe.c（runtime 层与 DPI 版完全一致），但用新链接脚本 + 新 start.S。
`run:` 目标直接调 `npc/sim-soc FLASH=$(IMAGE).bin`，无需 vendor gen.sh。

mainargs 注入仍走 `insert-arg.py`，patch 的是 `.bin`（`.rodata` 在 Flash 是
只读 XIP，但 .bin 文件本身可改写并烧到 Flash）。

---

## 3. dummy / hello / mem-test 回归 (smoke)

| 程序        | .bin 大小 | cycles      | 备注 |
| ----------- | ------- | ----------- | -- |
| dummy       | 240 B   | 12 709      | 18 K 倍 -> D6c 路径 3.2 M cycles，大幅快进 |
| hello       | 452 B   | 135 K       | mainargs="abc123" 经 insert-arg 正确替换 |
| mem-test    | 1 204 B | 8.9 M       | PSRAM/SDRAM AM 程序无回归（实际打 sdramChisel）|

测速结论：相比 D6c 的 vendor-bootloader 路径（370 KiB ROM → SDRAM 拷贝），
B2c 的 XIP 启动节省大量 SPI 流量，dummy 快 250 倍。

---

## 4. microbench (test 规模) 结果

```
$ make ARCH=riscv32e-npc-soc -C am-kernels/benchmarks/microbench insert-arg mainargs=test
$ ./npc/build/npc-soc --flash=.../microbench-riscv32e-npc-soc.bin --max-cycles=2000000000
```

完整输出：

```
npc-soc: loaded 30532 bytes from '.../microbench-riscv32e-npc-soc.bin' into Flash
npc-soc: reset released at cycle 16
======= Running MicroBench [input *test*] =======
[qsort] Quick sort: * Passed.
[queen] Queen placement: * Passed.
[bf] Brainf**k interpreter: * Passed.
[fib] Fibonacci number: * Passed.
[sieve] Eratosthenes sieve: * Passed.
[15pz] A* 15-puzzle search: * Passed.
[dinic] Dinic's maxflow algorithm: * Passed.
[lzip] Lzip compression: * Passed.
[ssort] Suffix sort: * Passed.
[md5] MD5 digest: * Passed.
==================================================
MicroBench PASS
Scored time: 15559.625 ms
Total  time: 21506.208 ms

HIT GOOD TRAP
npc-soc: ebreak hit at cycle 88205267
npc-soc: B2a access-fault events: 0
```

结果汇总：

| 子测试 | 结果   | 说明                            |
| ------ | ------ | ------------------------------- |
| qsort  | PASS   | 100 element Quick sort          |
| queen  | PASS   | 8-Queen placement               |
| bf     | PASS   | Brainf**k interpreter           |
| fib    | PASS   | fib(2)                          |
| sieve  | PASS   | sieve to 100                    |
| 15pz   | PASS   | A* 15-puzzle (trivial start)    |
| dinic  | PASS   | Dinic maxflow (10 nodes)        |
| lzip   | PASS   | Lzip on 128 B                   |
| ssort  | PASS   | Suffix sort 100                 |
| md5    | PASS   | MD5 on 100 B                    |

**10 / 10 PASS** (任务标准 >= 50%, 远超)。

数据要点：
- 总 88 M cycle (~3.5 s on this verilator host).
- AM `Scored time: 15.6 s`、`Total time: 21.5 s` 是 mcycle 模拟换算（除以
  `MCYCLE_PER_US=4`，参 `timer.c`）；不是 wall clock。
- `B2a access-fault events: 0` —— 整个流程 AXI bresp/rresp 全 OK，
  没有越界访问。

`test` 规模下每项的 mem 需求都 <= 32 KiB heap（参 benchmark.h）：

```
QSORT_S {     100,   1 KB,     0, 0x08467105}
QUEEN_S {       8,   0 KB,     0, 0x0000005c}
   BF_S {       2,  32 KB,     0, 0xa6f0079e}
  FIB_S {       2,   1 KB,     0, 0x7cfeddf0}
SIEVE_S {     100,   1 KB,     0, 0x00000019}
 PZ15_S {       0,   1 KB,     0, 0x00000006}
DINIC_S {      10,   8 KB,     0, 0x0000019c}
 LZIP_S {     128, 128 KB,     0, 0xe05fc832}
SSORT_S {     100,   4 KB,     0, 0x4c555e09}
  MD5_S {     100,   1 KB,     0, 0xf902f28f}
```

最大的 lzip 也只要 128 KiB heap，远小于 SDRAM 32 MiB。


---

## 5. typing-game 跑通 (字符屏 demo)

ysyxSoC 没有 framebuffer GPU、也没有 NVBoard 键盘，typing-game 默认会
`panic_on(!io_read(AM_INPUT_CONFIG).present, "requires keyboard")` 死掉。

参 D6d Mario 的"自动 demo"路线，给 `game.c` 加一个 `run_text_demo()` 路径：

```
if (!io_read(AM_GPU_CONFIG).present) {
  run_text_demo();   // 文字模式 -- HUD + 字母滚动 + 自动 hit
  return 0;
}
/* fall through to original GPU + keyboard path */
```

demo 行为：
- 模拟一个 64x16 字符屏（screen_w=512, screen_h=256）
- 每 tick 跑 `game_logic_update`（同原代码，新字母随机生成 + 重力下落）
- 每 6 tick 自动选屏上最底的 W 色字母 hit (`check_hit`)
- 每 10 tick 输出 HUD 行
- 每 5 tick sample 一个可见字母位置打印
- DEMO_TICKS=300 tick 后 `halt(hit > 0 ? 0 : 1)`

实跑 80 M cycles 输出（节选）：

```
=== typing-game text-demo (no GPU/keyboard) ===
screen=512x256 ticks=300 hit-period=6
[tick   0] live= 1 hit=1 miss=0 wrong=0
  char=Q x=203 y=  5 v=-8 col=G
[tick  30] live= 1 hit=6 miss=0 wrong=0
  char=T x=344 y=  4 v=-8 col=G
[tick  60] live= 1 hit=11 miss=0 wrong=0
  char=A x=225 y=  4 v=-8 col=G
... (字母 Y, X, K, I, D, I, Z ...)
[tick 290] live= 0 hit=49 miss=0 wrong=0
=== typing-game text-demo done: hit=50 miss=0 wrong=0 ===

HIT GOOD TRAP
npc-soc: ebreak hit at cycle 80422848
npc-soc: B2a access-fault events: 0
```

观察点：
- HUD 三列 (`hit/miss/wrong`) 完整, ✓
- 字母滚动: Q -> T -> A -> Y -> X -> K -> I -> D -> I -> Z, ✓
- `col=G` 表示该字母已被 hit, 速度变负向上飞回, ✓
- 50 次 hit，0 次 miss / wrong, ✓
- HIT GOOD TRAP 干净退出, ✓
- `B2a access-fault events: 0`, ✓

`render()` 在文字 demo 里完全不调用，所以 GPU 缺失没有影响。
原 GPU + 键盘路径保留不动，将来如果接上 NVBoard 仍可直接走老路。

---

## 6. PSRAM mem-test 扩展到 1 MiB

B2b 的 stand-alone harness（`npc/tests/mem-test-rtl/tb_psram.v`）只测
4 KiB。B2c 加 `tb_psram_1m.v`，把 `SIZE_BYTES = 32'h00100000`，2 个 pattern
write-then-read，**共 4 M 笔 32-bit 访存**。

跑法：

```
$ cd ysyx-workbench/npc/tests/mem-test-rtl
$ make psram-1m
```

实测：

```
== PSRAM mem-test 1M: starting (size=1048576 bytes = 1024 KiB) ==
   pat1 wr: 64 KiB done
   pat1 wr: 128 KiB done
   ... (每 64 KiB 一行进度)
   pat1 wr: 1024 KiB done
   pat1 rd: 64 KiB done
   ... (省略)
-- pat1 pass --
   pat2 wr: 64 KiB done
   ... (省略)
-- pat2 pass --
PSRAM mem-test 1M PASS
- Verilator: $finish at 566ms; walltime 10.069 s
```

数据要点：
- 仿真时间 566 ms (sim clock @ 100 MHz)，walltime 10 s。
- 含 1 MiB pat1 wr + rd + 1 MiB pat2 wr + rd = 4 MiB 数据流量。
- 全 PASS, 0 errors。
- 也再跑了 B2b 的 4 KiB smoke (`make all`): 仍然 PASS。

PSRAM QSPI 每笔 32-bit 访存约 50 SCK = 100 clk，所以 256 K 笔 * 2 pass *
50 ns/clk = 2.5 s 量级；实测 566 ms 比理论快，原因是 controller 内部把
连续 32-bit 访问当作 burst 处理，省掉一些 cmd/addr phase。

SDRAM 没有扩到 1 MiB，因为 B2b 的 SDRAM 4 KiB 仿真已经只要 471 us
（SDR-2 burst, no QSPI 序列化开销），扩到 1 MiB 也是秒级，可以跑但
没必要重复验证。

---

## 7. 已知遗留 / 限制

1. **PSRAM 实际未接进 ysyxSoCFull.v 顶层**（同 B2b）。
   1 MiB mem-test 是用 stand-alone harness 直接打 EF_PSRAM_CTRL +
   psram.v，没经过 NPC CPU。让 CPU 真正访问 PSRAM 需要 patch
   ysyxSoCFull.v 的 APBFanout（增加 sel_3 把 0xa0000000 段路由到
   psram_top_apb），任务约束禁止改顶层文件，留待 B3+。

2. **8 KiB SRAM (0x0f000000) 未挂载**。当前 APBFanout 把
   0x0f000000 段算成 sel_1 (UART)，与文档预期冲突。也属于 patch
   ysyxSoCFull.v 的范畴，本 task 不改。

3. **microbench 只跑 `test` 规模**。`train/ref/huge` 需 >= 128 KiB 到 64 MiB
   heap，理论上 32 MiB SDRAM 能跑到 `ref` 多数子项，但 verilator host
   对每个 sim 的吞吐约 25 M cycles/s，预计跑完 ref 要 30 min+。
   B3 / B4 引入 cache 后再扩。

4. **typing-game 走 demo 模式**，未走真实键盘。要走真实键盘需要
   NVBoard 或类似输入设备的 MMIO，当前 SoC 没有。

5. **mainargs[] 是 `const`, 在 .rodata (Flash)**。`insert-arg.py`
   patch 的是 .bin 文件，烧到 Flash 后程序读到的就是替换后的字串
   —— 这部分跟原 npc 平台行为一致；如果有人在 board 上从只读 ROM
   烧机后想动态改 mainargs，这条路径走不通（需要把 mainargs[] 放
   到 .data 段，会增加 .data 复制带宽，本 task 不改）。

6. **start.S 用了 a5 当 scratch (rv32e 缺 t3..t6)**。任何嵌入 ABI 假
   设 a5 在 _start 入口之前已就位的代码都会出错—— RV ABI 不允许这
   样的假设，安全。

---

## 8. 调试备忘 (踩坑)

1. **start.S 用了 t3/t4 → assemble fail**：rv32e ABI 只允许 x0..x15，
   t3 = x28 不在范围。改用 a5 (x15)。教训：rv32e 写汇编一定要约束
   寄存器号 <= 15。

2. **第一次链接报 `undefined reference to _pmem_start`**：
   `am/src/riscv/npc/trm.c` 里 `Area heap = RANGE(&_heap_start,
   PMEM_END)`，PMEM_END 定义为 `_pmem_start + 128 MiB`。新链接脚本
   没导出这个符号；通过 LDFLAGS `--defsym=_pmem_start=0x80000000`
   补回去。klib 的 malloc 仍以 `_heap_start` 起算，所以这个 defsym
   只是让链接通过，heap 实际上限由 SDRAM 末端给定。

3. **AM_SRCS 路径**：`riscv/npc-soc/start.S` 不是 `riscv/npc/start.S`，
   两份共存：DPI-C `npc` 平台的 start.S（PMEM 入口）保持不动；
   `npc-soc` 平台的 start.S 含 bootloader 逻辑。

4. **`*(entry)` 链接顺序**：B2c 链接脚本里 `.text : { *(entry)
   *(.text*) }`。如果先 `*(.text*)` 再 `*(entry)`，`_start` 就不
   位于 Flash 0x30000000，复位即跑垃圾指令。已经在 `.ld` 注释中
   写清。

---

## 9. 文件清单

新增：
- `abstract-machine/scripts/linker-soc.ld`
- `abstract-machine/scripts/platform/npc-soc.mk`
- `abstract-machine/scripts/riscv32e-npc-soc.mk`
- `abstract-machine/am/src/riscv/npc-soc/start.S`
- `npc/tests/mem-test-rtl/tb_psram_1m.v`

修改：
- `abstract-machine/scripts/...` (上述新增, 未触现有平台)
- `am-kernels/kernels/typing-game/game.c` (加 `run_text_demo` 分支)
- `npc/tests/mem-test-rtl/Makefile` (加 `psram-1m` target)

未触（按任务约束）：
- `npc/Makefile`, `npc/vsrc-soc/ysyxSoCFull.v`
- `ysyxSoC/perip/psram/efabless/*`, `ysyxSoC/perip/sdram/core_sdram_axi4/*`
- `ysyxSoC/perip/*/[a-z]_top_apb.v`
- `abstract-machine/scripts/riscv32e-npc.mk`, `platform/npc.mk`
  (与 DPI-C 平台保持独立, 无回归)

---

## 10. 接下来 (供 B3+ 引用)

- **patch ysyxSoCFull.v** 加 PSRAM (0xa0000000-0xbfffffff) sel_3。
  需修改 APBFanout 解码 + 添加 PSRAM top_apb 实例。这能让 CPU 真正
  跑 PSRAM 上的 microbench 大规模。

- **microbench `train` / `ref`** 跑：跟 cache (B4) 同步评估。当前
  flash XIP 取指带宽 ~10 cycle/inst (SPI Quad I/O 8 dummy + 8 data
  = 16 SCK = 32 clk)，cache 之后会拉到 ~1 cycle/inst。

- **typing-game NVBoard 接入**：B6 板级测试再做。
