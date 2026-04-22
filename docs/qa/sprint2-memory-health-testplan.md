# Sprint 2 QA 测试计划：Memory Loop 2.0（质量治理）

> 对应开发文档：`docs/HERMES_PARITY_SPRINT_PLAN.zh-CN.md` §Sprint 2  
> 对应 backlog：`docs/HERMES_PARITY_BACKLOG.zh-CN.md` §Epic S2  
> 执行命令入口：`python3 -m pytest -q cai-agent/tests/test_memory_health*.py`

---

## 1. 测试范围

| 功能 | 命令 | 测试重点 |
|------|------|---------|
| memory health 评分 | `memory health --json` | 输出结构、三档分级 |
| freshness 指标 | `memory health --freshness-days N` | 时间窗口过滤正确性 |
| conflict_rate 指标 | `memory health --conflict-threshold` | 阈值可配置、冲突对样例 |
| coverage 指标 | `memory health --days N` | 会话-记忆覆盖率计算 |
| nudge-report health_score | `memory nudge-report --json` | 字段存在性与类型 |
| CI 门禁 | `memory health --fail-on-grade C` | 退出码 0/2 |

---

## 2. 测试用例

### MEM-HLTH-001：health 命令基础输出结构
- **前置条件**：工作区有若干 session 文件和 entries.jsonl
- **执行**：`cai-agent memory health --json`
- **期望**：
  - exit 0
  - JSON 包含：`schema_version="1.0"`、`health_score`（0.0~1.0）、`grade`（A/B/C/D）
  - 包含子项：`freshness`、`coverage`、`conflict_rate`

### MEM-HLTH-002：空工作区的基础输出
- **前置条件**：临时空目录
- **执行**：`cai-agent memory health --json`
- **期望**：
  - exit 0
  - `health_score=0.0`、`grade=D`
  - `coverage=0.0`、`freshness=0.0`

### MEM-HLTH-003：健康状态分档（A 档）
- **前置条件**：近期有大量 session，entries.jsonl 有足量条目且近期创建，无重复
- **执行**：`cai-agent memory health --json`
- **期望**：`grade=A`，`health_score >= 0.8`

### MEM-HLTH-004：健康状态分档（D 档）
- **前置条件**：大量旧 session，entries.jsonl 为空
- **执行**：`cai-agent memory health --json`
- **期望**：`grade=D`，`health_score <= 0.2`

### MEM-HLTH-005：`--fail-on-grade C` 门禁（触发）
- **前置条件**：健康状态为 D
- **执行**：`cai-agent memory health --json --fail-on-grade C`
- **期望**：exit 2

### MEM-HLTH-006：`--fail-on-grade C` 门禁（不触发）
- **前置条件**：健康状态为 A
- **执行**：`cai-agent memory health --json --fail-on-grade C`
- **期望**：exit 0

### MEM-HLTH-007：文本模式输出（非 JSON）
- **执行**：`cai-agent memory health`
- **期望**：
  - exit 0
  - 输出包含 grade/score 可读文本
  - 输出包含至少一条建议动作

### MEM-FSH-001：freshness 窗口过滤
- **前置条件**：entries.jsonl 中有 2 条近 7 天、3 条超过 30 天的条目
- **执行**：`cai-agent memory health --json --freshness-days 14`
- **期望**：`freshness <= 0.5`（只有 2/5 条在窗口内）

### MEM-FSH-002：freshness=1.0（全部新鲜）
- **前置条件**：所有条目均在近 7 天内创建
- **执行**：`cai-agent memory health --json --freshness-days 7`
- **期望**：`freshness=1.0`

### MEM-CFT-001：conflict_rate 检测
- **前置条件**：entries.jsonl 中有两条文本内容高度相似（>85%）
- **执行**：`cai-agent memory health --json`
- **期望**：`conflict_rate > 0`，`conflict_pairs` 包含至少 1 对

### MEM-CFT-002：conflict_rate=0.0（无冲突）
- **前置条件**：所有条目内容完全不同
- **执行**：`cai-agent memory health --json`
- **期望**：`conflict_rate=0.0`

### MEM-CFT-003：`--conflict-threshold` 可配置
- **前置条件**：两条相似度约 0.7 的条目
- **执行**：
  - `cai-agent memory health --json --conflict-threshold 0.6`（期望检测到）
  - `cai-agent memory health --json --conflict-threshold 0.9`（期望未检测到）
- **期望**：结果按阈值不同而变化

### MEM-COV-001：coverage 计算正确性
- **前置条件**：5 个 session，2 个已有对应 memory 条目
- **执行**：`cai-agent memory health --json --days 30`
- **期望**：`coverage` 约为 0.4

### MEM-NDG-020：nudge-report health_score 字段
- **前置条件**：已存在 nudge-history.jsonl
- **执行**：`cai-agent memory nudge-report --json`
- **期望**：JSON 包含 `health_score`（数值或 null）、`schema_version="1.2"`

---

## 3. 边界与异常用例

### MEM-HLTH-008：损坏的 entries.jsonl
- **前置条件**：entries.jsonl 中有无效 JSON 行
- **执行**：`cai-agent memory health --json`
- **期望**：exit 0，`memory_warnings` 非空，健康分有所降低

### MEM-HLTH-009：超大量条目（性能）
- **前置条件**：entries.jsonl 中有 1000 条有效条目
- **执行**：`cai-agent memory health --json`
- **期望**：exit 0，耗时 < 5s

### MEM-HLTH-010：并发调用（只读安全性）
- **执行**：并发运行两次 `cai-agent memory health --json`
- **期望**：两次均 exit 0，不产生文件冲突

---

## 4. 回归关联

本 Sprint 完成后，以下已有测试必须全部通过：

```bash
python3 -m pytest -q cai-agent/tests/test_memory_nudge_cli.py
python3 -m pytest -q cai-agent/tests/test_memory_nudge_report_cli.py
python3 -m pytest -q cai-agent/tests/test_memory_entries_bundle.py
python3 -m pytest -q cai-agent/tests/test_memory_entry_validate.py
```

---

## 5. 验收信号

- 所有 P1 用例通过
- P2 用例通过率 ≥ 80%
- memory health 命令在 README 有示例
- CHANGELOG 有对应 entry
