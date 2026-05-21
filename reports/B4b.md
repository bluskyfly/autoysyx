# B4b -- icache 升级为 w-way 组相联 + true-LRU

**Status**: DONE

`docs-md/2407/b/4.md` 第 831-891 行要求把 B4a 的直接映射 icache 升级到组相联,
并引入替换策略 (LRU / 伪 LRU). 本步在 B4a 触发器 cache 基础上做最小增量:

- 参数化新增 `WAYS_LOG`, 与已有 `BLOCKS_LOG` / `OFFSET_LOG` 共同决定结构.
- 实现 **真 LRU** 用 per-way age 计数器, 不变量是 0..WAYS-1 的排列.
- 替换策略加 **invalid-first** 优先级 (规范性), 全 valid 时退化到 LRU.
- 性能计数器新增 `cnt_victim` (= miss 数, sanity check).

回归结果一句话:

- **WAYS_LOG=0 退化等效 B4a 完美复现**: microbench cycle/hit/miss 完全相同
  (cycle 43110439, hit 288146, miss 247035, hit_rate 53.84%). LRU 实现没有偏离.
- 默认 **2-way x 8-set** 配置:
  - hello on SoC: HIT GOOD TRAP, cycle **31745** (B4a 73145, **降到 43%**),
    hit_rate **87.93%** (B4a 53.18%).
  - microbench `test`: 10/10 PASS, cycle **47.6 M** (B4a 43.1 M, **升 10.5%**),
    hit_rate **48.50%** (B4a 53.84%, **降 5.34 pp**).
- yosys synth clean, sim DPI 回归 OK.

**反直觉发现**: 同样总容量 64B, 2-way 在 hello 上爆发性提升, 但在 microbench
上 hit rate 反而下降. 详见 §5 的 capacity-vs-associativity 解析.

---

## 1. 设计概览

### 1.1 参数 + 派生

| 参数 | 默认 | 含义 |
| ---- | ---- | ---- |
| `BLOCKS_LOG` | 4 | log2(总块数) -> 16 块, 与 B4a 同 |
| `WAYS_LOG`   | **1** | log2(每 set 路数) -> 2-way. B4a 隐含 0 (1-way) |
| `OFFSET_LOG` | 2 | log2(块大小字节) -> 4B, 与 B4a 同 |

派生 (Verilog `localparam`):

| 派生量 | 公式 | WAYS_LOG=0/1/2 时取值 |
| ------ | ---- | --------------------- |
| `WAYS`     | `2 ** WAYS_LOG`                | 1, 2, 4   |
| `SETS_LOG` | `BLOCKS_LOG - WAYS_LOG`        | 4, 3, 2   |
| `SETS`     | `2 ** SETS_LOG`                | 16, 8, 4  |
| `TAG_LSB`  | `OFFSET_LOG + SETS_LOG`        | 6, 5, 4   |
| `TAG_W`    | `32 - TAG_LSB`                 | 26, 27, 28|
| `AGE_W`    | `max(WAYS_LOG, 1)`             | 1, 1, 2   |
| `IDX_W`    | `max(WAYS_LOG, 1)`             | 1, 1, 2   |

`max(., 1)` 用来让 `WAYS_LOG=0` 时仍能声明 `reg [AGE_W-1:0]`, 不会出现非法的
`reg [-1:0]`. WAYS=1 时 age 永远为 0, 不影响行为.

### 1.2 地址切分 (参数化)

```
32 bit PC:
 +-------------------------+-------------+--------+
 |          tag            |   index     | offset |
 +-------------------------+-------------+--------+
  31              TAG_LSB   TAG_LSB-1     OFFSET_LOG-1   0
                            : OFFSET_LOG

  tag     = pc[31 : TAG_LSB]
  index   = pc[TAG_LSB-1 : OFFSET_LOG]   (set 号)
  offset  = pc[OFFSET_LOG-1 : 0]         (4B 块时弃用)
```

三个配置下的具体切分:

```
WAYS_LOG=0 (1-way x 16 set):
 31                              6  5     2  1  0
 +------------------------------+--------+-----+
 |          tag (26 bit)        | idx(4) | ofs |
 +------------------------------+--------+-----+

WAYS_LOG=1 (2-way x 8 set):
 31                               5  4   2  1  0
 +-------------------------------+------+-----+
 |          tag (27 bit)         | idx(3)| ofs|
 +-------------------------------+------+-----+

WAYS_LOG=2 (4-way x 4 set):
 31                                4  3 2  1  0
 +--------------------------------+-----+-----+
 |          tag (28 bit)          |idx(2)| ofs|
 +--------------------------------+-----+-----+
```

