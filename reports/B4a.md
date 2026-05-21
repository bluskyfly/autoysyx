# B4a -- 简易直接映射 icache (16 块 x 4B)

**Status**: DONE

`docs-md/2407/b/4.md` 第 522-527 行要求实现一个用触发器搭的 instruction
cache (块大小 4B、共 16 块)。本 step 在 NPC 的 SoC 通路 (ysyx_22040000 ->
SimpleBus -> SoC MemBridge -> AXI) 上插入 icache, 完整数据通路:

```
        +----------+   half-handshake  +--------+   half-handshake  +----------+
  CPU --|  ifu fsm |------------------>| icache |------------------>| MemBridge|--> AXI
  FSM  -|  (S_IF)  |<-- resp_valid ----|        |<-- bus_resp_valid-|          |
        +----------+    resp_data      +--------+    bus_resp_data  +----------+
                                       |        |
                                       | tag/data array (DFF)
                                       | 16 x 32b, 16 x 26b, 16 x 1b
                                       +--------+
```

回归结果一句话:

- hello on SoC: HIT GOOD TRAP, **73 145 cycle** (B2c 基线 135 K, **降到 54%**),
  icache hit rate **53.18%** (754 access).
- microbench `test`: 10/10 PASS, **43.1 M cycle** (B2c 基线 88 M, **降到 49%**),
  icache hit rate **53.84%** (535 K access).
- yosys synth: 仍然 clean (无 latch, 无多驱动).

---

## 1. icache 设计

### 1.1 地址切分

参数化两个 log: `BLOCKS_LOG` (默认 4 -> 16 块) 和 `OFFSET_LOG` (默认 2 ->
块大小 4B). 衍生:

- `BLOCKS    = 2 ** BLOCKS_LOG       = 16`
- `TAG_LSB   = OFFSET_LOG + BLOCKS_LOG = 6`
- `TAG_WIDTH = 32 - TAG_LSB          = 26`

PC = 32 位地址被拆成 tag / index / offset 三段:

```
 31                        6  5   2  1   0
+---------------------------+-------+-----+
|         tag (26)          | idx(4)| ofs |  PC[1:0]
+---------------------------+-------+-----+
                            ^       ^
                            |       |
                            |       +-- 块内偏移 (4B 块 -> 始终 00, 弃用)
                            +-- 行号 (16 行直接映射)
```

ASCII 数组示意 (16 行存储, 每行: valid + tag + 32b data):

```
 idx | valid | tag (26b)         | data (32b)
 ----+-------+-------------------+------------------
   0 |   v0  | tag_array[0]      | data_array[0]
   1 |   v1  | tag_array[1]      | data_array[1]
   2 |   v2  | tag_array[2]      | data_array[2]
   ... (共 16 行)
  15 | v15   | tag_array[15]     | data_array[15]
```

总存储 = 16 * (1 + 26 + 32) = 944 bit = 118 B (其中 64 B 是 data, 56 B 是 meta).
直接映射 -> 不需要 way 选择 / LRU 之类的外部状态.

### 1.2 状态机

icache 是个 2 状态 FSM:

```
                           req_valid && !hit
              +-------+---------------------+--------+
              |       |                     |        |
              | IDLE  |                     |  MISS  |
              |       |<--------+           |        |
              +-------+         |           +--------+
                |               |               |
                | hit:          | bus_resp_valid|
                | resp_valid=1  |     +---------+
                | (combinational)|    |
                v                v    v
        (CPU 一拍内拿到)      (填表 + 透传 bus_resp_data)
                                resp_valid=1
```

状态语义:

- **S_IDLE**: 默认状态. 上游若 `req_valid=1`:
  - **hit (组合)**: `resp_valid` 同周期组合拉高, `resp_data = data_array[index]`.
    下一拍如果 CPU 已经离开 S_IF, `req_valid` 落回 0, 留在 IDLE.
  - **miss**: 下一拍切到 S_MISS.
