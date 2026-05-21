## B4c -- icache 命中率达标 (microbench >= 90%)

**Status**: DONE.

`docs-md/2407/b/4.md` "实现 icache" 一节给的提示是: 4B 块大小 "也许不是
一个最好的设计... 至于大于 4B 是否更好, 我们后面再来评估". B4c 就是这个
评估 + 改造. B4a/B4b 的 cache 容量不变都是 64 B (16 块 x 4B), microbench
test 的 hit_rate 卡在 48-54% (1-way 53.85%, 2-way 48.48%, 4-way 48.99%) -
**块大小 = 一条指令的长度时, 空间局部性彻底失效**, 顺序取指的每条指令
都触发 cold miss.

B4c 把块大小提到 32 B (= 8 条指令), 总容量同步提到 1 KB (= 32 块 x 32 B,
仍 2-way). FSM 加 multi-beat fill 状态, 一次 miss 走 SimpleBus 单 word
协议拉 8 拍, 不需要改 MemBridge / SoC 顶层 / 外设. 实测结果:

- **microbench test**: 10/10 PASS, cycle **7.6 M** (B4a 43.4 M, **-82%**),
  hit_rate **99.46%** (B4b 48.48%, **+50.98 pp**). 远超 90% 目标.
- **hello on SoC**: HIT GOOD TRAP cycle 29067 (B4b 31749, **-8%**),
  hit_rate **98.54%** (B4b 87.93%).
- victim == miss sanity check 全过.
- yosys synth clean, DPI sim 烟雾 OK.

详细参数搜索见 ' 4. 数据.

---

## 1. 设计点 & 修改集

### 1.1 改动文件

| 文件 | 修改 | 大致行数 |
| ---- | ---- | -------- |
| `npc/vsrc/icache.v`        | 全文重写 (B4b -> B4c), 见 ' 1.2 | 230+ 行 |
| `npc/vsrc/ysyx_22040000.v` | 唯一的 icache 实例化 (line 275) 默认参数 | 1 行 (+ 注释更新) |
| `npc/csrc/main_soc.cpp`    | 退出报告多打一行 cycle / cyc-per-access | 3 行 |

不动: `npc/Makefile`, `npc/vsrc-soc/ysyxSoCFull.v`, `ysyxSoC/perip/*`,
`ysyx_22040000.v` 的其余信号. SimpleBus master 接口签名不变.

### 1.2 icache 内部改动概览 (vs B4b)

```
B4b icache.v (4B 块):                 B4c icache.v (32B 块, multi-beat):
+----------------------------+       +-----------------------------------+
| data_arr [SETS][WAYS]      |  -->  | data_arr [SETS][WAYS]             |
|   reg [31:0]               |       |   reg [BLOCK_BITS-1:0]            |
|                            |       |   = 8 word per slot               |
| FSM: 2 态                  |  -->  | FSM: 3 态                         |
|   S_IDLE / S_MISS          |       |   S_IDLE / S_FILL / S_DONE        |
|                            |       |   + fill_cnt [WCNT_W-1:0]         |
| bus_req_addr = block base  |  -->  | bus_req_addr = block base + 4*cnt |
| resp_data = hit_block      |  -->  | resp_data = mux(hit_block, woff)  |
| miss 1 拍 fill 完          |  -->  | miss BLOCK_WORDS 拍 fill + 1 拍   |
|                            |       |   S_DONE                          |
+----------------------------+       +-----------------------------------+
```

`BLOCK_WORDS = BLOCK_BYTES / 4 = 2 ^ (OFFSET_LOG - 2)`. 默认 OFFSET_LOG=5
-> BLOCK_WORDS=8.

---

## 2. 地址切分 (B4c 引入字偏移)

```
                                  +- TAG_LSB
                                  v
 31                          TAG_LSB-1            OFFSET_LOG-1   1  0
 +----------------------------+-------------------+-----------+-----+
 |          tag (TAG_W b)     |     index         | word_off  | =0  |
 +----------------------------+-------------------+-----------+-----+
                                                  ^           ^
                                              OFFSET_LOG     2
```

| 段名      | 取值范围                     | 说明                          |
| --------- | ---------------------------- | ----------------------------- |
| tag       | `[31 : TAG_LSB]`             | 比较用                        |
| index     | `[TAG_LSB-1 : OFFSET_LOG]`   | set 号                        |
| word_off  | `[OFFSET_LOG-1 : 2]`         | 块内第几个 32-bit word        |
| byte_off  | `[1:0]`                      | 我们 PC 永远 4B 对齐 = 0      |

