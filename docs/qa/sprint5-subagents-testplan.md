# Sprint 5 QA 测试计划：Subagents 并行编排

> 对应开发文档：`docs/archive/legacy/HERMES_PARITY_SPRINT_PLAN.zh-CN.md` §Sprint 5
> 对应 backlog：`docs/archive/legacy/HERMES_PARITY_BACKLOG.zh-CN.md` §Epic S5
> 执行命令入口：`python3 -m pytest -q cai-agent/tests/test_workflow*.py`
> **开发状态（2026-04-23）**：**S5-03**（`on_error`）与 **S5-04**（`budget_max_tokens` + `budget_used`/`budget_limit`/`budget_exceeded` + root **`quality_gate`** 后置门禁）已在 `cai_agent/workflow.py` 落地；自动化见 `cai-agent/tests/test_cli_workflow.py`。

---

## 1. 测试范围

| 功能 | 命令/配置 | 测试重点 |
|------|----------|---------|
| workflow 并行 stage | `workflow.json` + `parallel: true` | 并行分组解析与执行 |
| fan-out/fan-in 聚合 | `merge_strategy` 配置 | 合并策略正确性 |
| fail-fast / continue-on-error | `on_error` 配置 | 失败传播策略 |
| 预算门禁 | `budget_max_tokens` 配置 | 超预算中止行为 |
| 后置质量门禁 | `quality_gate` 配置 | workflow 成功后执行 quality-gate，失败时回写 workflow 状态 |

---

## 2. 测试用例

### SAG-PAR-001：串行 workflow（对照组，确保不退化）
- **配置**：3 个无 `parallel` 标记的步骤
- **执行**：`cai-agent workflow workflow.json --json`
- **期望**：步骤按顺序执行，输出顺序与定义一致

### SAG-PAR-002：两个并行步骤同组执行
- **配置**：2 个步骤标记 `parallel: true`，`group: "analysis"`
- **执行**：`cai-agent workflow workflow.json --json`
- **期望**：
  - 两步均执行
  - 总耗时 ≤ 单步最大耗时 × 1.5（并行加速）
  - 输出中每个步骤有独立 `result`

### SAG-PAR-003：并行步骤 + 串行步骤混合
- **配置**：步骤 A（串行）→ B+C（并行）→ D（串行）
- **执行**：`cai-agent workflow workflow.json --json`
- **期望**：A 先完成，B+C 并行，D 在 B+C 之后执行

### SAG-PAR-004：并行组内步骤独立，互不影响
- **执行**：并行 B 失败（fail-fast 关闭），C 正常
- **期望**：C 的结果不受 B 失败影响

### SAG-AGG-001：`concat` 合并策略
- **配置**：`merge_strategy: concat`
- **执行**：2 个并行步骤，各产出 answer
- **期望**：合并结果为两个 answer 拼接，顺序稳定（按步骤定义顺序）

### SAG-AGG-002：`last_wins` 合并策略
- **配置**：`merge_strategy: last_wins`
- **执行**：同上
- **期望**：合并结果为最后完成的步骤的 answer

### SAG-AGG-003：`best_of` 合并策略（按 score）
- **配置**：`merge_strategy: best_of`，每步返回 `score` 字段
- **执行**：两步骤 score 分别为 0.4 和 0.9
- **期望**：合并结果取 score=0.9 的步骤输出

### SAG-AGG-004：合并结果写入 session 文件
- **执行**：`workflow --json` 完成后
- **期望**：会话文件中 `answer` 为合并后结果，包含各步骤 trace

### SAG-ERR-001：`fail_fast` 策略下子任务失败立即中止
- **配置**：`on_error: fail_fast`，B 步骤失败
- **执行**：`cai-agent workflow workflow.json --json`
- **期望**：C 不执行，整体 exit 2，B 的 error 包含在输出中

### SAG-ERR-002：`continue_on_error` 策略下失败不阻断
- **配置**：`on_error: continue_on_error`，B 步骤失败
- **执行**：`cai-agent workflow workflow.json --json`
- **期望**：C 正常执行，merge 阶段跳过 B，exit 0

### SAG-ERR-003：默认策略为 `fail_fast`
- **配置**：`on_error` 未设置
- **执行**：子任务失败
- **期望**：行为等同 `fail_fast`

### SAG-BUDGET-001：超预算时中止未启动任务
- **配置**：`budget_max_tokens: 100`，两个任务，第 1 个消耗 80 tokens
- **执行**：`cai-agent workflow workflow.json --json`
- **期望**：第 2 个任务不执行，输出 `budget_exceeded=true`

### SAG-BUDGET-002：预算充足时正常执行
- **配置**：`budget_max_tokens: 99999`
- **执行**：`cai-agent workflow workflow.json --json`
- **期望**：所有任务执行，`budget_exceeded=false`

### SAG-BUDGET-003：已运行任务的结果不因超预算丢失
- **执行**：超预算中止后
- **期望**：已运行步骤的 result 保留在输出中

---

## 3. 边界与异常用例

### SAG-PAR-005：单个步骤也标记 parallel（降级为串行）
- **配置**：只有 1 个步骤，标记 `parallel: true`
- **期望**：正常执行，不报错

### SAG-PAR-006：并行步骤数量超过系统默认并发限制
- **配置**：10 个并行步骤，`--max-concurrent=3`
- **期望**：最多 3 个同时执行，其余排队，全部最终完成

---

## 4. 回归关联

```bash
python3 -m pytest -q cai-agent/tests/test_workflow*.py
```

---

## 5. 验收信号

- SAG-PAR-001~004、SAG-AGG-001~004 全部通过
- SAG-ERR-001~003 通过
- workflow 并行配置在 README 有示例和 schema 说明
