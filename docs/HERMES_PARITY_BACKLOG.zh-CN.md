# Hermes 对齐可执行 Backlog

> 导入格式说明：本文档可逐行导入 Jira / Linear / Notion 等工具。  
> 字段：**ID · Epic · Story · 验收标准（AC）· 优先级 · 测试用例 ID · 依赖 · 估算量级**  
>
> 优先级说明：  
> - `P0` 阻断发布  
> - `P1` 本 Sprint 必完成  
> - `P2` 本 Sprint 尽力完成  
> - `P3` 下 Sprint 排入  
>
> 估算量级说明：S = 半天内 / M = 1~2天 / L = 3~5天 / XL = 5天以上

---

## Epic S1：Parity 基线收敛

### S1-01 命令参数命名一致性审计
- **Story**：作为开发者，我希望所有命令都使用一致的参数命名约定（`--json`/`--days`/`--limit` 等），这样文档和自动化脚本不需要记不同的别名。
- **AC**：
  1. 执行 `cai-agent <cmd> --help` 所有参数与 README 示例完全一致。
  2. `--json` 在所有命令中行为一致（结构化输出，exit 0）。
  3. `--days`、`--limit`、`--index-path`、`--history-file` 命名无歧义。
- **优先级**：P1
- **测试用例 ID**：BASE-001 ~ BASE-005
- **依赖**：无
- **估算**：M

### S1-02 JSON 输出 schema 版本文档化
- **Story**：作为 QA/集成方，我希望有一份稳定的 schema 字典，明确每个命令 JSON 输出的字段、类型和版本号，以便编写稳定的契约测试。
- **AC**：
  1. `docs/schema/` 目录下每个命令有一份 schema 描述（字段/类型/版本/示例）。
  2. `schema_version` 字段在破坏性变更时必须升级。
  3. README 表格更新补充 schema 版本说明。
- **优先级**：P1
- **测试用例 ID**：BASE-006 ~ BASE-010
- **依赖**：S1-01
- **估算**：M

### S1-03 错误码规范与退出码一致
- **Story**：作为 CI 消费者，我希望所有命令在失败时返回可预测的非 0 退出码，方便脚本捕捉。
- **AC**：
  1. 正常：exit 0；逻辑错误（阈值/空结果）：exit 2；CLI 解析错误：exit 2。
  2. 所有 `--fail-on-*` 参数遵循统一语义。
  3. 补齐错误码文档。
- **优先级**：P1
- **测试用例 ID**：BASE-011 ~ BASE-015
- **依赖**：S1-01
- **估算**：S

### S1-04 Parity Matrix 更新与 backlog 冻结
- **Story**：作为产品，我希望有一份最新的能力对齐矩阵，知道哪些已完成、哪些是 Gap，方便排期。
- **AC**：
  1. `docs/PARITY_MATRIX.zh-CN.md` 按 A~J 能力域填写 Done / In Progress / Gap。
  2. Gap 项全部登记到本 backlog。
- **优先级**：P1
- **测试用例 ID**：（文档验证，无自动化用例）
- **依赖**：无
- **估算**：S

---

## Epic S2：Memory Loop 2.0

### S2-01 memory health 统一评分命令
- **Story**：作为运营/QA，我希望用一条命令获得当前工作区的记忆健康综合评分，不需要手动看多个指标。
- **AC**：
  1. `cai-agent memory health --json` 输出 `health_score`（0.0~1.0）、`grade`（A/B/C/D）、分项指标（freshness/coverage/conflict_rate）。
  2. `--fail-on-grade C` 可用于 CI 门禁。
  3. 有效 schema 版本 `1.0`。
- **优先级**：P1
- **测试用例 ID**：MEM-HLTH-001 ~ MEM-HLTH-010
- **依赖**：S1-01
- **估算**：L

### S2-02 freshness 指标（记忆新鲜度）
- **Story**：作为开发者，我希望知道当前记忆条目中有多少是近期产生的，以判断是否需要重新 extract。
- **AC**：
  1. `freshness` = 最近 N 天内创建的条目占总条目比。
  2. 可通过 `--freshness-days` 配置窗口（默认 14）。
  3. 结果在 `memory health` 与 `nudge-report` 中体现。
