# Sprint 3 QA 测试计划：Recall Loop 2.0（质量 + 可解释性）

> 对应开发文档：`docs/HERMES_PARITY_SPRINT_PLAN.zh-CN.md` §Sprint 3  
> 对应 backlog：`docs/HERMES_PARITY_BACKLOG.zh-CN.md` §Epic S3  
> 执行命令入口：`python3 -m pytest -q cai-agent/tests/test_recall*.py`

---

## 1. 测试范围

| 功能 | 命令 | 测试重点 |
|------|------|---------|
| recall 排序策略 | `recall --sort combined` | 排序结果一致性与可预测性 |
| 无命中解释 | `recall --query X` (0 命中) | `no_hit_reason` 字段枚举 |
| 索引体检 | `recall-index doctor` | 检测损坏/过期/缺失文件 |
| 性能基准 | `scripts/perf_recall_bench.py` | 大规模延迟阈值 |

---

## 2. 测试用例

### RCL-RANK-001：`--sort recent`（默认）与时间顺序一致
- **前置条件**：3 个会话，时间各不同，均命中关键词
- **执行**：`cai-agent recall --query "test" --json`
- **期望**：`results` 列表按 `mtime` 降序排列

### RCL-RANK-002：`--sort density` 命中密度优先
- **前置条件**：A 会话命中 5 次（旧）、B 会话命中 1 次（新）
- **执行**：`cai-agent recall --query "test" --sort density --json`
- **期望**：A 排在 B 前面（命中更密集优先）

### RCL-RANK-003：`--sort combined` 混合策略
- **前置条件**：同上
- **执行**：`cai-agent recall --query "test" --sort combined --json`
- **期望**：排序结果与 `--sort recent` 和 `--sort density` 均不同（体现综合权衡）

### RCL-RANK-004：排序不改变命中总数
- **执行**：同一查询分别用 `--sort recent/density/combined`
- **期望**：三次 `hits_total` 相同

### RCL-RANK-005：相同命中密度时按时间打破平局
- **前置条件**：两会话命中次数相同，A 更新
- **执行**：`--sort density`
- **期望**：A 排在前面（时间作为 tiebreak）

### RCL-RANK-006：`--sort` 错误值处理
- **执行**：`cai-agent recall --query "test" --sort invalid_value`
- **期望**：exit 2，错误信息说明可选值

### RCL-NOHIT-001：窗口太窄导致无命中
- **前置条件**：所有会话均在 30 天前
- **执行**：`cai-agent recall --query "test" --days 1 --json`
- **期望**：`hits_total=0`，`no_hit_reason="window_too_narrow"`

### RCL-NOHIT-002：关键词不匹配
- **前置条件**：有会话但内容不含查询词
- **执行**：`cai-agent recall --query "xxxxxxuniquexxx" --json`
- **期望**：`no_hit_reason="pattern_no_match"`

### RCL-NOHIT-003：索引为空
- **前置条件**：使用 `--use-index`，但索引文件不存在
- **执行**：`cai-agent recall --query "test" --use-index --json`
- **期望**：`no_hit_reason="index_empty"` 或 exit 2 + 提示先 build

### RCL-NOHIT-004：所有会话均解析失败
- **前置条件**：所有 session 文件均不可解析（空文件或乱码）
- **执行**：`cai-agent recall --query "test" --json`
- **期望**：`no_hit_reason="all_skipped"`，`parse_skipped > 0`

### RCL-NOHIT-005：文本模式下无命中提示可读
- **执行**：`cai-agent recall --query "xxxxxxuniquexxx"`
- **期望**：exit 0，输出人类可读提示（如"无命中：关键词可能不匹配，建议扩宽时间窗口"）

### RCL-DOC-001：健康索引的 doctor 输出
- **前置条件**：已 build 索引，session 文件均存在
- **执行**：`cai-agent recall-index doctor --json`
- **期望**：`is_healthy=true`，`issues=[]`，exit 0

### RCL-DOC-002：索引含已删除文件路径
- **前置条件**：build 索引后删除一个 session 文件
- **执行**：`cai-agent recall-index doctor --json`
- **期望**：`is_healthy=false`，`missing_files` 包含被删路径，exit 2

### RCL-DOC-003：索引 schema 版本不匹配
- **前置条件**：手动修改索引 `recall_index_schema_version` 为不支持的值
- **执行**：`cai-agent recall-index doctor --json`
- **期望**：`schema_version_ok=false`，`issues` 包含版本告警

### RCL-DOC-004：`--fix` 自动修复（删除失效路径）
- **前置条件**：索引含已删除文件路径
- **执行**：`cai-agent recall-index doctor --fix --json`
- **期望**：exit 0，`fixed` 字段包含删除的路径数

### RCL-DOC-005：索引文件不存在时 doctor
- **前置条件**：无索引文件
- **执行**：`cai-agent recall-index doctor --json`
- **期望**：exit 2，`issues` 包含"索引文件不存在"

### RCL-DOC-006：doctor 对比 info 输出一致性
- **前置条件**：健康索引
- **执行**：`doctor --json` 与 `info --json`
- **期望**：`sessions_indexed` 字段值一致

---

## 3. 性能测试

### PERF-RCL-001：10 文件扫描延迟
- **执行**：`python3 scripts/perf_recall_bench.py --sessions 10`
- **期望**：scan 延迟 < 500ms

### PERF-RCL-002：50 文件扫描延迟
- **执行**：`python3 scripts/perf_recall_bench.py --sessions 50`
- **期望**：scan 延迟 < 2s

### PERF-RCL-003：200 文件扫描延迟
- **执行**：`python3 scripts/perf_recall_bench.py --sessions 200`
- **期望**：scan 延迟 < 5s

### PERF-RCL-004：索引搜索延迟
- **执行**：200 文件索引后执行 `recall-index search`
- **期望**：搜索延迟 < 500ms

### PERF-RCL-005：增量刷新延迟（mtime 未变跳过）
- **执行**：建立 200 文件索引，不修改任何文件，执行 `recall-index refresh`
- **期望**：跳过所有文件，耗时 < 200ms

---

## 4. 回归关联

```bash
python3 -m pytest -q cai-agent/tests/test_recall_cli.py
python3 -m pytest -q cai-agent/tests/test_recall_index_cli.py
```

---

## 5. 验收信号

- RCL-RANK-001~006、RCL-NOHIT-001~005、RCL-DOC-001~006 全部通过
- 性能基准脚本可独立执行并产出报告
- `recall-index doctor` 在 README 有使用示例