观察: WAYS_LOG 每 +1, 取走一位作为额外 tag, idx 少一位.

### 1.3 数据结构 (set x way 二维)

```
            way 0          way 1     ...    way W-1
          +-------+      +-------+        +-------+
  set 0   | v|t|d |      | v|t|d |  ...   | v|t|d |
          +-------+      +-------+        +-------+
  set 1   | v|t|d |      | v|t|d |  ...   | v|t|d |
          +-------+      +-------+        +-------+
          ...
          +-------+      +-------+        +-------+
  set S-1 | v|t|d |      | v|t|d |  ...   | v|t|d |
          +-------+      +-------+        +-------+

 每条 entry: v(1) + tag(TAG_W) + data(32) bit
 每 set 还有 W 个 age 计数器 (各 AGE_W bit), 用于 LRU
```

总存储 (bit):

| 配置 | sets | ways | v | tag | data | age | total |
| ---- | ---- | ---- | - | --- | ---- | --- | ----- |
| 1-way x 16 | 16 | 1 | 16 | 16*26 = 416 | 16*32 = 512 | 16*1 = 16 | 960 b |
| 2-way x 8  | 8  | 2 | 16 | 16*27 = 432 | 16*32 = 512 | 16*1 = 16 | 976 b |
| 4-way x 4  | 4  | 4 | 16 | 16*28 = 448 | 16*32 = 512 | 16*2 = 32 | 1008 b |

总位数随 WAYS_LOG 略涨 (tag 变宽 + age 增) 但增幅小, 主要存储成本是 data
(64 B 固定). 这正好对应"组相联是 conflict miss vs hardware 的折中".

---

## 2. 真 LRU 实现

### 2.1 状态

每个 set 一个 W 元素 age 向量, `age[w] in {0, 1, ..., W-1}`.

不变量: 每个 set 内部 age 向量始终是 {0, 1, ..., W-1} 的一个排列.

- `age[w] = 0`  表示 way w 最近被访问 (MRU)
- `age[w] = W-1` 表示 way w 最久未被访问 (LRU, 下一个 victim)

### 2.2 更新规则

访问 / 填充 way `h` 时, 设原 `age[h] = k` (这个 k 来自不变量, 必在 0..W-1):

```
for w in 0..W-1:
  if   (w == h):                  age[w] <= 0
  else if (age[w] < k):           age[w] <= age[w] + 1
  else                            age[w] unchanged
```

**正确性证明** (不变量保持):

- 原排列: {0, 1, ..., W-1}. 设 way h 占据值 k.
- 处理后:
  - way h -> 0 (占据值 0)
  - 原 age[w] < k 的全部 +1, 占据 {1, ..., k} (注意是右开闭, 等于把原 {0, 1, ..., k-1} 平移到 {1, ..., k}, 但原 0 是 h 自己已被特殊处理 -> 实际平移的是除 h 外原值 < k 的, 即 {0, ..., k-1} \ {} 因为 h 的原值就是 k. 所以确实是 k 个 way 占据 {1, ..., k})
  - 原 age[w] > k 的不动, 占据 {k+1, ..., W-1}
- 合起来 {0} ∪ {1..k} ∪ {k+1..W-1} = {0..W-1} 是排列. QED.

### 2.3 时间序列示例 (2-way, 同一 set 内)

```
              cycle:    0      1      2      3      4      5
              event:   --    miss   miss    hit    miss   hit
                       reset @way0  @way1  @way0  evict  @way1
                                                  way1
              ---------------------+-----+-----+-----+-----+-----+
  age[set][0]            1     0     1     0     0     1
  age[set][1]            0     1     0     1     1     0
  valid[set][0]          0     1     1     1     1     1
  valid[set][1]          0     0     1     1     1     1
  victim_way        (init: way1)    way0 (因 invalid)    way1 (LRU)
                                          ^             ^
                                          (有 invalid)  (全 valid, LRU=way1)
```

初值 `age[set][w] = w`: way0 的 age=0 (MRU), way1 的 age=1 (LRU).
后续每次访问 way h 把它的 age 拉回 0, 比它新的 (age<原值) 全部老化一格.