- **优先级**：P1
- **测试用例 ID**：MEM-FSH-001 ~ MEM-FSH-005
- **依赖**：S2-01
- **估算**：M

### S2-03 conflict_rate 指标（记忆冲突率）
- **Story**：作为 QA，我希望检测记忆中是否存在主题/内容高度重叠的条目，便于触发去重流程。
- **AC**：
  1. `conflict_rate` = 相似度超过阈值的条目对数 / 总条目数。
  2. 阈值可配置（`--conflict-threshold`，默认 0.85 基于简单 n-gram 重叠）。
  3. `memory health` 输出中包含 `conflict_pairs` 样例（最多 3 对）。
- **优先级**：P2
- **测试用例 ID**：MEM-CFT-001 ~ MEM-CFT-005
- **依赖**：S2-01
- **估算**：L

### S2-04 coverage 指标（会话-记忆覆盖率）
- **Story**：作为运营，我希望知道最近的会话中有多少已被提炼成结构化记忆，避免经验流失。
- **AC**：
  1. `coverage` = 有 memory 条目的会话数 / 近期总会话数。
  2. 窗口与 `--days` 对齐。
  3. 纳入 `memory health` 输出。
- **优先级**：P2
- **测试用例 ID**：MEM-COV-001 ~ MEM-COV-005
- **依赖**：S2-01，S2-02
- **估算**：M

### S2-05 nudge-report 增加 health_score 字段
- **Story**：作为自动化消费方，我希望 `nudge-report` 的输出里直接包含最新健康评分，不用额外调用 `memory health`。
- **AC**：
  1. `nudge-report --json` 增加 `health_score` 字段（可选，若无 health 数据返回 null）。
  2. schema_version 升级到 `1.2`。
- **优先级**：P2
- **测试用例 ID**：MEM-NDG-020 ~ MEM-NDG-025
- **依赖**：S2-01
- **估算**：S

---

## Epic S3：Recall Loop 2.0

### S3-01 recall 排序策略升级（时间衰减 + 命中密度）
- **Story**：作为用户，我希望 recall 搜索结果排在最前面的是"更近且命中更集中"的会话，而不是简单按文件时间。
- **AC**：
  1. 增加 `--sort` 选项：`recent`（默认）/ `density`（命中密度优先）/ `combined`（时间衰减*密度）。
  2. 相同输入下 `--sort combined` 与 `--sort recent` 结果顺序可能不同，且有测试覆盖。
  3. 性能回归：大规模数据集（100+ 会话）延迟不超过前版 50%。
- **优先级**：P1
- **测试用例 ID**：RCL-RANK-001 ~ RCL-RANK-010
- **依赖**：S1-01
- **估算**：L

### S3-02 无命中解释（explain-no-hit）
- **Story**：作为用户，当 recall 返回 0 命中时，我希望得到可操作的解释（比如"时间窗口太窄"或"关键词不匹配"），而不是一个空列表。
- **AC**：
  1. 无命中时 JSON 输出增加 `no_hit_reason`（枚举：`window_too_narrow` / `pattern_no_match` / `index_empty` / `all_skipped`）。
  2. 文本模式打印可读提示。
  3. 有 3 种原因的测试用例。
- **优先级**：P1
- **测试用例 ID**：RCL-NOHIT-001 ~ RCL-NOHIT-010
- **依赖**：S1-01
- **估算**：M

### S3-03 recall-index doctor（索引体检命令）
- **Story**：作为运维，我希望能快速诊断当前索引文件的健康状况（是否损坏/过期/与实际文件不一致）。
- **AC**：
  1. `cai-agent recall-index doctor --json` 输出：`is_healthy`、`issues`（列表）、`stale_paths`、`missing_files`、`schema_version_ok`。
  2. `--fix` 可自动删除失效路径（等价于 `refresh --prune`）。
  3. exit 0 = 健康；exit 2 = 发现问题。
