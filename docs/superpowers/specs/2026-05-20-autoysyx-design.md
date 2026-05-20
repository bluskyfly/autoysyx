# autoysyx Design — 自动通关一生一芯 v24.07

| 元数据 | 值 |
|---|---|
| Date | 2026-05-20 |
| Owner | curry |
| Status | Draft (待用户审阅) |
| Target | YSYX v24.07, F→B 五阶段 + 两次流片准备 |
| Cohort docs | `docs-md/2407/`, `docs-md/ics-pa/`（已下载） |

---

## 1. 概述与目标

### 1.1 目标

让 Claude（claude-opus-4-7）**端到端自动完成**中国科学院计算所"一生一芯"v24.07 课程的所有**技术任务**，最终产出：

1. 一个可活性的 `ysyx-workbench/` 仓库（包含 NEMU、AM、Navy、npc、ysyxSoC 集成等子模块）
2. 每个阶段每个 task 的验证报告（`reports/*.md`）
3. 一套可重跑的脚本（`make all` 能从零复现验证）

### 1.2 非目标（明确不做）

- **入学答辩 / 阶段人工考核** — 这些需要真实学生本人参与，无法自动化
- **真实流片送 fab** — 流片需要 ECOS Studio 账号注册，由真人完成
- **A 阶段、S 阶段** — 官方讲义大部分未发布（`📚 🕊`），缺少自动化所需的输入
- **写读后感、答辩材料** — 这些是真人产出物
- **冒充学员身份** — 本项目是工程实验，不替代真实学习

### 1.3 设计原则

| 原则 | 说明 |
|---|---|
| 文档为准 | `docs-md/` 是规格的唯一来源；遇到歧义不脑补，停下问 |
| 外部 orchestrator | 编排逻辑在外部 Python 进程，不依赖单一 chat session 寿命 |
| 验证可信 > 跑得快 | 宁可慢也要让验证强到能挡住 LLM 的自欺自骗 |
| 失败隔离 | task 边界按"局部失败可回滚"切，不按教学章节切 |
| 环境可复现 | 工具链版本锁定，禁止"边跑边装" |
| 状态可审计 | 状态机走 append-only event log + projection，每次决策都能追溯 |

### 1.4 范围

```
覆盖           不覆盖
─────         ─────
F1-F6 (基础)   E7   (入学答辩)
E1-E6 (核心)   各阶段人工考核
D1-D6 (NEMU)  A/S  (讲义未发布)
C1-C5 (NPC)   真实流片
B1-B5 (SoC)
D6/B 流片准备
```

约 27 个原 task → 重新按"失败隔离性"切分约 40-45 个工程 task。


---

## 2. 架构

### 2.1 顶层结构

```
autoysyx/                                ← 本仓库 (Python orchestrator + docs + 状态)
├── docs-md/                             ← 已下载, 82 页 markdown (规格输入, 只读)
├── docs/superpowers/specs/              ← 本设计文档
├── orchestrator/                        ← Python 编排器 (本项目的"灵魂")
│   ├── main.py                          ← CLI entrypoint
│   ├── db.py                            ← SQLite 封装
│   ├── tasks.py                         ← Task 调度逻辑
│   ├── worker.py                        ← spawn claude CLI
│   ├── reviewer.py                      ← spawn codex CLI
│   ├── verifier.py                      ← 跑 test_runner + difftest
│   ├── bootstrap.py                     ← phase-0 装环境锁版本
│   ├── reporter.py                      ← 生成 reports/X.md
│   └── state.db                         ← SQLite (event log + projection)
├── plans/                               ← 每个阶段的 plan (markdown)
│   ├── 00-bootstrap.md
│   ├── F.md  E.md  D.md  C.md  B.md
│   └── tape-out-D.md  tape-out-B.md
├── prompts/                             ← 每个 task 的 prompt 模板
│   ├── F1.md ... B5d.md
│   └── _common/system-prompt.md          ← 给所有 worker 用的角色定义
├── test_runner/                         ← 每个 task 的验证脚本
│   ├── F1.sh ... B5d.sh
│   ├── difftest/                        ← difftest 配置 (D/C/B 阶段共用)
│   └── stage-{F,E,D,C,B}-final.sh       ← 阶段集成验证
├── tools/
│   ├── bootstrap.sh                     ← 装工具链, 写 env-lock.yaml
│   ├── check_env.sh                     ← 校验环境没漂
│   └── env-lock.yaml                    ← 工具链版本锁
├── reports/                             ← 每个 task 完成后写入
│   ├── PHASE0.md                        ← bootstrap 报告
│   ├── F1.md ... B5d.md
│   └── summary.md                       ← 总报告
├── ysyx-workbench/                      ← 产物仓库, git submodule, 从 OSCPU 克隆
│   ├── nemu/  abstract-machine/  ...
├── tests/                               ← orchestrator 自检 (pytest)
│   ├── test_db.py  test_tasks.py  test_verifier.py ...
├── CLAUDE.md                            ← worker 的工作约束
├── Makefile                             ← `make run / status / resume / test / reproduce`
└── README.md
```

### 2.2 数据流（高层）