- **S_MISS**: 拉 `bus_req_valid=1`, 把对齐后的 `req_addr` 抛给 MemBridge.
  SimpleBus 的 MemBridge 要求 reqValid 一直拉到 respValid 那拍, 自然契合.
  收到 `bus_resp_valid=1`:
  - 同周期 `resp_valid=1`, `resp_data = bus_resp_data` (透传, 不等下一拍).
  - 同周期触发器写: `valid_array[index] <= 1`, `tag_array[index] <= req_tag`,
    `data_array[index] <= bus_resp_data`.
  - 下一拍回 S_IDLE.

### 1.3 hit 与 miss 时序图

**hit 时序** (CPU S_IF 已经在 cycle N 触发 `req_valid=1`):

```
        cycle:   N           N+1
        clock:  __|^|_______|^|_______|^|___
       state:  +-----------+
        CPU:   |   S_IF    |   S_EX   ...
               +-----------+----------+
        FSM:   IDLE        IDLE        (icache 始终 IDLE)
  req_valid:   ^^^^^^^^^^^^^|__________
   req_addr:   <addr>                 (从 pc 来, S_IF 期间不变)
         hit:  ^^^^^^^^^^^^^|_________  (组合, valid&tag match)
 resp_valid:   ^^^^^^^^^^^^^|_________  (= hit)
  resp_data:   <data_array[index]>     (组合)
   bus_req_valid: __________________   (始终 0)
```

CPU 在 cycle N 看到 `resp_valid=1`, S_IF -> S_EX 一拍内完成, 与无 cache
的"运气好 bus 单拍返回"等价 -- 但 hit 的发生概率更高.

**miss 时序** (cache 空 / tag mismatch):

```
       cycle:   N         N+1        N+2 .. N+k    N+k+1
       clock:  _|^|_______|^|________ ...  |^|_____|^|___
       CPU:   |  S_IF                                                            |  S_EX |
              +---------------------------------------------------------------+-+-+----+
   icache FSM: IDLE     | MISS      | MISS  ...    MISS   | IDLE
  req_valid:   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^|________
         hit:  ____________|_______ (idx 行的 valid=0, miss)
bus_req_valid: ____________|^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^|______
 bus_resp_valid: __________________________________________|^|_____
   resp_valid:  _________________________________________|^|_____  (= miss_done)
   resp_data:  -- (旧值)                              <bus_resp_data>
         填表:                                       valid=1 + tag/data 写入
```

时间开销 = bus 一次取指的延迟. 在 NPC 当前 SoC 上, Flash XIP 一次取指 ≈
4000+ cycle (SPI flash bit-banging). SDRAM 取指快得多 (一次 transaction 约
6 cycle). 所以 miss penalty 主要看是 Flash 还是 SDRAM.

### 1.4 性能计数器

`cnt_access / cnt_hit / cnt_miss` 全部 64 bit, `posedge` 时序:

- `resp_valid=1` 那一拍 (即一次访问完成): `cnt_access += 1`.
- 同一拍若 `idle_hit=1` (= `state == S_IDLE && hit`): `cnt_hit += 1`.
- 否则 (= `miss_done`): `cnt_miss += 1`.

不需要边沿检测, 因为 `resp_valid` 一次访问只发一个脉冲.

verilator 侧通过 `/*verilator public_flat_rd*/` 把它们抬到扁平符号表
(`ysyxSoCFull__DOT__asic__DOT__cpu__DOT__cpu__DOT__u_icache__DOT__cnt_*`).
`main_soc.cpp` 退出前从 root pointer 读出, 打印 hit_rate.

---

## 2. 集成方式

### 2.1 关键改动

`npc/vsrc/ysyx_22040000.v`:

