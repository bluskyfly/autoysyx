# autoysyx

外部 Python orchestrator, 用于让 Claude (claude-opus-4-7) 自动通关一生一芯
v24.07 的 F-E-D-C-B 五阶段技术任务. 详见
`docs/superpowers/specs/2026-05-20-autoysyx-design.md`.

## 快速开始

1. 装环境 (~30 min, 需要 sudo):
   ```
   make bootstrap
   ```
   会装 `gcc-riscv64-linux-gnu`, `qemu-system-riscv64`, `mill`, clone
   `ysyx-workbench` + `ysyxSoC`, 然后写 `tools/env-lock.yaml`.

2. 开跑 (长跑数小时到几十小时):
   ```
   make run
   ```

3. 查进度:
   ```
   make status
   ```

4. 失败暂停时, 你可以:
   - `python -m orchestrator.main skip <task>` 跳过
   - `python -m orchestrator.main retry <task>` 重置 attempts
   - 修改 `tasks.yaml` 后再 `make run` 接着跑

## 状态恢复

orchestrator 把所有状态写在 SQLite (`orchestrator/state.db`).
进程死掉, terminal 关掉, 重启机器, 都不影响 `make run` 继续推进.

## 自检

```
make test
```

跑 pytest, 含 db / tasks / worker / verifier / reviewer / reporter / dry_run
共约 67 个测试, 应在 2 分钟内跑完.

## 设计原则

- 文档为准 (`docs-md/` 是规格唯一来源)
- 外部 orchestrator (不依赖单 chat session 寿命)
- 反 LLM 自欺自骗 10 条规则
- difftest 在 D/C/B 阶段贯穿
- 状态 = SQLite append-only event log

详见 spec.