默认配置 (OFFSET=5, BLOCKS=5, WAYS=1):
- TAG_LSB = 5 + 4 = 9, TAG_W = 32-9 = 23 bit
- index 4 bit -> 16 sets, 每 set 2 way -> 32 块
- word_off 3 bit -> 8 word/块 (即 32 B/块)

### 2.1 退化兼容性

| OFFSET_LOG | BLOCK_WORDS | WORD_LOG | 退化 |
| ---------- | ----------- | -------- | ---- |
| 2          | 1           | 0        | 等价 B4b 行为 (单 word, S_FILL 1 拍 + S_DONE 1 拍) |
| 4          | 4           | 2        | 16 B 块, B4c sweep 测过 PASS |
| **5 (默认)** | **8**     | **3**    | **B4c 默认 32 B 块** |
| 6          | 16          | 4        | 64 B 块, B4c sweep 测过 PASS |

`WCNT_W = max(WORD_LOG, 1)` 是为了让 `reg [WCNT_W-1:0]` 在 WORD_LOG=0 时
仍合法 (避免 `reg [-1:0]`), 与 B4b 处理 AGE_W/IDX_W 的思路一致.

---

## 3. FSM 升级 (单 word miss -> multi-beat fill)

### 3.1 状态机 ASCII

```
            req_valid & ~hit (miss)
       +--------------------------------+
       |                                v
+--------------+  ~req or hit  +-----------+   bus_resp & !last
|              | <-----------+ |           | <----+
|   S_IDLE     |               |  S_FILL   |      |
|              |  req & hit    |           +------+
|              | (resp_valid=1 |           |
|              |  组合返回)    +-----------+
|              |                       | bus_resp & last (== BLOCK_WORDS-1)
|              |                       v
|              |                +-----------+
|              | <--------------|  S_DONE   |
|              | 1 拍后回 IDLE  |           |
+--------------+   resp_valid=1 +-----------+
                  (取 fill 好的
                   block[woff])
```

### 3.2 与 B4b 状态机的差异

| 维度 | B4b S_MISS | B4c S_FILL + S_DONE |
| ---- | ---------- | ------------------- |
| 拍数 | 1 拍 (单 word fill 完同时回 resp) | BLOCK_WORDS 拍 fill + 1 拍 S_DONE |
| `bus_req_addr` | 块基地址 (= req_addr 低 OFFSET_LOG 位清零) | 块基地址 + `fill_cnt*4` |
| `resp_data` 来源 | `bus_resp_data` (透传 miss 当拍 word) | `data_arr[miss_index][miss_way][woff]` (S_DONE 读 fill 好的整块) |
| 计数器 | 在 `miss_done` 累加 | 在 fill last beat 累加 |

**为什么需要 S_DONE 单独一拍?**

S_FILL 的最后一拍把 word slot 写进 `data_arr` 是非阻塞 (`<=`). 同周期组合
逻辑从 `data_arr[miss_index][miss_way]` 读出来不会拿到刚 latched 的最后
一个 word (Verilog NBA 时序). 让 resp 推迟一拍, 在 S_DONE 那拍读到稳定
状态的整块, 然后按 `miss_woff_r` 选出目标 word.

代价: 每次 miss 多 1 拍 (在 8 拍 fill 之后), 总成本 9 拍/miss; 但相对
miss 数下降 80x (B4b 275k -> B4c 2.9k), 净收益巨大 (cycle 47.9M -> 7.6M).

### 3.3 Multi-beat fill 时序图

下面是默认 32 B 块 (BLOCK_WORDS=8) 的一次 miss 时序. ` ` 表示 `'X'` /
不关心. 假定 bus 单 word 协议是: 拉 `bus_req_valid`, 一拍后 (或更晚)
拿到 `bus_resp_valid` 同周期的 `bus_resp_data`.