- **优先级**：P1
- **测试用例 ID**：RCL-DOC-001 ~ RCL-DOC-010
- **依赖**：S1-01
- **估算**：M

### S3-04 recall 性能基准测试
- **Story**：作为 QA，我希望有一套可重复运行的基准，量化 recall/recall-index 在不同数据规模下的延迟，以便检测回归。
- **AC**：
  1. `scripts/perf_recall_bench.py`：生成 10/50/200 个会话文件，测量 scan/index/search 延迟。
  2. 输出 Markdown 报告，可落盘 `docs/qa/runs/`。
  3. 200 文件 scan < 5s，index search < 500ms（参考阈值，可调整）。
- **优先级**：P2
- **测试用例 ID**：PERF-RCL-001 ~ PERF-RCL-005
- **依赖**：S3-01
- **估算**：M

---

## Epic S4：Scheduler 2.0

### S4-01 任务失败重试与指数退避
- **Story**：作为运维，我希望失败的定时任务能自动按指数退避重试，而不是直接标为"failed"放弃。
- **AC**：
  1. `.cai-schedule.json` 任务增加 `max_retries`（默认 3）、`retry_count`、`next_retry_at`。
  2. daemon 在任务失败后按 `2^retry_count * 60s` 延迟重新入队。
  3. 达到上限后状态为 `failed_exhausted`。
- **优先级**：P1
- **测试用例 ID**：SCH-RETRY-001 ~ SCH-RETRY-010
- **依赖**：S1-03
- **估算**：L

### S4-02 并发控制（全局/任务级）
- **Story**：作为运维，我希望 daemon 不会同时运行超过 N 个任务，避免资源竞争和 LLM 并发超限。
- **AC**：
  1. `schedule daemon --max-concurrent <N>`（默认 1）。
  2. 超限时多余任务排队，当前轮次不执行，下轮再判断。
  3. 日志中记录 `skipped_due_to_concurrency` 事件。
- **优先级**：P1
- **测试用例 ID**：SCH-CONC-001 ~ SCH-CONC-008
- **依赖**：S4-01
- **估算**：L

### S4-03 任务依赖（A 完成后执行 B）
- **Story**：作为开发者，我希望能声明任务依赖关系，让 memory extract 在 recall-index refresh 完成后才执行。
- **AC**：
  1. `schedule add --depends-on <task-id>`。
  2. daemon 执行前检查依赖任务的 `last_status`，未完成则跳过当前任务。
  3. `schedule list` 显示依赖链。
- **优先级**：P2
- **测试用例 ID**：SCH-DEP-001 ~ SCH-DEP-008
- **依赖**：S4-01，S4-02
- **估算**：L

### S4-04 执行审计日志统一 schema
- **Story**：作为 QA/运维，我希望 schedule 的 JSONL 日志每行格式一致，方便用 jq / 日志系统解析。
- **AC**：
  1. JSONL 事件类型统一：`task.started` / `task.completed` / `task.failed` / `task.retrying` / `task.skipped` / `daemon.cycle`。
  2. 每行包含：`ts`（ISO）、`event`、`task_id`、`goal_preview`、`elapsed_ms`、`error`（可选）。
  3. 文档补充 schema 说明。
- **优先级**：P1
- **测试用例 ID**：SCH-AUDIT-001 ~ SCH-AUDIT-008
- **依赖**：S4-01
- **估算**：M

### S4-05 任务 SLA 指标与报告
- **Story**：作为运营，我希望能看到每个任务的成功率/平均耗时/P95耗时，判断稳定性。
- **AC**：
  1. `schedule stats --json` 输出：per-task success_rate/avg_elapsed_ms/p95_elapsed_ms/run_count/fail_count。
  2. 支持 `--days` 时间窗口。
- **优先级**：P2
- **测试用例 ID**：SCH-SLA-001 ~ SCH-SLA-005
- **依赖**：S4-04
- **估算**：M

---

## Epic S5：Subagents 并行编排