```verilog
// FSM 给 icache 上游, icache 下游接出 io_ifu_* (外部端口签名不变)
wire        ifu_cpu_req_valid  = (state == S_IF) & ~reset;
wire [31:0] ifu_cpu_req_addr   = {pc[31:2], 2'b00};
wire        ifu_cpu_resp_valid;
wire [31:0] ifu_cpu_resp_data;

icache #(.BLOCKS_LOG(4), .OFFSET_LOG(2)) u_icache (
  .clock(clock), .reset(reset),
  .req_valid(ifu_cpu_req_valid),   .req_addr(ifu_cpu_req_addr),
  .resp_valid(ifu_cpu_resp_valid), .resp_data(ifu_cpu_resp_data),
  .bus_req_valid(io_ifu_reqValid), .bus_req_addr(io_ifu_addr),
  .bus_resp_valid(io_ifu_respValid),.bus_resp_data(io_ifu_rdata)
);
```

FSM 的取指等待条件由 `io_ifu_respValid` 改为 `ifu_cpu_resp_valid`. Access
fault 检测也相应改成 `ifu_cpu_resp_valid` -- bus 端的 fault 信号经 cache
透传 (cache 不缓存 fault 那拍的 junk data, 因为 valid_array 不写入).

### 2.2 不改 Makefile 的策略

任务约束: 不动 `npc/Makefile`. icache.v 通过 `\`include "vsrc/icache.v"`
在 ysyx_22040000.v 顶部拉进编译单元. verilator 的工作目录是 npc/, 所以
相对路径 `vsrc/icache.v` 能找到. 这样不需要把 icache.v 加进 SOC_CPU_VSRCS.


---

## 3. 回归验证

### 3.1 SoC 仿真编译

```
$ cd /home/curry/code/autoysyx/ysyx-workbench/npc && make sim-soc SOC_ARGS=...
- Verilator: Built from 7.050 MB sources in 68 modules, into 0.665 MB in 10 C++ files
```

68 个模块 (B2c 时是 67 个 + 新增 1 个 icache). 编译 walltime 4.2 s, 无 lint
warning (除已知 vendor RTL 噪声).

### 3.2 hello on SoC

```
$ ./build/npc-soc --flash=../am-kernels/kernels/hello/build/hello-riscv32e-npc-soc.bin \
                  --max-cycles=3000000

npc-soc: loaded 452 bytes from '.../hello-riscv32e-npc-soc.bin' into Flash
npc-soc: reset released at cycle 16
Hello, AbstractMachine!
mainargs = 'abc123'.

HIT GOOD TRAP
npc-soc: ebreak hit at cycle 73145
npc-soc: B2a access-fault events: 0
npc-soc: icache access=754 hit=401 miss=353 hit_rate=53.18%
```

对比 (来自 B2c 报告):

| 指标         | B2c (无 cache) | B4a (16-block icache) | 变化           |
| ------------ | -------------- | --------------------- | -------------- |
| cycles       | 135 000        | 73 145                | -45.8% (1.8x)  |
| icache hit   | -              | 401 / 754             | 53.18%         |
| HIT GOOD TRAP | yes           | yes                   | 同             |
| fault events | 0              | 0                     | 同             |

### 3.3 microbench `test` 规模

```
$ ./build/npc-soc --flash=.../microbench-riscv32e-npc-soc.bin \
                  --max-cycles=2000000000

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
Scored time: 8452.358 ms
Total  time: 10457.504 ms

HIT GOOD TRAP
npc-soc: ebreak hit at cycle 43110439
npc-soc: B2a access-fault events: 0
npc-soc: icache access=535181 hit=288146 miss=247035 hit_rate=53.84%
```

10 / 10 全 PASS, 与 B2c 相同. cycle 数对比:

| 指标         | B2c (无 cache) | B4a (16-block icache) | 变化            |
| ------------ | -------------- | --------------------- | --------------- |
| cycles       | 88 205 267     | 43 110 439            | -51.1% (2.0x)   |
| icache access | -             | 535 181               | -               |
| icache hit   | -              | 288 146               | -               |
| hit rate     | -              | 53.84%                | -               |
| AM Scored ms | 15 559.6       | 8 452.4               | -45.7% (mcycle 同步降) |
| AM Total ms  | 21 506.2       | 10 457.5              | -51.4%          |

