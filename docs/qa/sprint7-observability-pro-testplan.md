# Sprint 7 QA 测试计划：Observability Pro（运营看板）

> 对应开发文档：`docs/archive/legacy/HERMES_PARITY_SPRINT_PLAN.zh-CN.md` §Sprint 7
> 对应 backlog：`docs/archive/legacy/HERMES_PARITY_BACKLOG.zh-CN.md` §Epic S7

---

## 1. 测试范围

| 功能 | 命令 | 测试重点 |
|------|------|---------|
| 统一指标模型 | 各模块事件输出 | 字段完整性、类型正确性 |
| observe report | `observe report --format markdown/json` | 内容准确、格式可解析 |
| 跨域关联洞察 | `insights --cross-domain --json` | 趋势数据对齐 |
| 运营看板导出 | `observe export --format csv/json/markdown` | 格式合规性 |

---

## 2. 测试用例

### OBS-METRICS-001：metrics 事件字段完整
- **前置条件**：运行一次 `recall`，记录事件
- **期望**：事件包含 `ts`、`module`、`event`、`latency_ms`、`success`

### OBS-METRICS-002：各模块事件 module 字段正确
- **期望**：
  - recall 事件：`module=recall`
  - memory 事件：`module=memory`
  - schedule 事件：`module=schedule`
  - gateway 事件：`module=gateway`

### OBS-METRICS-003：`success=true/false` 语义正确
- **前置条件**：一次成功执行 + 一次失败执行
- **期望**：成功时 `success=true`，失败时 `success=false`

### OBS-RPT-001：`observe report` JSON 基础结构
- **执行**：`cai-agent observe report --days 7 --format json`
- **期望**：包含 `schema_version="1.0"`、`session_count`、`success_rate`、`token_total`、`tool_error_rate`

### OBS-RPT-002：`observe report --format markdown` 可读性
- **执行**：`cai-agent observe report --days 7 --format markdown`
- **期望**：输出为有效 Markdown，包含标题、表格、数值

### OBS-RPT-003：空数据时报告返回零值而非崩溃
- **前置条件**：无任何会话记录
- **执行**：`cai-agent observe report --format json`
- **期望**：exit 0，`session_count=0`，`success_rate=1.0`（无失败样本时的默认）

### OBS-RPT-004：`top_failing_tools` 正确排序
- **前置条件**：tool A 失败 5 次，tool B 失败 2 次
- **执行**：`cai-agent observe report --format json`
- **期望**：`top_failing_tools[0].tool = A`

### OBS-RPT-005：`--days` 时间窗口过滤正确
- **前置条件**：有 7 天前和 14 天前的会话各一组
- **执行**：
  - `observe report --format json --days 10`（期望只包含 7 天前那组）
  - `observe report --format json --days 20`（期望两组都包含）

### OBS-CROSS-001：跨域洞察输出三条趋势序列
- **前置条件**：有 memory/recall/schedule 的历史数据
- **执行**：`cai-agent insights --json --cross-domain --days 14`
- **期望**：包含 `recall_hit_rate_trend`、`memory_health_trend`、`schedule_success_trend`（均为数组）

### OBS-CROSS-002：趋势数组按时间升序排列
- **执行**：同上
- **期望**：每个趋势数组中的 `ts` 字段按升序排列

### OBS-EXP-001：`observe export --format csv`
- **执行**：`cai-agent observe export --format csv --days 30 -o out.csv`
- **期望**：生成合法 CSV，首行为列名，包含日期/session_count/success_rate 等列

### OBS-EXP-002：`observe export --format json`
- **执行**：`cai-agent observe export --format json --days 30 -o out.json`（根对象 **`observe_export_v1`**，按日数据在 **`rows`**）
- **期望**：合法 JSON 数组，每项为一天的汇总数据

### OBS-EXP-003：`observe export --format markdown`
- **执行**：`cai-agent observe export --format markdown --days 30 -o out.md`
- **期望**：合法 Markdown 表格，可直接粘贴至文档

---

## 3. 边界与异常用例

### OBS-RPT-006：同输入多次运行输出一致（确定性）
- **执行**：同一数据集运行两次 `observe report --format json`
- **期望**：输出完全一致（JSON 字段值相同）

### OBS-EXP-004：目标文件不可写时报错
- **前置条件**：目标路径无写权限
- **执行**：`observe export -o /root/readonly.csv`
- **期望**：exit 2，清晰错误信息，不产生部分文件

---

## 4. 回归关联

```bash
python3 -m pytest -q cai-agent/tests/test_insights_cli.py
python3 -m pytest -q cai-agent/tests/test_observe*.py
```

---

## 5. 验收信号

- OBS-RPT-001~005 全部通过
- OBS-CROSS-001~002 通过
- OBS-EXP-001~003 通过
- observe report 在 README 有使用示例