### S5-01 workflow schema 增加并行阶段（parallel stage）
- **Story**：作为开发者，我希望在 workflow.json 里声明哪些 step 可以并行运行，减少总耗时。
- **AC**：
  1. workflow step 增加 `parallel: true`，同 `group` 的步骤并发执行。
  2. 串行步骤仍按顺序执行。
  3. 有单元测试覆盖并行分组解析。
- **优先级**：P1
- **测试用例 ID**：SAG-PAR-001 ~ SAG-PAR-010
- **依赖**：S4-02（并发控制）
- **估算**：L

### S5-02 fan-out/fan-in 结果聚合
- **Story**：作为用户，我希望并行子任务的结果能自动汇总为一份摘要，不需要手动合并。
- **AC**：
  1. 并行步骤执行完后进入一个 `merge` 阶段，汇总所有子任务 answer。
  2. 支持合并策略：`concat`（拼接）/ `last_wins`（取最后）/ `best_of`（按 score 取最高）。
  3. 汇总结果写入 session 文件。
- **优先级**：P1
- **测试用例 ID**：SAG-AGG-001 ~ SAG-AGG-010
- **依赖**：S5-01
- **估算**：L

### S5-03 fail-fast 与 continue-on-error 策略
- **Story**：作为 CI，我希望并行工作流在一个子任务失败时有两种行为可选：立即中止或继续其他分支。
- **AC**：
  1. workflow root 增加 `on_error: fail_fast | continue_on_error`（默认 `fail_fast`）。
  2. `continue_on_error` 模式：失败的子任务标记为 `failed`，其他子任务继续，merge 阶段跳过失败项。
  3. 有两种策略的测试用例。
- **优先级**：P2
- **测试用例 ID**：SAG-ERR-001 ~ SAG-ERR-008
- **依赖**：S5-01，S5-02
- **估算**：M

### S5-04 预算与质量门禁联动
- **Story**：作为运营，我希望并行工作流的总 token 消耗超过预算时自动中止，避免意外超支。
- **AC**：
  1. workflow root 增加 `budget_max_tokens`（可选）。
  2. 超过预算时中止未启动的子任务，已运行的结果保留。
  3. 最终报告包含 `budget_used` / `budget_limit` / `budget_exceeded`。
- **优先级**：P2
- **测试用例 ID**：SAG-BUDGET-001 ~ SAG-BUDGET-006
- **依赖**：S5-02
- **估算**：M

---

## Epic S6：Messaging Gateway（Telegram MVP）

### S6-01 gateway 命令组基础结构
- **Story**：作为用户，我希望通过 `cai-agent gateway` 子命令管理网关的生命周期，类似 Hermes 的 `hermes gateway`。
- **AC**：
  1. `gateway setup` 引导配置（Bot Token、allowlist、工作区）。
  2. `gateway start` 启动后台服务。
  3. `gateway status` 输出运行状态/已绑定用户/连接数。
  4. `gateway stop` 优雅停止。
- **优先级**：P1
- **测试用例 ID**：GTW-BASE-001 ~ GTW-BASE-010
- **依赖**：无
- **估算**：XL

### S6-02 Telegram Bot 消息收发
- **Story**：作为用户，我希望在 Telegram 里发消息给 Bot，Bot 代理 CLI 执行 `run` 并把结果返回到 Telegram。
- **AC**：
  1. 用户发送文本消息 → Bot 调用 `run` → 回复完整 answer。
  2. 长回复自动分段发送（< 4096 字符/条）。
  3. `/status`、`/stop`、`/new` 等 slash 命令在 Telegram 中可用。
- **优先级**：P1
- **测试用例 ID**：GTW-TG-001 ~ GTW-TG-015
- **依赖**：S6-01
- **估算**：XL

### S6-03 用户身份绑定与 allowlist
- **Story**：作为安全负责人，我希望只有明确授权的 Telegram 用户能与 Bot 交互，未授权用户的消息直接忽略。
- **AC**：
  1. 配置 `allowed_chat_ids`（Telegram chat_id 白名单）。
  2. `gateway setup --allow <chat_id>` 追加授权。
  3. 未授权消息回复标准拒绝语并不触发执行。