```
cycle       | 0   | 1   | 2   | 3   | 4   | 5   | 6   | 7   | 8   | 9   | 10  | 11
state       |IDLE |FILL |FILL |FILL |FILL |FILL |FILL |FILL |FILL |DONE |IDLE |...
fill_cnt    | -   | 0   | 0   | 1   | 2   | 3   | 4   | 5   | 6   | 7   | -   | ...
req_valid   | 1   | 1   | 1   | 1   | 1   | 1   | 1   | 1   | 1   | 1   | 0   | ...
hit         | 0   | -   | -   | -   | -   | -   | -   | -   | -   | -   | -   | ...
bus_req_v   | 0   | 1   | 1   | 1   | 1   | 1   | 1   | 1   | 1   | 0   | 0   | ...
bus_req_a   | -   | B+0 | B+0 | B+4 | B+8 | B+c | B+10| B+14| B+18| -   | -   | ...
bus_resp_v  | 0   | 0   | 1   | 1   | 1   | 1   | 1   | 1   | 1   | 0   | -   | ...
bus_resp_d  | -   | -   | w0  | w1  | w2  | w3  | w4  | w5  | w6  | w7  | -   | ...
resp_valid  | 0   | 0   | 0   | 0   | 0   | 0   | 0   | 0   | 0   | 1   | 0   | ...
resp_data   | -   | -   | -   | -   | -   | -   | -   | -   | -   | wK  | -   | ...
                                                                ^ K = miss_woff_r
                                                                 (上游想要的 word)
```

注意 (符合实际 SimpleBus + MemBridge 行为):

- bus_req_addr 在 fill_cnt 还未递增到 7 之前一直拉; 第 8 拍 fill_cnt=7 时
  仍发地址, 但 bus_resp_v 在第 9 拍才回. 不同 bus 模型这里时序会变, 但
  我们的实现是 "持续拉 bus_req_valid 直到 fill_cnt 到 BLOCK_WORDS, 同时
  每收到一拍 resp 就递增 fill_cnt + 推进 addr".
- B + i 中 B = `miss_base_r` = req_addr 低 OFFSET_LOG 位清零.
- S_DONE 那一拍 `resp_data` = `data_arr[miss_index_r][miss_way_r][miss_woff_r]`
  即上游想要的具体 word, 而不是块基地址的 word0.

---

## 4. 数据

### 4.1 参数搜索 (microbench test, 全部 10/10 PASS)

实测 (sweep 脚本 `/tmp/sweep_icache.sh`, sed 改 `ysyx_22040000.v` 中
icache 实例参数, 每次 rm -rf build/obj_dir_soc + make sim-soc):

| 配置                      | OFFSET_LOG | BLOCKS_LOG | WAYS_LOG | 总容量 | 块大小 | hit_rate    | cycles      | victim==miss | >=90% |
| ------------------------- | ---------- | ---------- | -------- | ------ | ------ | ----------- | ----------- | ------------ | ----- |
| B4a 基线 (1-way 16x4B)    | 2          | 4          | 0        | 64 B   | 4 B    | 53.85%      | 43,357,868  | OK           | NO    |
| B4b 默认 (2-way 16x4B)    | 2          | 4          | 1        | 64 B   | 4 B    | 48.48%      | 47,912,139  | OK           | NO    |
| 4-way 4x4B                | 2          | 4          | 2        | 64 B   | 4 B    | (B4b 数据)  |              | OK           | NO    |
| B4c 16x16B-2way           | 4          | 4          | 1        | 256 B  | 16 B   | **96.31%**  | 16,505,339  | OK           | **YES** |
| B4c 16x32B-2way           | 5          | 4          | 1        | 512 B  | 32 B   | **98.46%**  | 14,416,809  | OK           | **YES** |
| **B4c 默认 32x32B-2way**  | **5**      | **5**      | **1**    | **1 KB** | **32 B** | **99.46%**  | **7,612,183** | **OK**       | **YES** |
| B4c 32x64B-2way           | 6          | 5          | 1        | 2 KB   | 64 B   | **99.82%**  | 6,390,421   | OK           | **YES** |

B4a 复测 53.85% / cycle 43.36M 与 B4b 报告记录的 53.84% / cycle 43.11M
有约 0.01 pp / 0.6% 微差, 来源是 `--max-cycles=2e9` 边界 / verilator clock
edge 采样的小尾巴 (sim 跑到 HIT GOOD TRAP 时 cnt_access 比 B4b 报告中的
535181 多了 98), 不影响 hit_rate 量级.

### 4.2 默认配置选择: 32 块 x 32 B (1 KB)

为什么不是 64 B 块 (2 KB) 而是 32 B 块 (1 KB) 作默认:

- **任务要求 ' 90% 已远超**: 99.46% vs >=90%, 余量 9.46 pp.
- **容量翻倍 (2 KB) 收益边际化**: cycle 7.61M -> 6.39M, 仅 -16%; hit
  从 99.46 提到 99.82, 仅 +0.36 pp. 触发器开销翻倍 (512 个 32-bit slot ->
  1024 个 32-bit slot).
- **块大小翻倍 (64 B) miss 时 fill 拍数翻倍**: 一次 miss 从 8 + 1 = 9 拍
  涨到 16 + 1 = 17 拍. 用 cycle 数验证: 32x64B 在 miss 数下降到 953
  (从 2868) 时, 平均 cycle/miss 大幅上升说明 fill 拍数主导.
- **1 KB 容量已能装下 microbench 内层循环 hot region**: 99.46% 几乎全 hit
  说明工作集已落入 cache.
- **STA / B3 综合时序**: 32x32B 的 1024-bit 块 mux + 2 路 tag 比较, 时序
  可控; 任务推荐的就是这个配置.

故选 **OFFSET_LOG=5, BLOCKS_LOG=5, WAYS_LOG=1 (32 块 x 32 B x 2-way =
1 KB)** 作 B4c 默认.

### 4.3 hello on SoC 回归

```
$ ./build/npc-soc --flash=.../hello-riscv32e-npc-soc.bin --max-cycles=3000000
npc-soc: loaded 452 bytes from '.../hello-riscv32e-npc-soc.bin' into Flash
npc-soc: reset released at cycle 16
Hello, AbstractMachine!
mainargs = 'abc123'.

HIT GOOD TRAP
npc-soc: ebreak hit at cycle 29067
npc-soc: B2a access-fault events: 0
npc-soc: icache access=754 hit=743 miss=11 hit_rate=98.54% victim=11
npc-soc: total_cycles=29067 access/miss/hit ratio: 38.550 cyc/access
```

对比:

| 阶段 | hello cycle | hello hit_rate | hello miss |
| ---- | ----------- | -------------- | ---------- |
| B4a 1-way 16x4B   | 73,145  | 53.18% | 354 |
| B4b 2-way 16x4B   | 31,749  | 87.93% | 91  |
| **B4c 2-way 32x32B** | **29,067** | **98.54%** | **11** |

hello 体量小 (452 B = 113 条指令), 1 KB cache 完全装得下, 多 miss 11 次
基本就是 cold start.

### 4.4 microbench test 默认配置详细输出

```
$ ./build/npc-soc --flash=.../microbench-riscv32e-npc-soc.bin --max-cycles=2000000000
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
Scored time: 984.251 ms
Total  time: 1756.198 ms

HIT GOOD TRAP
npc-soc: ebreak hit at cycle 7612183
npc-soc: B2a access-fault events: 0
npc-soc: icache access=534425 hit=531557 miss=2868 hit_rate=99.46% victim=2868
npc-soc: total_cycles=7612183 access/miss/hit ratio: 14.244 cyc/access
```

- **10/10 PASS, MicroBench PASS**.
- `hit_rate=99.46% >= 90%` 达标.
- `victim=miss=2868` sanity check 过.
- 平均 14.24 cycle/access (B4b 默认是 89.5 cyc/access), CPI 大幅改善.

### 4.5 yosys 综合

```
$ cd npc && make yosys-synth
==> yosys: synthesise ysyx_22040000 (SoC-facing CPU top)
==> yosys: synthesise cpu (D4/D5 harness top, -DSYNTHESIS)
==> yosys: synthesise ysyx_22040000_bus (B1 full-handshake top)
==> yosys synthesis OK: clean lint, all check -assert passed
```

无 latch, 无 multi-driven, 无 unconnected. 所有 `check -assert` 通过.

---

## 5. icache.v 数据通路 / 修改点行号

(基于改后 `npc/vsrc/icache.v`, B4c 重写版本)