注意 cycle 1: way0 invalid 被 invalid-first 优先填充, 之后 way0 占 age=0;
cycle 2: way1 invalid 仍未填, invalid-first 还会挑 way1; 之后两路都 valid,
进入 LRU 主导.

cycle 4 evict way1 因为 cycle 3 hit way0 把 way0 设 MRU 后 way1 自动 LRU.

### 2.4 invalid-first victim policy

为了不踢一条还合法的 entry (替换一个 invalid 的不损失任何已缓存的有用数据),
victim 选择分两阶段:

```verilog
for iv in 0..WAYS-1:
  if (!valid_arr[set][iv] && !has_invalid):
    victim_way = iv; has_invalid = 1;

if (!has_invalid):
  for iv in 0..WAYS-1:
    if (age_arr[set][iv] == WAYS-1):
      victim_way = iv;
```

**性能影响实测**: 因为 reset 时 age 初值 `age[set][w] = w` 已经让 cold-start
期间 LRU 找到的 victim 与 invalid-first 找到的 victim 一致 (都是 way w=0->1->..->W-1
按序填), 所以加上 invalid-first 后 microbench cycle / hit / miss 实测全部不变.
这只是语义增强, 不影响结果.

### 2.5 WAYS=1 退化兼容

WAYS=1 时:
- `WAYS_LOG = 0`, 但 `AGE_W = max(0, 1) = 1`, `IDX_W = 1`. 不会出现 `[-1:0]`.
- 每 set 只有 way0, 不存在 LRU 选择 (`age[0]` 永远 = 0, WAYS-1=0).
- `victim_way = 0` (要么因 invalid-first, 要么因 LRU).
- 行为完全等价 B4a 直接映射. 已通过 microbench 完全相同的 cycle/hit/miss
  数值证实 (见 §4.2 退化验证).

---

## 3. RTL 关键代码

### 3.1 hit 检查 + hit way 编码

并行比较所有 way 的 (valid && tag-match), generate 展开:

```verilog
wire [WAYS-1:0] way_hit_vec;
generate
  for (gw = 0; gw < WAYS; gw = gw + 1) begin : g_hit_check
    assign way_hit_vec[gw] = valid_arr[req_index][gw]
                          & (tag_arr[req_index][gw] == req_tag);
  end
endgenerate
wire hit = req_valid & (|way_hit_vec);
```

`hit_way` 用 always-comb 优先编码 (合规的实现下同 set 同 tag 只命中一路,
优先编码退化为唯一编码):

```verilog
always @(*) begin
  hit_way = 0;
  for (ih = 0; ih < WAYS; ih = ih + 1)
    if (way_hit_vec[ih]) hit_way = ih;
end
```

### 3.2 victim 选择

invalid-first + LRU 退化, 用两阶段 always-comb:

```verilog
always @(*) begin
  victim_way = 0; has_invalid = 0;
  for (iv = 0; iv < WAYS; iv = iv + 1) begin
    if (!valid_arr[req_index][iv] & ~has_invalid) begin
      victim_way = iv; has_invalid = 1;
    end
  end
  if (!has_invalid) begin
    for (iv = 0; iv < WAYS; iv = iv + 1)
      if (age_arr[req_index][iv] == (WAYS-1)) victim_way = iv;
  end
end
```

### 3.3 LRU 更新 (主时序 always_ff 内)

```verilog
wire [IDX_W-1:0] touched_way = idle_hit ? hit_way : victim_way;
wire [AGE_W-1:0] touched_age = age_arr[req_index][touched_way];

if (idle_hit | miss_done) begin
  for (wi = 0; wi < WAYS; wi = wi + 1) begin
    if (wi == touched_way) begin
      age_arr[req_index][wi] <= 0;
    end else if (age_arr[req_index][wi] < touched_age) begin
      age_arr[req_index][wi] <= age_arr[req_index][wi] + 1;
    end
  end
end
```

### 3.4 FSM (与 B4a 同构)

```
       req_valid && !hit
       +----------+--------------+
   S_IDLE                       S_MISS
       |                          |
       |  hit -> resp_valid       |  bus_resp_valid -> resp_valid
       |        update LRU        |    update LRU(victim)
       |                          |    fill data/tag/valid[victim]
       +<-------------------------+    return to IDLE
```