- **优先级**：P0
- **测试用例 ID**：GTW-SEC-001 ~ GTW-SEC-010
- **依赖**：S6-01
- **估算**：M

### S6-04 跨端会话连续性（CLI ↔ Telegram）
- **Story**：作为用户，我希望在 Telegram 开始的对话可以通过 CLI `continue` 继续，反之亦然。
- **AC**：
  1. Telegram 消息触发的会话自动保存为 `.cai-session-tg-<id>.json`。
  2. 用户可用 `cai-agent continue <file>` 在本地继续。
  3. 有文档说明如何切换端。
- **优先级**：P2
- **测试用例 ID**：GTW-CONT-001 ~ GTW-CONT-008
- **依赖**：S6-02
- **估算**：L

---

## Epic S7：Observability Pro

### S7-01 统一指标模型（metrics schema）
- **Story**：作为运维，我希望所有模块（memory/recall/schedule/gateway）共享一套指标字段定义，方便统一聚合。
- **AC**：
  1. 定义 `metrics_schema_v1`：`ts`、`module`、`event`、`latency_ms`、`tokens`、`cost_usd`（可选）、`success`。
  2. 各模块输出事件时填写对应字段。
  3. 有 schema 文档与 Python TypedDict 定义。
- **优先级**：P1
- **测试用例 ID**：OBS-METRICS-001 ~ OBS-METRICS-008
- **依赖**：S4-04
- **估算**：M

### S7-02 observe report（周报/日报导出）
- **Story**：作为运营，我希望用一条命令生成过去 7 天的运营摘要报告（会话量/成功率/成本/工具错误率），导出 Markdown 或 JSON。
- **AC**：
  1. `observe report --days 7 --format markdown > report.md`。
  2. 包含：session_count、success_rate、token_total/avg、tool_error_rate、top_failing_tools。
  3. JSON 格式 schema 版本 `1.0`。
- **优先级**：P1
- **测试用例 ID**：OBS-RPT-001 ~ OBS-RPT-010
- **依赖**：S7-01
- **估算**：L

### S7-03 跨域关联洞察（memory/recall/schedule 趋势联合）
- **Story**：作为运营，我希望看到"记忆质量变化"与"recall 命中率"的关联趋势，判断 memory 提炼是否改善了搜索效果。
- **AC**：
  1. `insights --cross-domain --json` 输出：recall_hit_rate_trend、memory_health_trend、schedule_success_trend。
  2. 时间对齐到相同 7/14/30 天窗口。
- **优先级**：P2
- **测试用例 ID**：OBS-CROSS-001 ~ OBS-CROSS-006
- **依赖**：S7-02，S2-01，S3-01
- **估算**：L

### S7-04 运营看板导出（JSON/CSV/Markdown）
- **Story**：作为运营，我希望能把关键指标一键导出为多种格式，直接粘贴进例会文档或导入 BI 工具。
- **AC**：
  1. `observe export --format csv/json/markdown --days 30 -o out.csv`。
  2. 列包含：日期、session_count、success_rate、token_avg、schedule_tasks_ok/failed、memory_health。
- **优先级**：P2
- **测试用例 ID**：OBS-EXP-001 ~ OBS-EXP-006
- **依赖**：S7-02
- **估算**：M

---

## Epic S8：GA 收敛

### S8-01 全量回归套件整合
- **Story**：作为 QA，我希望有一个入口命令跑所有功能域的回归，并产出带时间戳的报告。
- **AC**：
  1. `scripts/run_regression.py` 覆盖所有 Sprint 功能测试。
  2. 报告包含：通过率/失败列表/风险评估。
  3. CI 失败时阻断合并。
- **优先级**：P0
- **测试用例 ID**：GA-REG-001 ~ GA-REG-010
- **依赖**：S1~S7 全部 DoD
- **估算**：L

### S8-02 关键路径压测
- **Story**：作为架构师，我希望在发布前验证关键路径在负载下不会崩溃或显著退化。
- **AC**：
  1. recall 200 文件检索 < 5s。
  2. schedule daemon 长跑 100 轮次不 OOM/不锁死。
  3. gateway 连续收发 500 条消息不掉线。