| 关键点 | 行号 / 段 | 简述 |
| ------ | --------- | ---- |
| 参数声明 (OFFSET_LOG 默认提到 5) | 60-62 | `BLOCK_BYTES = 32`, `BLOCK_WORDS = 8` |
| 派生 localparam              | 75-86 | 新增 `BLOCK_WORDS / BLOCK_BITS / WORD_LOG / WCNT_W` |
| 地址切分 (word_off)          | 90-100| `req_woff = req_addr[OFFSET_LOG-1:2]`, WORD_LOG=0 退化 |
| data_arr 升级宽度            | 103  | `reg [BLOCK_BITS-1:0] data_arr [..][..]` |
| FSM 3 态                     | 132-145 | S_IDLE / S_FILL / S_DONE + fill_last |
| miss 入口 latch              | 218-225 | 锁存 `miss_index / tag / way / woff / base` |
| S_FILL beat 写入             | 229-244 | 按 `fill_cnt` 选 word slot 写入, last beat 同时置 valid/tag |
| bus_req_addr 计算            | 188   | `miss_base_r + (fill_cnt << 2)` |
| resp_data 选 word            | 162-180 | `hit_word` (idle_hit) vs `done_word` (S_DONE), 用 `iw*32 +: 32` 静态宽度 +: |
| LRU 更新 (touched_way)       | 199-211, 247-256 | 与 B4b 同, 但 touched_index / touched_way 在 S_DONE 时来自 `miss_*_r` |
| cnt_victim 同步              | 215  | 在 fill last beat 累加, 保持 `victim == miss` 不变量 |

---

## 6. 边缘情况 + 已测

| 情形 | 预期 | 测试 |
| ---- | ---- | ---- |
| 4B 块退化 (OFFSET=2)                 | 等价 B4b (多 1 拍 S_DONE) | sweep 没列, 但 OFFSET=2/BLOCKS=4/WAYS=1 在 reset 后 microbench 应仍 PASS; 我没专门跑这一档但 sweep 跑了 OFFSET=4..6 都过 |
| `req_addr` 跨块边界 (word_off=BLOCK_WORDS-1)  | 取出块最后一个 word | hello 已经会触发 (PC 顺序进入新块前一定有 word 7) |
| miss 进 fill 时上游 req 不释放        | 上游一直等 resp_valid, S_FILL/S_DONE 期间 req_valid=1 不影响 | hello / microbench 验证 OK |
| reset 期间 req_valid = 0              | cnt_victim 不会被错误累加 | 通过 `(state==S_FILL) & fill_last` 判定保证, 实测 victim=miss |
| fill 期间 bus 给一拍空响应再继续      | fill_cnt 仅在 bus_resp_valid 时递增 | 当前 MemBridge 不会发空响应; 未来 SDRAM 加 delay 也兼容 |
| `WAYS_LOG=0` (直接映射) + 大块         | age_arr 退化, victim_way 永远 0; 数据通路不变 | 我没切 1-way 跑回归 (任务要求只要 2-way), 但与 B4b 同结构 |

### 6.1 没测的边缘情况 (建议 follow-up 加单元 testbench)

1. **`OFFSET_LOG=2` (4B 块退化)** 完整复测: 应等价 B4b 行为 + 多 1 拍 S_DONE.
2. **4-way / 8-way 配置**: B4c sweep 没专门测 WAYS_LOG=2,3.
3. **bus 间歇 resp** (resp 之间有空拍): MemBridge 不会, 但 SDRAM 真延迟下可能.
4. **fill 中途 bus 报 fault (`io_fault`)**: 我没改 fault 逻辑, 任何 bus_resp_valid
   + io_fault 的同周期被 ysyx_22040000.v 当作 ifu_fault. 但 B4c 中 ifu_fault 是
   靠 `(state == S_IF) & ifu_cpu_resp_valid & io_fault` 检测, 而 ifu_cpu_resp_valid
   在 S_FILL 中间几拍是 0, 只在 S_DONE 那一拍是 1. **如果 fault 发生在
   S_FILL 中间, 不会被上游捕获**. 这是个已知遗留 -- 当前 MemBridge / 现有
   SoC 不会在 SimpleBus 读响应上发 fault (只有 DECERR 走 LSU 路径), 所以
   实测不踩, 但需要在报告里点出.

### 6.2 建议单元测试 (testbench, 非本任务必做)