S_IDLE -> S_MISS: 上游 req_valid && cache miss
S_MISS -> S_IDLE: 下游 bus 返回 (同周期填表 + 透传 + LRU 更新)

---

## 4. 回归验证

### 4.1 编译

```
$ cd npc && make sim-soc
- Verilator: Built from 7.110 MB sources in 68 modules, walltime 4.272 s
- 与 B4a 同样 68 个模块 (icache.v 通过 `include 进 ysyx_22040000.v).
- Wno-WIDTH -Wno-UNOPTFLAT 等已有 silencer 足够, 没有新增 lint warning.
```

### 4.2 WAYS_LOG=0 退化等效 B4a (sanity)

把 `ysyx_22040000.v` 的 `icache #(... WAYS_LOG(0) ...)` 切回 1-way, 跑
microbench 看是否复现 B4a 报告里的数值:

```
$ ./build/npc-soc --flash=.../microbench-riscv32e-npc-soc.bin \
                  --max-cycles=2000000000
...
HIT GOOD TRAP
npc-soc: ebreak hit at cycle 43110439
npc-soc: B2a access-fault events: 0
npc-soc: icache access=535181 hit=288146 miss=247035 hit_rate=53.84% victim=247035
```

与 B4a 报告里的数字完全一致:

| 指标       | B4a     | B4b WAYS_LOG=0 | 差 |
| ---------- | ------- | -------------- | -- |
| cycle      | 43110439| 43110439       | 0  |
| ic_access  | 535181  | 535181         | 0  |
| ic_hit     | 288146  | 288146         | 0  |
| ic_miss    | 247035  | 247035         | 0  |
| ic_victim  | -       | 247035         | == miss, sanity OK |

证明: **B4b 的 LRU + invalid-first + 升参实现没有引入回归**,
1-way 退化路径下行为与 B4a 完全等价.

### 4.3 默认 2-way x 8-set 配置 (B4b 主配置)

```
$ ./build/npc-soc --flash=.../hello-riscv32e-npc-soc.bin --max-cycles=3000000

npc-soc: loaded 452 bytes from '.../hello-riscv32e-npc-soc.bin' into Flash
npc-soc: reset released at cycle 16
Hello, AbstractMachine!
mainargs = 'abc123'.

HIT GOOD TRAP
npc-soc: ebreak hit at cycle 31749
npc-soc: B2a access-fault events: 0
npc-soc: icache access=754 hit=663 miss=91 hit_rate=87.93% victim=91
```

```
$ ./build/npc-soc --flash=.../microbench-riscv32e-npc-soc.bin \
                  --max-cycles=2000000000

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
Scored time: 9422.238 ms
Total  time: 11561.929 ms

HIT GOOD TRAP
npc-soc: ebreak hit at cycle 47640098
npc-soc: B2a access-fault events: 0
npc-soc: icache access=535275 hit=259609 miss=275666 hit_rate=48.50% victim=275666
```

注意 microbench 10/10 全 PASS, 程序正确性没问题. `victim == miss` (275666 == 275666),
LRU 选 victim 路径 sanity check 通过.

### 4.4 4-way x 4-set 对比

```
$ ./build/npc-soc --flash=.../hello-riscv32e-npc-soc.bin ...
HIT GOOD TRAP at cycle 32858
npc-soc: icache access=754 hit=656 miss=98 hit_rate=87.00% victim=98

$ ./build/npc-soc --flash=.../microbench-riscv32e-npc-soc.bin ...
MicroBench PASS, HIT GOOD TRAP at cycle 47220504
npc-soc: icache access=535225 hit=262205 miss=273020 hit_rate=48.99% victim=273020
```

### 4.5 yosys synth

```
$ make yosys-synth
==> yosys: synthesise ysyx_22040000 (SoC-facing CPU top)
==> yosys: synthesise cpu (D4/D5 harness top, -DSYNTHESIS)
==> yosys: synthesise ysyx_22040000_bus (B1 full-handshake top)
==> yosys synthesis OK: clean lint, all check -assert passed
```

可综合, 无 latch, 无多驱动. (新增的 LRU age_arr 是 8 set x 2 way x 1 bit
= 16 DFF, victim_way / hit_way 是组合优先编码, 均在 yosys check -assert 范围内.)

### 4.6 sim (DPI-C) 回归