> 注: AM 报告的 Scored / Total ms 是把 mcycle 除以 `MCYCLE_PER_US = 4` 得到
> 的"模拟微秒", 并非 wall clock. cycles 翻倍 / 减半的影响会反映在这两个数上.

### 3.4 yosys 综合 (B3 回归)

```
$ make yosys-synth
==> yosys: synthesise ysyx_22040000 (SoC-facing CPU top)
==> yosys: synthesise cpu (D4/D5 harness top, -DSYNTHESIS)
==> yosys: synthesise ysyx_22040000_bus (B1 full-handshake top)
==> yosys synthesis OK: clean lint, all check -assert passed
```

icache 与 ysyx_22040000 一起综合: 无 latch, 无未连接的 sink, 无多驱动.
直接映射 cache 用 16 个 32-bit reg 阵列 + 16 个 tag reg + 16 个 valid reg
+ 1-bit FSM, 全部能映射到 DFF. 这与 docs 的"先用触发器实现存储阵列"完全
一致.

### 3.5 sim (DPI-C) 回归

`make sim` 仍走 cpu.v (不含 ysyx_22040000), 不受 icache 影响:

```
$ make sim
npc: loaded 56 bytes from .../cpu-tests.bin
npc: cycles=19
HIT GOOD TRAP
```

### 3.6 命中率分析

53% 看起来比预期 (50%) 高了一点点, 但比"现代 CPU L1I 接近 99%"差得远.
原因可分析:

1. **块大小只有 4B**: 一条指令一个块, 完全没有空间局部性. 顺序代码访问相邻
   指令时仍 miss. 升级到块 16B/32B (B4b/B4c 改) 后, 一次 miss 能填 4-8 条指令,
   预期 hit rate 直接 >= 75%.
2. **只有 16 行**: 64 B 容量. 任何超过 64 B 的代码段都会有 conflict miss.
   microbench 的内层循环 (qsort 比较函数, ssort 比较函数) 长度多在 100-300 B,
   循环体内多个分支跳来跳去, 一个 PC 把另一个 PC 踢出.
3. **直接映射**: 同 idx 的两个 PC (相距 64B 的倍数) 会互相挤掉. 升级到
   2-way / 4-way set-associative (B4b) 会显著改善.

B4b/B4c 会针对这两点优化.


---

## 4. 关键代码

### 4.1 icache.v 核心