- **优先级**：P0
- **测试用例 ID**：PERF-GA-001 ~ PERF-GA-010
- **依赖**：S3-04，S4-02，S6-02
- **估算**：L

### S8-03 安全审计
- **Story**：作为安全负责人，我希望发布前完成一轮安全扫描，确保无已知 secret 泄露、无越权路径。
- **AC**：
  1. `security-scan` 零 P0 误报（高风险规则全覆盖）。
  2. gateway allowlist bypass 测试通过。
  3. 无硬编码 API key。
- **优先级**：P0
- **测试用例 ID**：SEC-GA-001 ~ SEC-GA-010
- **依赖**：S6-03
- **估算**：M

### S8-04 发布说明与迁移指南
- **Story**：作为用户，我希望升级时有清晰的 breaking change 列表和迁移步骤，不会因为不知道有破坏性变更而遇到意外问题。
- **AC**：
  1. `CHANGELOG.md` 中 0.6.0 章节包含：breaking changes、新命令列表、废弃警告。
  2. `docs/MIGRATION_GUIDE.md`：从 0.5.x 到 0.6.0 的每一步变更操作。
  3. README 补充版本要求。
- **优先级**：P1
- **测试用例 ID**：（文档验证）
- **依赖**：S8-01
- **估算**：M

---

## 快速参考：优先级总表

| ID | 标题 | Sprint | 优先级 | 估算 |
|----|------|--------|--------|------|
| S1-01 | 命令参数命名一致性审计 | S1 | P1 | M |
| S1-02 | JSON 输出 schema 版本文档化 | S1 | P1 | M |
| S1-03 | 错误码规范与退出码一致 | S1 | P1 | S |
| S1-04 | Parity Matrix 更新 | S1 | P1 | S |
| S2-01 | memory health 统一评分 | S2 | P1 | L |
| S2-02 | freshness 指标 | S2 | P1 | M |
| S2-03 | conflict_rate 指标 | S2 | P2 | L |
| S2-04 | coverage 指标 | S2 | P2 | M |
| S2-05 | nudge-report health_score 字段 | S2 | P2 | S |
| S3-01 | recall 排序策略升级 | S3 | P1 | L |
| S3-02 | 无命中解释 | S3 | P1 | M |
| S3-03 | recall-index doctor | S3 | P1 | M |
| S3-04 | recall 性能基准测试 | S3 | P2 | M |
| S4-01 | 重试与指数退避 | S4 | P1 | L |
| S4-02 | 并发控制 | S4 | P1 | L |
| S4-03 | 任务依赖 | S4 | P2 | L |
| S4-04 | 执行审计日志 schema | S4 | P1 | M |
| S4-05 | 任务 SLA 指标 | S4 | P2 | M |
| S5-01 | workflow 并行 stage | S5 | P1 | L |
| S5-02 | fan-out/fan-in 聚合 | S5 | P1 | L |
| S5-03 | fail-fast / continue-on-error | S5 | P2 | M |
| S5-04 | 预算与质量门禁联动 | S5 | P2 | M |
| S6-01 | gateway 命令组基础 | S6 | P1 | XL |
| S6-02 | Telegram 消息收发 | S6 | P1 | XL |
| S6-03 | 用户身份绑定与 allowlist | S6 | P0 | M |
| S6-04 | 跨端会话连续性 | S6 | P2 | L |
| S7-01 | 统一指标模型 | S7 | P1 | M |
| S7-02 | observe report 导出 | S7 | P1 | L |
| S7-03 | 跨域关联洞察 | S7 | P2 | L |
| S7-04 | 运营看板导出 | S7 | P2 | M |
| S8-01 | 全量回归套件整合 | S8 | P0 | L |
| S8-02 | 关键路径压测 | S8 | P0 | L |
| S8-03 | 安全审计 | S8 | P0 | M |
| S8-04 | 发布说明与迁移指南 | S8 | P1 | M |