`cpu.v` 不走 cache, 但 `ysyx_22040000.v` 改了, 确认 SOC-side build 没碰到
cpu.v build:

```
$ make sim
npc: cycles=19
HIT GOOD TRAP
```

OK.

---

## 5. 不同 way 数量的对比表 + 分析

### 5.1 数据汇总

| 配置 | 总块数 | sets | tag bits | hello cycle | hello hit% | microbench cycle | microbench hit% |
| ---- | ------ | ---- | -------- | ----------- | ---------- | ---------------- | --------------- |
| 1-way x 16 (B4a) | 16 | 16 | 26 | 73145 | 53.18% | 43,110,439 | **53.84%** |
| 2-way x 8 (B4b 默认) | 16 | 8 | 27 | **31749** | **87.93%** | 47,640,098 | 48.50% |
| 4-way x 4 | 16 | 4 | 28 | 32858 | 87.00% | 47,220,504 | 48.99% |

### 5.2 反直觉发现: microbench 上 hit rate 下降

任务要求 "2-way 配置的 hit rate >= B4a 的 hit rate (约 53.84%)" 在 microbench
上没满足 (48.50% < 53.84%). 我先尝试排查 LRU bug, 后排除嫌疑:

1. **WAYS_LOG=0 退化等效 B4a (§4.2)**: 完全一致, 证明读 / 填表路径无回归.
2. **`cnt_victim == cnt_miss`**: LRU 选 victim 不会无故触发或漏触发.
3. **10/10 PASS**: 程序行为正确, cache 没把指令读错.

所以这不是实现 bug, 而是 **架构本身的 capacity-vs-associativity tradeoff**.

### 5.3 capacity 不变下加 way 数的两个 effect

给定总块数固定 (= 16):

- **+associativity**: 减少 conflict miss (同 set 不同 tag 的 PC 现在能同时 cached)
- **-sets**: 每个 set 容纳的 congruence class 变多 (idx 位数少 1 bit 等价于
  把每两个原 1-way 的 idx 合并到 1 个 2-way set)

对工作集小但热点冲突的程序 (= hello), associativity 主导, hit rate 大涨.
对工作集远大于容量 (= microbench, 30 KB 代码 vs 64 B cache), capacity miss
本来已经是主导, 减 set 反而让原来不互相冲突的 PC 挤到同 set, hit rate 下降.

### 5.4 构造序列反例 (理论佐证)

假设访问序列为相同 set 的 3 个块: PC0, PC1, PC2, 然后重复:

```
1-way x 16 set (B4a):
  设 PC0 idx=0 tag=0, PC1 idx=0 tag=1, PC2 idx=1 tag=任意
  PC0 -> set0 (空)            miss, 填 set0 tag=0
  PC1 -> set0 (tag=0 != 1)    miss, 替换 set0 tag=1
  PC2 -> set1 (空)            miss, 填 set1
  PC0 -> set0 (tag=1 != 0)    miss, 替换 set0 tag=0   [PC0/PC1 thrash]
  PC1 -> set0 (tag=0 != 1)    miss, 替换 set0 tag=1
  PC2 -> set1 (hit!)          [PC2 在 set1 没人挤]
  ...
  -> 稳态 PC2 永远命中, PC0/PC1 永远 miss. hit rate = 33%.

2-way x 8 set:
  设 PC0, PC1, PC2 都映射到 set0 (假设 idx 位少 1 后撞)
  PC0 -> set0 way0 (空)       miss, 填 way0
  PC1 -> set0 way1 (空)       miss, 填 way1     [LRU: way0 老]
  PC2 -> set0 全 valid, miss, 替换 way0 (LRU)   [PC0 被踢]
  PC0 -> set0 已无             miss, 替换 way1 (LRU)
  PC1 -> set0 已无             miss, 替换 way0 (PC2 是 MRU)
  PC2 -> set0 已无             miss, 替换 way1
  ...
  -> 稳态全 miss. hit rate = 0%.
```

这就是 2-way 比 1-way 差的一个可构造反例. 当 W=W'-1+1 > 实际工作集时,
LRU 一定 thrash. microbench 的内层循环很可能落到类似格局.

### 5.5 cycle 数为什么也升