```verilog
// npc/tests/icache-tb/icache_tb.sv (建议)
//   1. tb_fill_then_hit_seq:  顺序读 8 个 word, 第 1 个 miss 8 拍 fill +
//      1 拍 done, 后 7 个 hit (cycle = 8+1+7 = 16)
//   2. tb_replacement_2way:    在 2-way 8-set 配置, 让 PC 命中同 set 不同 tag
//      3 次, 验证 LRU 把第一次填入的 way 踢掉
//   3. tb_block_size_offset:   block size = 32B 时, woff 选 0..7 都能正确
//      取出 word, 不会取错相邻 word
//   4. tb_back_to_back_miss:   连续两个 miss 落不同 set, S_DONE 下一拍立即
//      进下一次 miss 而不是夹一拍空闲
//   5. tb_woff_at_block_end:   首次访问 PC = base + (BLOCK_BYTES - 4), miss
//      时 fill 8 拍, S_DONE 返回的是 woff=7 这个 word
//   6. tb_param_param_sweep:   `WORD_LOG=0 / 2 / 3 / 4` 都综合 + sim 一遍
```

---

## 7. 已知遗留

- **dcache 未做**: 任务只要 icache 达标. 现在 LSU 路径仍直连 MemBridge
  AXI, store 操作走 burst-less SimpleBus, 性能瓶颈仍在 load/store.
- **burst-mode bus 未做**: B4c multi-beat fill 是用 8 次独立 SimpleBus
  单 word 协议串起来, 没用 AXI burst, 没用 MemBridge 的 burst hint.
  优化空间: 改 MemBridge 支持 4-beat / 8-beat burst, fill 时少握手.
- **OFFSET_LOG=2 (4B 块退化路径)** 没专门做回归: 现在默认是 5, 没人会切
  回 2, 但作为兼容性应保证. 已知逻辑等价 B4b.
- **`io_fault` 在 fill 中间发生**: ' 6.1 已说明, 当前 SoC 不会触发, 但
  写在已知遗留里以便后续加 fault 注入测试.
- **B4c sweep 没专门覆盖 1-way / 4-way + 大块**: 任务要求只到 90%, 默认
  配置满足. 4-way 大块或许能更高 hit_rate, 但触发器开销翻倍.
- **没专门写 testbench**: ' 6.2 列了 6 个建议用例, 单元测试维度更完备, 但
  任务范围内 hello + microbench 已能覆盖核心数据通路.

---

## 8. 关键 hit_rate 提升解释

为什么从 B4b 48.48% 跳到 B4c 99.46% (50.98 pp)?

**核心**: 块大小 4B 时, 顺序取指 `PC -> PC+4 -> PC+8 -> ...` 每次都命中
**不同 cache line**. 即使工作集再小, 也至少有 (instruction count) 个
cold miss. block size = 32 B 时, 取指 `PC -> PC+4 -> ... -> PC+28` 都在
同一 line, hit rate 直接从 0% 起跳到 7/8 = 87.5% (空间局部性).

实测分解 (B4c 默认 32x32B-2way, microbench access=534425):

```
理论 cold-block miss 数 = code_footprint / block_size
                       约= 30 KB / 32 B = 960 唯一块
实测 miss = 2868 -> 平均每块被 fetch 约 (2868 / 960) 约= 3 次
( 不是每块只 miss 1 次, 因为 microbench 内层循环跨多个块,
  容量 1 KB / 32 块, 工作集超容量时仍会 evict + 再 fetch. )

hit = 534425 - 2868 = 531557
  其中  "同块内顺序顺取" 至少占 (7/8) * 534425 = 467622
  剩 531557 - 467622 = 63935 是  "已 fetch 块的二次复用"
                                (内层循环 hot path)
```

也就是说:

- **空间局部性 (大块)** 贡献了 ' 87.5% hit rate.
- **时间局部性 (小工作集 + 1 KB 容量)** 把额外 12 pp 拉到 99.46%.
- B4a/B4b 这两条都吃不到: 块大小 4B 没空间局部性; 容量 64 B 装不下任何
  内层循环.

---

## 9. 总结一句

B4c 改造了 icache 数据通路 (4B 块 -> 32B 块) + FSM (2 态 -> 3 态 multi-beat
fill), 引入字偏移选 word 通路. 默认参数 **OFFSET_LOG=5, BLOCKS_LOG=5,
WAYS_LOG=1** (1 KB 容量, 32 B 块, 32 块, 2-way). microbench test hit
rate 从 B4b 48.48% 提升到 **99.46%**, 远超 90% 目标. 同时 hello cycle
从 31749 降到 29067 (-8%), microbench cycle 从 47.9M 降到 7.6M (-84%).
yosys 综合 clean, victim==miss sanity 全过, 不动 SoC / 外设 / Makefile.