```
┌─────────────────────────────────────────────────────────────────────┐
│  外部 Python orchestrator (autoysyx/orchestrator/main.py)            │
│                                                                       │
│  python orchestrator/main.py run                                      │
│                                                                       │
│  ┌─────────────────────────────────────────┐                          │
│  │  Phase 0 (一次性): bootstrap            │                          │
│  │  - 装工具链 (apt + curl)                │                          │
│  │  - clone ysyx-workbench + ysyxSoC       │                          │
│  │  - 写 env-lock.yaml (锁版本)            │                          │
│  │  - 跑 smoke test (verilator + NEMU)     │                          │
│  └─────────────────────────────────────────┘                          │
│                       │                                               │
│  ┌────────────────────▼────────────────────┐                          │
│  │  主循环: while not all_done:             │                         │
│  │                                          │                         │
│  │   1. pick_next_task() from SQLite       │                          │
│  │      ← 状态投影 (event log → state)     │                          │
│  │                                          │                         │
│  │   2. assemble prompt (prompts/X.md      │                          │
│  │      + docs-md/<相关章节>               │                          │
│  │      + 前次 attempt 的错误日志)         │                          │
│  │                                          │                         │
│  │   3. spawn worker:                       │                         │
│  │      claude --print --output-format json │                         │
│  │        --model opus                      │                         │
│  │        --add-dir docs-md ysyx-workbench  │                         │
│  │        --allowedTools "Bash Edit Read    │                         │
│  │                       Write Glob Grep"   │                         │
│  │        --max-budget-usd 5.0              │                         │
│  │        --append-system-prompt @sys.md    │                         │
│  │        -p @prompts/X.md                  │                         │
│  │                                          │                         │
│  │   4. parse TASK_CONTRACT JSON            │                         │
│  │      ← regex 提取, schema 校验          │                          │
│  │                                          │                         │
│  │   5. run verifier:                       │                         │
│  │      - test_runner/X.sh (exit + grep)   │                          │
│  │      - difftest (D/C/B 阶段)            │                          │
│  │      - 干净环境复跑                      │                         │
│  │                                          │                         │
│  │   6. if green:                           │                         │
│  │      spawn codex review:                 │                         │
│  │        codex exec "review diff: ..."     │                         │
│  │                                          │                         │
│  │   7. if codex also green:                │                         │
│  │      - git commit (有签名)               │                         │
│  │      - write reports/X.md (机器生成)    │                          │
│  │      - emit event task_done              │                         │
│  │      - 进入下一个 task                   │                         │
│  │                                          │                         │
│  │   8. if any fail:                        │                         │
│  │      - emit event attempt_failed         │                         │
│  │      - 把错误日志打包到下次 prompt       │                         │
│  │      - 派新 worker 重试 (fresh subagent) │                         │
│  │      - attempts++                        │                         │
│  │                                          │                         │
│  │   9. if attempts >= 3:                   │                         │
│  │      - 写 reports/X-FAILED.md            │                         │
│  │      - emit event task_failed            │                         │
│  │      - exit 1                            │                         │
│  └──────────────────────────────────────────┘                         │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.3 控制平面 vs 数据平面

| 平面 | 位置 | 状态 |
|---|---|---|
| 控制平面 | `orchestrator/*.py` | SQLite (`state.db`) - 状态机 |
| 数据平面 | `ysyx-workbench/*` | Git - 实际代码产物 |
| 输入 | `docs-md/`, `plans/`, `tasks.yaml` | 只读, 任何改动需要重新初始化 |
| 输出 | `reports/`, `ysyx-workbench/` 中的 commit | append-only 风格 |
| 缓存 | `.humanize/skill/`, `.cache/` | 随时可清, 不影响重跑 |

### 2.4 与 humanize 的关系

| humanize 提供 | autoysyx 用法 |
|---|---|
| `humanize:ask-codex` (`ask-codex.sh`) | 直接调，用于 review 每个 task 的 diff |
| `humanize:start-rlcr-loop` | **不直接用**，但参考其状态机设计 |
| `setup-rlcr-loop.sh` | 参考其 `setup-*.sh` 模板写 `bootstrap.sh` |

humanize 是为"单个 plan 多轮迭代"设计；autoysyx 是为"~40 个 task 串行执行"设计，状态机不一样，所以自己写。


---

## 3. 组件细节

### 3.1 SQLite Schema (`orchestrator/state.db`)

```sql
-- ===== Append-only event log =====
CREATE TABLE events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,                  -- ISO 8601 UTC
    type        TEXT NOT NULL,                  -- 'phase0_done', 'task_started',
                                                -- 'attempt_started', 'attempt_failed',
                                                -- 'attempt_passed', 'codex_passed',
                                                -- 'task_done', 'task_failed', 'env_check_failed'
    task_id     TEXT,                           -- nullable
    payload     TEXT NOT NULL                   -- JSON blob
);
CREATE INDEX idx_events_task ON events (task_id, ts);

-- ===== Projection: 当前状态 (派生自 events) =====
-- 任何时候可以用 SELECT 重建
CREATE VIEW task_state AS
SELECT
    task_id,
    -- 状态: pending / running / completed / failed / skipped
    -- (实现见 db.py 的 SQL window 函数)
    ...
FROM events
WHERE task_id IS NOT NULL
GROUP BY task_id;

-- ===== 环境锁 =====
CREATE TABLE env_lock (
    tool        TEXT PRIMARY KEY,
    version     TEXT NOT NULL,
    path        TEXT NOT NULL,
    sha256      TEXT,                            -- nullable, 大文件不算
    locked_at   TEXT NOT NULL
);

-- ===== Attempts (每次重试的详细记录) =====
CREATE TABLE attempts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id         TEXT NOT NULL,
    attempt_num     INTEGER NOT NULL,
    started_at      TEXT NOT NULL,
    ended_at        TEXT,
    worker_session  TEXT,                       -- claude session_id
    contract_json   TEXT,                       -- 解析后的 TASK_CONTRACT
    verify_log_path TEXT,                       -- reports/attempts/<id>/verify.log
    codex_log_path  TEXT,
    outcome         TEXT,                       -- 'passed' / 'failed' / 'timeout'
    fail_category   TEXT,                       -- 'compile' / 'test' / 'difftest' /
                                                -- 'codex_reject' / 'contract_invalid' /
                                                -- 'env_drift' / 'timeout'
    cost_usd        REAL
);
```

### 3.2 Task 切分原则 (tasks.yaml)

```yaml
# tasks.yaml — Single source of truth for task definitions
# Auto-generated from plans/, refreshed when plans change.

tasks:
  - id: PHASE0
    title: Bootstrap toolchain & repos
    deps: []
    estimated_minutes: 30
    verification:
      type: env_lock_complete
      file: tools/env-lock.yaml
      required_tools:
        - verilator         # already 5.042
        - yosys             # already 0.60+
        - riscv32-unknown-elf-gcc  # already 15.1
        - riscv64-linux-gnu-gcc    # need install
        - qemu-system-riscv64      # need install
        - mill                     # need install
    immutable_after: true       # phase0 once locked, no re-run

  - id: F1
    title: 如何科学地提问 (产出提问规范报告)
    deps: [PHASE0]
    doc_refs: [docs-md/2407/f/1.md]
    estimated_minutes: 20
    verification:
      type: doc_artifact
      check:
        - "[ -f reports/F1.md ]"
        - "grep -q '提问模板' reports/F1.md"
        - "grep -q 'STFW\\|RTFM\\|RTFSC' reports/F1.md"

  - id: D1a
    title: NEMU 实现 RV32I 基础指令集
    deps: [E6, PHASE0]
    doc_refs:
      - docs-md/2407/d/1.md
      - docs-md/ics-pa/PA1.md
      - docs-md/ics-pa/PA2.md
      - docs-md/ics-pa/2.2.md   # RTFM
      - docs-md/ics-pa/2.3.md   # Programs, Runtime, AM
    immutable_files:
      - ysyx-workbench/nemu/tests/cpu-tests/      # 不可改测试
      - ysyx-workbench/nemu/Makefile              # 不可改构建脚本
    estimated_minutes: 240
    verification:
      type: multi_step
      steps:
        - { name: clean_build,
            cmd: "cd ysyx-workbench/nemu && make clean && make ARCH=riscv32-nemu",
            expect_exit: 0 }
        - { name: cpu_tests,
            cmd: "cd ysyx-workbench/nemu && make ARCH=riscv32-nemu run-cpu-tests-rv32i",
            expect_exit: 0,
            expect_grep: ["ALL", "PASS"] }
        - { name: difftest_unused_here,
            note: "D1a 阶段尚无 NPC, difftest 留给 D4" }

  - id: D6c
    title: ysyxSoC 跑 hello world
    deps: [D6a, D6b]
    doc_refs: [docs-md/2407/d/6.md]
    estimated_minutes: 60
    verification:
      type: multi_step
      steps:
        - { name: run_hello,
            cmd: "bash scripts/run_d6_hello.sh",
            expect_exit: 0,
            expect_grep: "Hello World!",
            timeout_sec: 600 }
        - { name: verify_artifact,
            cmd: "ls ysyx-workbench/npc/build/V*-hello.bin",
            expect_exit: 0 }

  # ... 共约 40-45 个 task, 完整列表见第 8 节 ...
```

### 3.3 Prompt 模板结构 (`prompts/<task_id>.md`)

每个 task 一个 markdown 文件，会被自动注入下面 7 个变量后传给 worker：

```markdown
# Task: {{ task_id }} — {{ title }}

你是 autoysyx worker，目标是完成下面这个 task，让 verifier 通过。

## 角色边界
- 你只能改 ysyx-workbench/ 内 ALLOW 列表的目录
- 你绝对不能改: {{ immutable_files }}
- 你完成后必须用 ====TASK_CONTRACT_BEGIN==== 包裹 JSON 输出

## 任务说明
{{ task_description }}

## 文档参考 (规格)
{{ docs_content }}     ← 自动拼接 doc_refs 列表里的 markdown

## 你的工作目录
- 项目根: {{ project_root }}
- 工作目录: {{ work_dir }}

## 验收命令 (orchestrator 会独立跑, 不信你自报)
```bash
{{ verification_cmd_preview }}
```

## 已知陷阱 (从前次失败中提取, 第一次时此节为空)
{{ known_pitfalls }}

## 上一次尝试的错误日志 (第一次时为空)
{{ previous_error_excerpt }}

## 完成后必须输出的 TASK_CONTRACT
{{ contract_schema }}

不要写客套话, 不要重复任务描述, 直接动手。
```

### 3.4 System Prompt (`prompts/_common/system-prompt.md`)

```markdown
你是 autoysyx 的 worker subagent，在外部 Python orchestrator 调度下工作。

## 硬性约定
1. 文档为准。遇到歧义不脑补，写 known_risks 让上游决定。
2. 不改测试代码、不改 Makefile 主目标、不改 orchestrator 任何文件。
3. 完成后必须输出 TASK_CONTRACT JSON，schema 不对视为失败。
4. 不要在 stdout 写无关内容，只写实际操作 + 最后的 contract。
5. 不要尝试 git commit (orchestrator 来 commit)。
6. 不要尝试用 sudo (orchestrator 已经把环境装好)。
7. 你的 attempt 在 git worktree 隔离下进行，可放心改文件。

## 调试与求助
1. 真卡了不要硬撑。在 contract 的 open_issues 字段写出来。
2. 如果发现文档矛盾或不可执行，写 known_risks。
3. 允许 grep GitHub 上的其他 YSYX 实现作为参考，但 attribution 必须写在 key_decisions 里。

## 工具使用
- Bash: 跑测试 / 编译 / clone 子仓库
- Edit/Write: 修改源码
- Read/Glob/Grep: 读项目 / 查文档
```

### 3.5 Verifier 设计 (`orchestrator/verifier.py`)

```python
class VerifyResult:
    passed: bool
    fail_category: str       # 'compile' / 'test' / 'difftest' / 'env_drift' / 'timeout'
    log_path: str            # 完整 stdout/stderr 落盘路径
    grep_misses: list[str]   # 期望 grep 但没找到的关键字

def verify(task: Task, worktree: Path) -> VerifyResult:
    # 1. 干净环境复跑: clean build artifacts before running
    run_in_clean_env(task.verification.steps[0])

    # 2. 多步骤验证: 任一步失败立刻返回
    for step in task.verification.steps:
        rc, out, err = run_with_timeout(step.cmd, step.timeout_sec, cwd=worktree)
        log_step(step, rc, out, err)
        if rc != step.expect_exit:
            return VerifyResult(passed=False,
                                fail_category=classify_failure(step, rc, out, err),
                                log_path=...)
        for keyword in step.expect_grep:
            if keyword not in out:
                return VerifyResult(passed=False, fail_category='grep_miss', ...)

    # 3. difftest (D/C/B 阶段, 自动判断)
    if task.stage in ('D', 'C', 'B') and task.id != 'D1a':  # D1a 没 NPC 跳过
        difftest_result = run_difftest(worktree)
        if not difftest_result.passed:
            return VerifyResult(passed=False, fail_category='difftest', ...)

    # 4. 不可变文件检查
    if has_modified(worktree, task.immutable_files):
        return VerifyResult(passed=False, fail_category='immutable_modified', ...)

    return VerifyResult(passed=True, ...)
```


---

## 4. 数据流：一个 task 的端到端

### 4.1 时序图（以 D4 为例）

```
Orchestrator              SQLite              Worker (claude CLI)         Codex CLI
─────────────             ──────              ──────────────────         ─────────

pick_next_task() ──read──▶
                                              
                ◀──D4 (pending, deps met)──
                                                
emit task_started ───────────▶  events += task_started
                                                                          
create worktree (git worktree add)
                                                                          
assemble prompt:
  read prompts/D4.md
  read docs-md/2407/d/4.md
  read docs-md/ics-pa/PA2.md
  inject {{ vars }}
                                                
spawn worker ──────────────────────────────────▶  read docs+prompt
                                                  edit ysyx-workbench/npc/*
                                                  bash: make sim
                                                  iterate locally...
                                                  echo TASK_CONTRACT JSON
                ◀─────────────────────────────────  return JSON wrapper
                                                  
parse contract JSON
schema check                                      ← (失败则 attempt_failed,
                                                     重试无须 worker)

verify on clean worktree:
  bash test_runner/D4.sh
  bash test_runner/difftest/D4.sh

if all green:
  spawn codex ─────────────────────────────────────────────────────▶ review diff
                                                                  ◀──── 'looks good' or 'fix X'

if codex green:
  git commit on main
  emit task_done ──read──▶
  gen reports/D4.md
                                                  
  continue → next task

if any fail:
  emit attempt_failed ────▶
  destroy worktree
  attempts++
  if attempts < 3:
    pack error log into prompt
    spawn new worker (fresh subagent)
  else:
    emit task_failed
    write reports/D4-FAILED.md
    exit 1
```

### 4.2 跨会话恢复

```
[新会话 / orchestrator 进程刚启动]
        │
        ▼
python orchestrator/main.py resume
        │
        ▼
db.load_projection()
        │
        ├─ 发现 last_event = attempt_failed for D4, attempts=2
        │  → pick D4, attempts := 2, schedule attempt 3
        │
        ├─ 发现 last_event = task_done for B5d (最后一个)
        │  → 跑 final summary, exit 0
        │
        └─ 发现 last_event = task_failed for D6c
           → 不自动恢复, print "user must decide: skip/reset/edit-task"
```

### 4.3 不可变边界

| 文件 / 目录 | worker 可改? | 谁会改 | 改了怎么办 |
|---|---|---|---|
| `docs-md/` | ❌ | 只在 phase 0 初始化时下载 | 拒绝 commit, 报错 |
| `tasks.yaml` | ❌ | 用户手动 | 触发 schema 校验 + 状态 reconcile |
| `prompts/_common/` | ❌ | 用户手动 | 同上 |
| `test_runner/*.sh` | ❌ | 用户手动 | worker 改了直接判 fail |
| `tools/env-lock.yaml` | ❌ | phase 0 写一次 | env_check 失败, 停下 |
| `ysyx-workbench/<task 的 immutable_files>` | ❌ | 看 task 配置 | worker 改了直接判 fail |
| `orchestrator/*.py` | ❌ | 用户手动 | 触发自测重跑 |
| `reports/*` | ✅ | orchestrator | (worker 不应改) |
| `ysyx-workbench/<task 的 work_dir>` | ✅ | worker | 正常工作 |

---

## 5. 错误处理

### 5.1 错误分类与默认动作

| 类别 | 例子 | 默认动作 |
|---|---|---|
| **A. Worker 实现错误** | 编译失败 / 测试失败 / difftest 不通过 | retry with fresh worker, attempts++ |
| **B. Worker 协议违反** | 无 TASK_CONTRACT / contract JSON 不合 schema | retry, 在 prompt 强调格式 |
| **C. Codex 审查否决** | 找到代码质量 / 安全 / 正确性问题 | retry, 把 codex 意见注入 prompt |
| **D. Verifier 找到造假** | 改了不可变文件 / 测试输出说通过但实际没产物 | retry, 错误日志严格记录到事件 |
| **E. 环境漂移** | env-lock.yaml 检测到工具版本变了 | 立刻停, 通知用户 |
| **F. 资源耗尽** | 磁盘 < 10GB / 内存 OOM | 立刻停, 通知用户 |
| **G. 工具链失败** | apt install / git clone 超时 | 重试 3 次指数退避, 仍失败则停 |
| **H. 超时** | worker 跑了 max_minutes 还没回 | kill worker, attempts++ |
| **I. 上游 API 限流** | claude / codex 返回 rate limit | 指数退避 (60s, 300s, 1500s) |
| **J. SQLite / git 损坏** | DB 写失败 / git ref 错乱 | 立刻停, dump diagnostics |

### 5.2 重试策略

```
attempts = 0
while attempts < MAX_ATTEMPTS:
    attempts += 1
    worker_result = run_worker(prompt + accumulated_errors)
    verify_result = verify(...)
    if verify_result.passed:
        codex_result = codex_review(...)
        if codex_result.approved:
            commit + report
            return SUCCESS
        else:
            accumulated_errors.append("codex review: " + codex_result.summary)
    else:
        accumulated_errors.append("verify failed: " + verify_result.log_excerpt)
    # destroy worktree, recreate for next attempt
    recreate_worktree()

write_failure_report(accumulated_errors)
return FAILURE  # exit 1
```

`MAX_ATTEMPTS` 默认 3，可以在 tasks.yaml 里 per-task 覆盖（流片 task 可能给 5）。

### 5.3 失败暂停状态

attempts >= MAX 触发后，orchestrator：
1. 在 SQLite emit `task_failed` event
2. 写 `reports/<task>-FAILED.md` 含完整 ledger（每次 attempt 的 prompt、worker 返回、verify 日志、codex 意见、自动诊断）
3. exit 1，进程退出

用户的选项（手动跑命令）：
- `python orchestrator/main.py skip <task>` — 标 skipped，继续后面
- `python orchestrator/main.py retry <task>` — 重置 attempts，再来一轮
- 修改 `tasks.yaml` / `plans/X.md` / `test_runner/X.sh`，让验收宽一点 / prompt 更详细
- 修改 `prompts/<task>.md` 加针对性提示

### 5.4 反 LLM 自欺自骗的 10 条硬规则

Codex review 指出 YSYX 场景下 LLM 必踩的 10 个"自欺欺人"模式，本 spec 一一对应应对：

| # | LLM 常见自欺模式 | 反作弊规则 + 实施方式 |
|---|---|---|
| 1 | 改测试脚本让它更短/更宽松 | `immutable_files` 列表 + verifier git diff 检查; worker 越界视为失败 |
| 2 | 用 grep 关键字伪造成功日志 | 同时检查 exit code + 多个 `expect_grep` + 必须有 artifact 文件存在 |
| 3 | 依赖历史 build 产物冒充当前编译过 | verifier 强制 `make clean` 后在 fresh worktree 跑, 复跑结果为准 |
| 4 | 只改日志格式不改真实语义 | 必跑 difftest (D/C/B 阶段), 逐指令对比寄存器+PC+内存 |
| 5 | 硬编码官方测试样例 | tasks.yaml 跑官方测试集, 不让 worker 改 test; 跑多组测试覆盖 |
| 6 | 关 warning/assert/strict flag | verifier 警报编译选项里出现 `-Wno-` / `NDEBUG` / 关键 assert 被 `#ifdef` 包裹 |
| 7 | 用未定义行为碰运气 | difftest 用多 seed 跑 (RTL); valgrind 跑 NEMU (软件) |
| 8 | 文档没写清的地方脑补语义 | TASK_CONTRACT 的 `known_risks` 字段强制声明; codex review 阶段对照原文档 |
| 9 | Subagent 之间继承错误结论 | 每次重试 fresh subagent; 历史只传"错误日志"不传"上次的结论" |
| 10 | 报告越写越像真相, 代码越偏越远 | 报告由 `reporter.py` 从 SQLite 结构化记录生成, worker 不写 markdown 报告 |

### 5.5 附加防线

- **TASK_CONTRACT schema 强制**: jsonschema 校验, 不合规视为 attempt 失败
- **immutable hash 检查**: verifier 在 verify 前比对 `test_runner/`, `tasks.yaml` 等关键文件的 sha256
- **`tasks.yaml` 是 single source of truth**: 多次重试不读 worker 自己写的"放宽建议版本"
- **Codex review 独立**: review 阶段不让 worker 参与, 防止 worker prompt 反向影响 codex
- **负例测试**: D/C/B 阶段集成测试含一个"错误实现必须 failed"的反向 case, 验证 verifier 本身有效


---

## 6. 测试策略

### 6.1 三层验证

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: Task 验收 (per-task)                                │
│  test_runner/<task>.sh                                       │
│  - clean build → run tests → grep keywords                   │
│  - 双重判定: exit code + 关键字命中                          │
├─────────────────────────────────────────────────────────────┤
│ Layer 2: 阶段集成 (per-stage final)                          │
│  test_runner/stage-{F,E,D,C,B}-final.sh                      │
│  - 跨 task 联调                                              │
│  - F-final: mini-RISC-V 跑 cpu-tests                         │
│  - D-final: NEMU 完整 PA + minirv 接 ysyxSoC 跑 hello         │
│  - B-final: 流水线 NPC 接 SoC 跑超级玛丽 + Cache 命中率达标   │
├─────────────────────────────────────────────────────────────┤
│ Layer 1: difftest (灵魂验证, D/C/B 阶段贯穿)                  │
│  test_runner/difftest/                                       │
│  - NEMU (作为参考) ↔ NPC (被测) 逐指令 diff                  │
│  - 寄存器+PC+内存任何一处不一致即失败                         │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Orchestrator 自检 (`tests/`)

```
tests/
  test_db.py                 # SQLite schema + event sourcing 正确
  test_tasks.py              # tasks.yaml 解析 + 依赖图无环
  test_pick_next_task.py     # 状态机：选下一个 task 的逻辑
  test_worker.py             # spawn claude CLI 的 mock 测试
  test_verifier.py           # verifier 各种 fail_category 路径
  test_immutable_check.py    # 反作弊：改了不可变文件能识别
  test_state_recovery.py     # event log → projection 重建
  test_dry_run.py            # 端到端 dry run, mock worker 和 codex
  test_reporter.py           # reports/X.md 模板生成
```

跑：`make test` 或 `pytest tests/` （要求 < 2 分钟跑完）。

### 6.3 边缘案例清单

按用户 CLAUDE.md 要求：每次代码完成后列出 edge cases。下面是**预期会写代码时**会遇到的：

| 类别 | 边缘 case | 测试名 |
|---|---|---|
| **冷启动** | 第一次跑，DB 不存在 | `test_db::test_cold_start` |
| **DB 损坏** | events 表半截写入 | `test_state_recovery::test_partial_event_recovered` |
| **依赖** | tasks.yaml 有循环依赖 | `test_tasks::test_cycle_detection` |
| **依赖** | task 标 deps 但 deps 不存在 | `test_tasks::test_unknown_dep_errors` |
| **完成** | 所有 task done → 跑 summary | `test_pick_next_task::test_all_done` |
| **skipped** | 用户标 skipped → 不算 failed | `test_pick_next_task::test_skipped_excluded` |
| **timeout** | worker 跑超时 → kill, 标 timeout | `test_worker::test_timeout_kills` |
| **空 diff** | worker 没改任何文件就返回 success | `test_verifier::test_empty_diff_fail` |
| **immutable 被改** | worker 改了 test_runner/X.sh | `test_immutable_check::test_test_file_changed` |
| **contract 缺失** | 没有 TASK_CONTRACT 标记 | `test_worker::test_no_contract_fail` |
| **contract 格式错** | JSON 解析失败 | `test_worker::test_invalid_json_fail` |
| **contract schema 错** | 缺必需字段 | `test_worker::test_missing_required_field` |
| **env 漂移** | 跑到一半 verilator 升级了 | `test_dry_run::test_env_drift_halts` |
| **磁盘** | worktree 创建失败 | `test_dry_run::test_disk_full_handled` |
| **网络** | apt install 超时 | `test_dry_run::test_apt_timeout_retries` |
| **codex 不可用** | codex CLI 返回非 0 | `test_dry_run::test_codex_unavailable` |
| **重启** | 跑到一半 SIGINT | (手工测试 - 不能 mock) |
| **API 限流** | claude 返回 rate limit | `test_worker::test_rate_limit_backoff` |
| **session 死亡** | 用户关 terminal | (天然支持 - SQLite 持久化) |

### 6.4 反作弊验证（Layer 0）

在每个 task `verify()` 调用前：

```python
def pre_verify_checks(task, worktree):
    # 0. 全部 immutable 文件 hash 没变
    for f in task.immutable_files:
        assert sha256(f) == locked_hash[f], f"immutable {f} modified"

    # 1. env-lock 校验
    for tool, locked_version in env_lock.items():
        current = capture(f"{tool} --version")
        assert locked_version in current, f"env drift on {tool}"

    # 2. git 状态: worktree 上的 commits 必须是 worker 在本 attempt 内创建的
    #    (防止 worker 偷复用历史 commits)
    assert worktree.head.created_at >= attempt.started_at

    # 3. 没有 .stamp 文件造假
    #    (官方测试常用 .stamp 标记"我跑过了", worker 不能偷写)
    assert no_orphan_stamp_files(worktree)
```

---

## 7. Task 清单（重切后约 44 个）

### 7.1 总览

```
Phase 0 (1 task):     PHASE0
F 阶段  (6 tasks):    F1, F2, F3, F4, F5, F6
E 阶段  (8 tasks):    E1, E2, E3, E4a, E4b, E5, E6, [E7 跳过]
D 阶段  (12 tasks):   D1a, D1b, D1c, D2, D3a, D3b, D4, D5,
                       D6a, D6b, D6c, D6d   (D6 拆 4 个)
C 阶段  (7 tasks):    C1, C2a, C2b, C3, C4, C5a, C5b
B 阶段  (10 tasks):   B1, B2a, B2b, B2c, B3, B4a, B4b, B4c,
                       B5a, B5b   (B5 拆 2 个简化)
─────────────────────────────────────────────────────────
共 44 个 tasks
```

### 7.2 关键 task 细节（节选）

| Task | Title | Deps | 预估时间 | 关键验证 |
|---|---|---|---|---|
| PHASE0 | Bootstrap | – | 30 min | env-lock 完整, smoke test 过 |
| F3 | 数字逻辑电路基础 | F2 | 60 min | Logisim 电路文件存在 + 跑测试通过 |
| E5 | 从 RTL 到可流片版图 | E2 | 90 min | yosys 综合无错 + 版图脚本能跑通 |
| E6 | 完成 PA1 | E1-E5 | 120 min | NEMU 跑通 calculator + 表达式求值 |
| D1a | RV32I 指令集 | E6 | 240 min | cpu-tests-rv32i 全过 |
| D1b | M 扩展 (乘除法) | D1a | 90 min | cpu-tests-m 全过 |
| D1c | Zicsr + ecall | D1b | 60 min | csr-tests 全过 |
| D4 | minirv RTL 处理器 | D1c, D2, D3a, D3b | 180 min | NPC vs NEMU difftest 全过 |
| D5 | 设备 IO | D4 | 120 min | VGA/键盘/timer 测试 + super-mario 跑通 |
| D6a | NPC 接 ysyxSoC | D5, C1 (部分) | 90 min | ysyxSoC verilator 编过 |
| D6b | 综合可收敛 | D6a | 120 min | yosys 综合无 latch/无多驱动 |
| D6c | hello world on ysyxSoC | D6a | 60 min | grep "Hello World!" |
| D6d | 字符版超级玛丽 | D6c | 90 min | mario 输出关卡画面字符 |
| B5b | 流水线 + 冒险解决 | B5a | 240 min | pipelined NPC vs NEMU difftest 全过 |

完整 44 task 表见 `tasks.yaml` 自动生成。

### 7.3 总时间预估

```
工作时间 (中等学生)       42 个 task × 1-4 小时   ~270 小时
壁钟时间 (Claude 跑)      每 task 7-30 分钟 × 1.5 平均重试  ~20-50 小时
                          (含等待 claude API + 跑测试 + codex review)
预算 (USD)               每 task $1-3 × 1.5 重试  ~$80-200
                          (假设 cache 不命中, opus 4.7 价格 input $15/MT output $75/MT)
```


---

## 8. 风险与限制

### 8.1 已知风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| Codex 指出的"长会话不可托付"在 Python orchestrator 上不存在 | ✅ 已解决 | 外部进程, SQLite 持久化 |
| Claude API 长跑成本高 ($80-200) | 中 | `--max-budget-usd` 卡上限, 监控 |
| difftest 框架本身可能有 bug | 中 | 跑负例 (改一条指令看能不能抓住) |
| YSYX 官方测试集对某些角落 case 覆盖弱 | 高 | 补 negative tests, 跑 stress test |
| ysyxSoC verilator 跑超级玛丽要 ~30 分钟 | 低 | timeout 配宽, 用 SDRAM 而非 Flash 直跑 |
| A/S 阶段讲义陆续会发布, 现在做了后面要重做 | 高 | spec 明说**当前不覆盖**, 后续按需扩展 |
| 流片 ECOS Studio 账号问题 | 高 | spec 明说**不做真实流片**, 只到本地仿真验证 |
| LLM 在 RTL 调试时陷入死循环 | 高 | timeout + 引入 `hardware-debug-waveform` skill |
| 跑了一半发现 `tasks.yaml` 切错了 | 中 | event log 可回放, 可以局部 reset 重切 |

### 8.2 设计上明确的"不做"

- 不做实时进度推送 / Slack 通知 (Codex 议程的可选项, 用户没要求)
- 不做并发 task 执行 (顺序串行, 简单可控)
- 不做 worker pool 复用 (每个 task 独立 spawn, fresh context)
- 不做实时监控 dashboard (state 用 `make status` 查)
- 不做自动 publish 报告 (用户手动决定怎么用 `reports/`)

### 8.3 与 Codex review 意见的对照

Codex 提出的 6 大攻击点，本 spec 的应对：

| Codex 攻击点 | 应对 |
|---|---|
| 本会话当 orchestrator 是最脆弱的点 | ✅ 改为外部 Python orchestrator |
| 验证强度不够 (`exit + grep` 太弱) | ✅ 引入 difftest + 干净环境复跑 + immutable hash + 多步验证 |
| 27 task 按文档章节切是教学组织, 不是工程边界 | ✅ 重切为 44 个 task, 按"失败隔离性"+"独立可验证" |
| 流片准备被"一句带过" | ✅ D6 拆 4 个子 task (a/b/c/d), B 流片在 B5 后类似处理 |
| 边跑边装是无人值守高危设计 | ✅ Phase 0 一次性 bootstrap + env-lock.yaml |
| Subagent 返回 summary 太弱 | ✅ 强制 TASK_CONTRACT JSON, schema 校验, 不合规视为失败 |

未采纳的：

| Codex 建议 | 不采纳的理由 |
|---|---|
| 任务输入 hash 锁定 (文档切片 + golden) | 用户选择不上, 增加复杂度收益边际 |
| 性能/资源约束门槛 (例如频率趋势) | YSYX 主线没强要求, 后期可加 |
| 并发 / worker pool | 增加复杂度, 顺序串行已能完成 |

---

## 9. 验收（这份 spec 自己怎么算"OK"）

### 9.1 用户审阅完成后，spec 是 done 当且仅当：

1. ✅ 所有 9 节都没有 `TBD` / `TODO` / `[占位符]`
2. ✅ Codex review 提出的 6 个攻击点都有"应对"或"明确不应对的理由"
3. ✅ 用户在终端确认"接受这份 spec"
4. ✅ spec 文件已 commit 到 autoysyx 仓库 git 主分支

### 9.2 spec 之后的下一步

按 brainstorming skill 的流程：
- 调用 `superpowers:writing-plans` 把 spec 落到一份可执行的实施 plan
- 该 plan 会按顺序产出: `orchestrator/` 代码, `tools/bootstrap.sh`, `tasks.yaml`, `prompts/`, `test_runner/` 骨架
- 最后用 `python orchestrator/main.py bootstrap && python orchestrator/main.py run` 启动跑

### 9.3 何时本设计需要重新 brainstorm

- 如果 phase 0 跑完后, 发现工具链有不可解决的问题 (例如 mill 无法装上)
- 如果 D1a 第一次跑就失败 3 次, 提示 task 粒度还是太粗
- 如果用户在跑了 5 个 task 后发现根本性的方向错误
- 如果 YSYX 官方文档大改 (v24.07 升级)

---

## 附录 A: 决策记录

| 日期 | 决策 | 理由 | 谁 |
|---|---|---|---|
| 2026-05-20 | 范围限定 F-E-D-C-B + D6/B 流片准备 | 跳过 A/S (讲义未发) 和人工评审 | 用户 |
| 2026-05-20 | 产物 = 仓库 + 报告 + 可重跑脚本 | 平衡可信度与工作量 | 用户 |
| 2026-05-20 | 起点 = 官方 ysyx-workbench 模板 + 允许参考开源 | 不发明轮子 | 用户 |
| 2026-05-20 | 控制方式 = 一镚到底, 遇错才停 | 用户授权无人值守 | 用户 |
| 2026-05-20 | 环境 = 部分装了, 边跑边装 (后改为 phase-0 前置) | Codex 指出"边跑边装"是高危 | 用户 + Codex |
| 2026-05-20 | Orchestrator 位置 = 外部 Python (非本会话) | Codex 指出长会话不可托付 | 用户 + Codex |
| 2026-05-20 | 验证策略 = difftest + 结构化 contract + 前置 bootstrap | 采纳 Codex 3/4 建议 (hash-lock 未采纳) | 用户 + Codex |
| 2026-05-20 | Task 切法 = 按"失败隔离" 44 个, 不按教学章节 27 个 | Codex 建议 | 用户 + Codex |

## 附录 B: 引用资源

- YSYX 官方文档（已下载）: `docs-md/2407/`, `docs-md/ics-pa/`
- YSYX 课程主页: https://ysyx.oscc.cc/docs/2407/
- ysyx-workbench (起点): https://github.com/OSCPU/ysyx-workbench
- ysyxSoC (流片用): https://github.com/OSCPU/ysyxSoC
- humanize skill (调度模式参考): https://github.com/humania/humanize
- superpowers skills (subagent / verification / TDD)
- 《计算机系统——基于 RISC-V+Linux 平台》袁春风 余子濠 陈璐 编著
- 《RISC-V 开放架构设计之道》Patterson, Waterman

---

*文档结束*