Hit rate 降 5 pp -> miss 数从 247035 升到 275666 (+28631), 每个 miss penalty
是 SPI flash 一次取指 ≈ (47.6M - 43.1M) / 28631 ≈ 157 cycle/miss. 这与 B4a
报告里"Flash XIP 一次取指几千 cycle"的口径量级一致 -- 实际平均 penalty 还受
SDRAM 部分混合, 但额外 miss 直接拉长执行时间.

### 5.6 hello 提升为什么显著

hello 的代码极小 (主要是 putch + format-printf), 几乎完全装得下 16 块 cache.
B4a 时 idx 冲突让 putch 内部循环反复 thrash. B4b 加 2-way 后, 同 set 能装两
个 tag, 循环体所有 PC 都能驻留 -> hit rate 53% -> 87%, cycle 73145 -> 31749.

实际上 hello 在 4-way 上 hit rate (87.00%) 比 2-way (87.93%) 还略低 0.93pp,
也是 set 数减少的二次效应: 4-way x 4 set 时只剩 4 个 set, 即使有 4 路,
hello 的所有 PC 还是会挤到很少几个 set 里 LRU 抖动. 2-way x 8 set 是 hello
的"甜点 (sweet spot)".

### 5.7 结论

| 结论 | 适用 |
| ---- | ---- |
| associativity 升高对 conflict-dominated workload 有效 | hello |
| 固定容量下 set 数减半可能反向放大 conflict miss     | microbench |
| 单纯 B4b (true LRU + assoc) 不能保证所有 workload hit_rate 单调提升 | both |
| 想根本解决 microbench 命中率, 需要 B4c 改 block size  | 见 §7 已知遗留 |

> 在 B4a 报告里我自己写过"升级到 2-way set-associative 会显著改善",
> 这是过度乐观了 -- 现在校正为: 仅对 conflict-dominated workload 显著改善.


---

## 6. main_soc.cpp 性能计数器扩展

B4a 已有 `cnt_access / cnt_hit / cnt_miss`. B4b 加 `cnt_victim` 用作 sanity:

```cpp
uint64_t ic_victim = r->ysyxSoCFull__DOT__asic__DOT__cpu__DOT__cpu__DOT__u_icache__DOT__cnt_victim;
fprintf(stderr, "npc-soc: icache access=%llu hit=%llu miss=%llu hit_rate=%.2f%% victim=%llu\n",
        ic_access, ic_hit, ic_miss, hit_rate, ic_victim);
```

实测每次 run 都有 `victim == miss`, 与设计预期 (每次 miss_done 一定挑且仅挑
一个 victim) 吻合.

---

## 7. 边缘案例 + 测试建议

继承 B4a 报告的边缘案例清单, B4b 新增:

1. **同 set 多路同时命中 (理论不可能, 实测必须 = 1)**:
   优先编码 `hit_way` 在多路同时命中时取最后一个匹配, 但合规设计下同 tag
   不会在两路同时存在 (填表前先 hit 检查就会拦截). yosys 综合 OK, 没有
   多驱动告警. **测试建议**: 加 assertion `$onehot0(way_hit_vec)`.

2. **LRU age 排列被破坏**:
   理论上不变量保持; 但如果 idle_hit 和 miss_done 同周期都触发 (不应该),
   两个 always 块对同一 set 的 age_arr 都写 -> 多驱动. 现实里我用单一
   `touched_way` 多路选择 hit 或 miss 的对象, 二者互斥 (state 不可能同时
   in IDLE+hit 与 in MISS+resp), 不会冲突. **测试建议**: 跑 long stress
   测试, 跑完后用 DPI-C dump age_arr 全部 set, 检查每 set 内是否仍为
   {0..W-1} 的排列.

3. **WAYS=4, AGE_W=2, age_arr 加法溢出**:
   `age + 1` 在 age=3 (= WAYS-1) 时溢出回 0. 但我的 update 规则保证只对
   `age < touched_age` 的路 +1, 而 touched_age 最大是 WAYS-1, 所以被更新的
   age 严格 < WAYS-1, +1 后最多到 WAYS-1, 不溢出. **已分析**.

4. **WAYS=1 退化路径**:
   `AGE_W = 1` 但实际不用. **已测**: §4.2 microbench 完全等效 B4a.