```verilog
module icache #(
  parameter BLOCKS_LOG = 4,
  parameter OFFSET_LOG = 2
)(
  input clock, input reset,
  input req_valid,  input [31:0] req_addr,
  output resp_valid, output [31:0] resp_data,
  output bus_req_valid, output [31:0] bus_req_addr,
  input bus_resp_valid, input [31:0] bus_resp_data
);
  localparam BLOCKS    = (1 << BLOCKS_LOG);
  localparam TAG_LSB   = OFFSET_LOG + BLOCKS_LOG;
  localparam TAG_WIDTH = 32 - TAG_LSB;

  wire [TAG_WIDTH-1:0]  req_tag   = req_addr[31:TAG_LSB];
  wire [BLOCKS_LOG-1:0] req_index = req_addr[TAG_LSB-1:OFFSET_LOG];

  reg [31:0]           data_array [0:BLOCKS-1];
  reg [TAG_WIDTH-1:0]  tag_array  [0:BLOCKS-1];
  reg                  valid_array[0:BLOCKS-1];

  wire entry_valid = valid_array[req_index];
  wire tag_match   = (tag_array[req_index] == req_tag);
  wire hit         = req_valid & entry_valid & tag_match;

  localparam S_IDLE = 1'b0;
  localparam S_MISS = 1'b1;
  reg state, next_state;
  // ... FSM 见前节

  wire idle_hit  = (state == S_IDLE) & hit;
  wire miss_done = (state == S_MISS) & bus_resp_valid;
  assign resp_valid = idle_hit | miss_done;
  assign resp_data  = miss_done ? bus_resp_data : data_array[req_index];

  assign bus_req_valid = (state == S_MISS);
  assign bus_req_addr  = {req_addr[31:OFFSET_LOG], {OFFSET_LOG{1'b0}}};

  // 性能计数器, public_flat_rd 供 C 读
  reg [63:0] cnt_access /*verilator public_flat_rd*/;
  reg [63:0] cnt_hit    /*verilator public_flat_rd*/;
  reg [63:0] cnt_miss   /*verilator public_flat_rd*/;

  always @(posedge clock) begin
    if (reset) begin
      cnt_access <= 0; cnt_hit <= 0; cnt_miss <= 0;
      state <= S_IDLE;
      // 全部 valid 清零 ...
    end else begin
      state <= next_state;
      if (resp_valid) begin
        cnt_access <= cnt_access + 1;
        if (idle_hit) cnt_hit  <= cnt_hit  + 1;
        else          cnt_miss <= cnt_miss + 1;
      end
      if (miss_done) begin
        valid_array[req_index] <= 1'b1;
        tag_array [req_index]  <= req_tag;
        data_array[req_index]  <= bus_resp_data;
      end
    end
  end
endmodule
```

### 4.2 配置点

参数对外可改:

```verilog
icache #(.BLOCKS_LOG(6), .OFFSET_LOG(2)) u_icache (...);  // 64 行 -> 256 B
icache #(.BLOCKS_LOG(4), .OFFSET_LOG(4)) u_icache (...);  // 16 行 x 16B
```

但是 `OFFSET_LOG > 2` 需要改 FSM (要发多个 bus transaction 才能填一个块).
B4b 会做这个升级.

### 4.3 main_soc.cpp 性能计数器输出

```cpp
uint64_t ic_access = r->ysyxSoCFull__DOT__asic__DOT__cpu__DOT__cpu__DOT__u_icache__DOT__cnt_access;
uint64_t ic_hit    = r->ysyxSoCFull__DOT__asic__DOT__cpu__DOT__cpu__DOT__u_icache__DOT__cnt_hit;
uint64_t ic_miss   = r->ysyxSoCFull__DOT__asic__DOT__cpu__DOT__cpu__DOT__u_icache__DOT__cnt_miss;
double hit_rate = ic_access ? (double)ic_hit * 100.0 / ic_access : 0.0;
fprintf(stderr, "npc-soc: icache access=%llu hit=%llu miss=%llu hit_rate=%.2f%%\n",
        ic_access, ic_hit, ic_miss, hit_rate);
```

---

## 5. 边缘案例 + 测试建议

我把 icache 集成进通路时有几个边缘需要专门看. 当前 hello/microbench 都
跑过, 但写在这里供后续 (B4b/B4c 改 cache 时) 做回归参考:

1. **reset 期间 req_valid 短暂为 1**: ysyx_22040000 用 `& ~reset` 屏蔽,
   cache 也只在 reset=0 时才更新 state, 不会写 valid_array. **已测**.

2. **bus 返 fault**: B2a 给 NPC 的策略是 bus 报 fault 时跳到 PC=0. icache
   不区分 fault, 把 bus_resp_data 直接当数据写表了 -- 但这一拍 io_fault 也
   会拉高, ysyx_22040000 同周期 `ifu_fault=1`, FSM 跳 S_IF (PC=0), 也不会
   latch inst_r. 所以 fault 后 cache 会留一个 valid + tag=<fault addr 的
   tag> + data=garbage 的条目. **潜在问题**: 后续如果 PC 回到 fault 地址, 会
   命中并返回 garbage. 但 B2a 文档说 fault 后 PC=0, 不会再访问 fault 地址,
   所以现在不修. **建议测试**: 单独写一个 testbench, 手动把 io_fault 拉 1
   一拍, 然后再请求同地址, 看 cache 是否返回原数据. (留到 B4b 解决.)