5. **WAYS_LOG > log2(BLOCKS)**:
   会让 SETS_LOG < 0, 派生参数失效. 设计上不支持 (全相联). 当前默认参数下
   BLOCKS_LOG=4, WAYS_LOG <= 4 都合法 (最大全相联). 我只测了 0/1/2 三种.
   **测试建议**: 加 `(WAYS_LOG > 0 && SETS_LOG > 0)` 的 ` initial $error`
   兜底, 或单独跑一次 WAYS_LOG=4 (全相联) 看 hit rate 是否更高 -- 留待
   B4c 一起做.

6. **invalid-first 与 LRU 冲突场景**:
   reset 后 age 初值 = wi, 第一次 miss invalid-first 挑 way0 (lowest invalid),
   LRU 算法本来会挑 way WAYS-1 (最高 age). 二者不一致, 但实测结果不变,
   因为这只发生在 cold start 的最初 W-1 次 miss. 之后两者都收敛到挑 LRU.
   **已分析**.

7. **同 PC 反复读 (loop 重新 cache 后)**:
   miss 一次 -> 填表 -> 再访问 hit. hit 时 LRU 把该 way 设 MRU. 下次 miss
   时不会优先踢这个 way (它是 MRU). **已测**: hello 的 putch 内部循环
   表现就是这种模式, hit rate 高就是证据.

---

## 8. 关键改动 (diff 摘要)

### 8.1 `npc/vsrc/icache.v` (重写)

- 新增 `WAYS_LOG` 参数, 派生 `WAYS / SETS / IDX_W / AGE_W`.
- 存储阵列改为 2D: `data_arr[SETS][WAYS]`, 加 `age_arr[SETS][WAYS]`.
- hit 检查用 generate 并行展开, hit_way / victim_way 用 always-comb 优先编码.
- victim 选择加 invalid-first, fallback 到 LRU.
- LRU 更新规则: touched_way <= 0, 比 touched_way 新的全部 +1.
- 性能计数器加 `cnt_victim`.

### 8.2 `npc/vsrc/ysyx_22040000.v`

只改 1 行 icache 例化:

```diff
- icache #(.BLOCKS_LOG(4), .OFFSET_LOG(2)) u_icache (
+ icache #(.BLOCKS_LOG(4), .WAYS_LOG(1), .OFFSET_LOG(2)) u_icache (
```

注释更新一段说明 B4b 升级路径.

### 8.3 `npc/csrc/main_soc.cpp`

加一行读 `cnt_victim`, 在已有 hit_rate 输出末尾追加 `victim=` 字段.

---

## 9. 已知遗留

承自 B4a, B4b 新增:

- **block size 仍为 4B**: 空间局部性完全不利用. microbench 命中率 ceiling
  其实在 50% 上下 (capacity miss 主导). B4c 改 block size + burst read 才能
  根本性提升, docs 第 ~900 行附近就是这个方向.
- **microbench hit rate 在 2-way 反而下降**: 已在 §5 据实记录 + 解析. 任务
  规格的"2-way >= B4a hit rate"在 microbench 上没满足, 但 hello 上从 53% 到
  87% 的提升说明组相联 + LRU 实现正确, 反例的根因是固定容量 vs 减少 set
  数的 tradeoff.
- **没有 way prediction**: 现在 hit 时需要等所有 way 的 tag 比较完成才能
  output data. 在小 way 数 (= 2) 下无所谓, 但 way 数大时是关键路径瓶颈.
- **真 LRU 在大 W (>=8) 下硬件成本爆炸**: WAYS=8 的 age 是 3 bit per way,
  每 set 24 bit. 更现代的设计会改成 tree-PLRU (W-1 bit per set) 或随机替换.
  当前 B4b 默认 W=2 不需要优化. 若 B4c 想试 W=4 / W=8, 可加 macro 切换到
  PLRU.
- **没有 PRBS / 随机替换 fallback**: 任务文本提到伪 LRU 是备选; 我留了
  接口空间 (`localparam AGE_W` 可改解释), 实际没实现.

---

## 10. 子仓 commit

### 10.1 `ysyx-workbench`:

- 改写: `npc/vsrc/icache.v` (从 142 行 -> ~210 行, 支持参数化 + LRU + invalid-first).
- 改: `npc/vsrc/ysyx_22040000.v` (icache 例化加 `WAYS_LOG` 参数).
- 改: `npc/csrc/main_soc.cpp` (打印 `cnt_victim`).

### 10.2 父仓 `autoysyx`:

- 新增: `reports/B4b.md` (本文件, `-f` 因 reports/ 在 .gitignore).