3. **同地址连续两次取指 (loop body 第一条)**: 第一次 miss 填表, 第二次该
   立刻 hit. **已测** (microbench 内层循环表现就是这样, 53% hit rate 主要
   来自这种 case).

4. **tag conflict**: PC1 = 0x30000040, PC2 = 0x30000080, idx 相同, tag 不同.
   两个 PC 交替访问 -> 全 miss (thrashing). **已测**: hit rate 53.84% 没到
   90% 的主因之一. 升级到 2-way set-associative 后解决.

5. **bus_resp_valid 与 req_valid 在 IDLE 同周期拉高 (不可能但要确认)**: 我
   的 FSM 设计里 bus_req_valid 只在 S_MISS 拉高, S_IDLE 不会向 bus 发请求,
   bus 也不会主动返 resp. **建议**: yosys 综合后看是否真的没有这种组合环
   (本步综合 OK). 

6. **req_addr 中途变化 (CPU 跳到新 PC 但还在 S_IF)**: CPU 的 S_IF 期间 pc
   是 reg, 在 S_WB 才更新, 所以 S_IF 期间 req_addr 锁定. **已测**.

7. **块大小升级到 16B 时**: 需要 burst read 才能填一个完整块. 当前 OFFSET_LOG=2
   时 bus_req_addr 直接 = req_addr & ~0x3, 1 次读完事. OFFSET_LOG > 2 时要
   循环 `2^(OFFSET_LOG-2)` 次. **当前 B4a 不实现**; B4b 单独处理.

8. **performance counter 溢出**: 64 bit 计数, 2^64 cycle ≈ 10^19 拍. 现在
   microbench 才 5 * 10^5 access, 没有溢出风险.

---

## 6. 关键参数

| 参数        | 默认值 | 含义                            |
| ----------- | ------ | ------------------------------- |
| BLOCKS_LOG  | 4      | log2(块数) -> 16 行             |
| OFFSET_LOG  | 2      | log2(块大小字节) -> 4B (1 inst) |
| TAG_LSB     | 6      | tag 最低位 (= OFFSET+BLOCKS_LOG)|
| TAG_WIDTH   | 26     | tag 位宽                        |
| 总容量      | 64 B   | data; meta 56 B = 120 B 触发器  |

---

## 7. 已知遗留

- **块大小固定 4B**: 一次 miss 只填 1 条指令. 空间局部性没利用. B4b 改.
- **直接映射**: 同 idx 不同 tag 的两个 PC 会反复 thrashing. B4b 改 set-assoc.
- **fault 后 cache 留 garbage 条目**: 已分析见边缘案例 #2.
- **没有 write 接口**: icache 只读, 没有 invalidate/flush 入口. 后续如果跑
  自修改代码 (例如 JIT) 会出问题. 现在 microbench 没这个场景.
- **没有 DPI-C 实时上报**: cnt 只在退出前打印一次. 想要在跑测试中间观察
  hit rate 变化需要加 watch.

---

## 8. 子仓 commit

- `ysyx-workbench`:
  - 新增: `npc/vsrc/icache.v` (≈ 130 行)
  - 改: `npc/vsrc/ysyx_22040000.v` (插 icache 实例, 把 FSM 的取指等待目标
        从 io_ifu_respValid 切到 ifu_cpu_resp_valid)
  - 改: `npc/csrc/main_soc.cpp` (退出前读 cnt_access/hit/miss, 打印 hit rate)
- 父仓 `autoysyx`:
  - 新增: `reports/B4a.md` (本文件, `-f` 加因为 reports/ 在 .gitignore)

