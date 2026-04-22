# Hermes 对齐开发总计划（按 Sprint）

本文档用于统一 Cai Agent 的 Hermes 对齐开发节奏，作为研发、QA、发布与文档同步的单一执行基线。

关联文档：
- `docs/ROADMAP_EXECUTION.zh-CN.md`
- `docs/NEXT_IMPLEMENTATION_BUNDLE.zh-CN.md`
- `docs/REFERENCE_PARITY_BACKLOG_2026-04-17.zh-CN.md`
- `docs/PRODUCT_GAP_ANALYSIS.zh-CN.md`
- `docs/PARITY_MATRIX.zh-CN.md`
- `docs/DEVELOPMENT_PROGRESS_TRACKER.zh-CN.md`

---

## 1) 当前能力基线（已完成项）

基于现有代码与 `DEVELOPMENT_PROGRESS_TRACKER`，当前已完成或高完成度能力如下：

1. 任务与编排底座
   - `workflow` 支持多步执行、并发组（`parallel_group`）与 merge 结果汇总。
   - 输出包含标准化事件流与子代理 I/O 结构（`subagent_io_schema_version`）。

2. 观测与门禁
   - 已有 `observe` / `observe-report` 聚合通道。
   - `release-ga` 支持质量、安全、成本、doctor、memory nudge、memory state 多维门禁。

3. 安全策略
   - `security-scan` 已接入开发流程。
   - `run_command` 高危命令可配置阻断（默认防护）。

4. 记忆与召回
   - `memory` 与 `recall` 已具备 schema 演进与评分模型增强。
   - 支持状态评估（active/stale/expired）和 prune 治理策略。

5. 网关 MVP
   - Telegram 映射、update 解析、webhook 接入、执行触发与回发闭环已具备最小可用链路。

> 结论：项目已具备 Hermes 对齐所需的核心执行底座；后续重点从“可用”升级到“标准化、可运营、可持续演进”。

---

## 2) Hermes 对齐目标能力域

按 Hermes 对齐目标，能力域拆分如下：

1. Runtime & Task Model
   - 统一任务状态机、事件信封、schema 版本治理。
2. Tooling & Integrations
   - WebSearch/Notebook 的 MCP 优先路径与降级策略。
3. Memory & Recall Governance
   - 记忆 schema 校验、TTL/置信度、召回排序可解释性。
4. Safety & Permissions
   - 高危命令审批、敏感信息扫描、反馈链路脱敏。
5. Observability & Operations
   - 看板化任务运营与跨命令可观测一致性。
6. Release & Quality
   - 可重复门禁、回归套件、发布说明与 parity 勾选闭环。
7. Ecosystem & Compatibility
   - 跨 harness 导出与兼容映射持续对齐。
8. Team Execution
   - PR 规范、测试与文档同步、backlog 标签治理。

---

## 3) 8 个 Sprint 完整规划

### Sprint 1：事件与任务模型统一（L1 基础收口）

- 范围
  - 统一 `run/continue/workflow/observe/sessions` 的任务主键与状态语义。
  - 明确并固化事件信封 schema 与版本字段。
- 开发任务
  - 增补 `task_id` 全链路透传校验。
  - 为关键命令输出补齐 `run_schema_version`。
  - 对 `observe` 聚合字段做一致性梳理（events_count、state 分布）。
- DoD
  - 单测覆盖关键命令 JSON 输出字段一致性。
  - 文档给出事件字段字典与示例。
  - `PARITY_MATRIX` 同步状态变更。
- 依赖/风险
  - 依赖现有 workflow 事件模型。
  - 风险：历史会话兼容，需保留向后读取策略。

### Sprint 2：任务看板最小可用版（L1 可观测）

- 范围
  - 提供面向人读的任务看板（TUI 面板或本地轻量页面）。
- 开发任务
  - 基于 `observe` 结果生成任务列表与状态汇总视图。
  - 支持按 task_id/session 过滤与最近失败优先展示。
  - 增加最小告警视图（失败率/门禁失败）。
- DoD
  - 能展示至少一次完整 workflow 状态流转。
  - 看板与 JSON 聚合统计一致。
  - 增加 e2e 冒烟测试或快照测试。
- 依赖/风险
  - 依赖 Sprint 1 事件统一。
  - 风险：UI 形态分歧，需保持 CLI-first、不阻塞主链路。

### Sprint 3：MCP 优先的 WebSearch/Notebook 对齐

- 范围
  - 落地 WebSearch 与 Notebook 的 MCP 优先策略和文档闭环。
- 开发任务
  - 固化 MCP 配置模板、权限建议与失败降级提示。
  - CLI 层补充快速自检入口（连接、超时、鉴权提示）。
  - 明确 OOS 条件与替代路径模板。
- DoD
  - 文档可从零复现一次 WebSearch/Notebook 能力接入。
  - 失败路径不影响主执行链（可降级）。
  - `PARITY_MATRIX` 标记 `MCP` 或 `Done`。
- 依赖/风险
  - 依赖外部 MCP 服务稳定性。
  - 风险：网络与密钥配置导致假失败，需强引导诊断信息。

完成记录（进行中）：
- 已落地 `mcp-check` 自检增强：`--preset websearch|notebook`、`--list-only`，并在 JSON 输出中增加 `preset` 诊断对象（`recommended_tools/matched_tools/missing_tools/ok`）。
- 已落地降级提示与模板输出：当 preset 未命中时输出 `fallback_hint`，并支持 `--print-template` 直接生成最小 MCP 配置片段。
- 已补充差异化模板：`--print-template` 针对 `websearch/notebook` 输出不同的示例工具名与环境变量提示，便于按能力域快速起配。
- 目的：在不强依赖具体 MCP 服务实现的前提下，为 WebSearch/Notebook 接入提供可脚本化的最小诊断入口与可复制配置起点。

### Sprint 4：Memory Schema v1 严格化与治理策略

- 范围
  - 强化 memory entry schema 校验、TTL 与置信度治理。
- 开发任务
  - 写入前 schema 校验与错误提示标准化。
  - 导入导出一致性检查与坏数据隔离报告。
  - prune 策略增加可解释统计（按原因分桶）。
- DoD
  - 非法 entry 必须拒绝写入，错误信息可读可定位。
  - 导入导出回归测试通过。
  - 文档包含字段定义与迁移说明。
- 依赖/风险
  - 依赖现有 memory schema 文件。
  - 风险：老数据兼容，需要迁移/忽略策略。

完成记录（进行中）：
- 已落地 `memory import-entries --dry-run`：导入前可先做纯校验，不写入磁盘。
- 已强化 bundle 校验错误语义：返回结构化错误（`entry_index/path/errors`），并在 CLI 失败时输出 `error=memory_bundle_invalid` + `validation_errors`。
- 已补齐坏数据隔离报告导出：`memory import-entries` 新增 `--error-report <path>`，当存在无效行时输出 `memory_entries_import_errors_v1` 报告（含 `source_file/errors_count/errors`）。
- 已增强 CLI 人类可读失败摘要：校验失败时在 stderr 输出总览（total/validated/invalid）与首个错误定位（entry_index/path/reason），并提示报告文件路径。
- 目的：让坏数据导入失败具备可定位、可修复、可自动化消费的错误结构，降低批量数据迁移风险。

### Sprint 5：Hooks Runtime 深化（执行器 + profile）

- 范围
  - 完善 `hooks.json` 匹配、执行、禁用列表与 profile（minimal/standard/strict）。
- 开发任务
  - 实现 hooks 执行器统一入口及错误语义。
  - profile 切换影响默认启用规则。
  - 增加 Windows 路径与 shell 兼容测试。
- DoD
  - 指定 hook ID 可禁用且行为可验证。
  - profile 生效路径有自动化测试覆盖。
  - 安全默认值阻断高危执行。
- 依赖/风险
  - 依赖现有 hook 摘要输出能力。
  - 风险：跨平台执行差异，需要最小公约数命令策略。

### Sprint 6：上下文压缩与成本策略联动

- 范围
  - 把 `context` 与 `cost budget` 从统计升级为策略引擎。
- 开发任务
  - 引入 compact 触发规则（阶段点/失败重试前/预算预警）。
  - 增加模型路由建议输出（轻量任务/复杂任务）。
  - `stats/observe` 暴露策略触发计数。
- DoD
  - 触发规则可配置、可观测、可测试。
  - 文档给出默认阈值与调优建议。
  - 不破坏现有 usage 统计输出。
- 依赖/风险
  - 依赖成本统计稳定性。
  - 风险：策略过于激进影响质量，需要默认保守。

### Sprint 7：反馈与发布闭环（DevEx/Release）

- 范围
  - 建立“可反馈、可追踪、可发布说明”的产品闭环。
- 开发任务
  - 增加 issue 模板与环境信息收集（脱敏）。
  - 发布说明模板对齐 parity 变更项。
  - 将关键门禁输出映射为用户可读摘要。
- DoD
  - 反馈信息不泄露密钥。
  - CHANGELOG、PARITY、ROADMAP 三处同步可追踪。
  - QA 可按模板复用发布检查单。
- 依赖/风险
  - 依赖现有 doctor/release-ga 输出。
  - 风险：文档更新不一致，需 PR 模板强约束。

### Sprint 8：跨 Harness 兼容与 GA 收敛

- 范围
  - 完成 GA 前兼容性、质量与文档的最终收敛。
- 开发任务
  - `export` 与兼容映射表补齐差异项。
  - 增补回归测试（核心命令 JSON schema + 门禁 + 导出）。
  - 完成最终验收清单与残留风险备案。
- DoD
  - 兼容矩阵关键项达到可发布门槛。
  - 全量回归通过，残留项有 OOS 或延期说明。
  - 形成 GA 验收包（测试报告 + 文档索引）。
- 依赖/风险
  - 依赖前 7 个 Sprint 稳定收口。
  - 风险：跨模块联动回归成本高，需固定 smoke + full 回归分层执行。

---

## 4) 跨 Sprint 约束

### 4.1 文档同步约束

每个 Sprint 合并前必须同步更新：
- `docs/DEVELOPMENT_PROGRESS_TRACKER.zh-CN.md`
- `docs/PARITY_MATRIX.zh-CN.md`
- 相关能力专题文档（如 MEMORY、MCP、OBSERVE、RELEASE）

### 4.2 测试同步约束

每个 Sprint 至少包含：
- 单元测试：覆盖新增逻辑与异常分支。
- 回归测试：`python scripts/run_regression.py`（或等效套件）。
- 关键命令 JSON schema 验证（快照或字段断言）。

### 4.3 Schema 版本策略

- 新增字段：优先向后兼容（可选字段 + 默认值）。
- 破坏性变更：必须升级 schema 版本并提供迁移/兼容读取策略。
- 所有 JSON 输出（run/workflow/observe/memory/recall/release）需显式 `schema_version` 或等价版本字段。

---

## 5) 开发执行规范

### 5.1 PR 要求

每个 PR 必须包含：
1. 变更背景（对应 Sprint 与能力域）。
2. 代码变更说明（模块、行为变化、兼容性）。
3. 测试证据（新增测试 + 执行结果）。
4. 文档同步清单（至少列出已更新文档路径）。
5. 风险与回滚说明（若涉及 schema 或门禁策略）。

### 5.2 禁止事项

- 禁止只改代码不补文档/测试。
- 禁止在无 schema 版本说明下修改 JSON 契约。
- 禁止绕过安全默认值（尤其高危命令策略）直接放开。
- 禁止将密钥、令牌、敏感路径写入日志或反馈输出。
- 禁止未验证回归即宣称 Sprint 完成。

### 5.3 Backlog 标签体系（建议）

- `hermes:sprint-1` ... `hermes:sprint-8`
- `domain:runtime` `domain:tooling` `domain:memory` `domain:safety`
- `domain:observability` `domain:release` `domain:compatibility`
- `type:feature` `type:refactor` `type:bug` `type:test` `type:docs`
- `risk:low` `risk:medium` `risk:high`
- `status:blocked` `status:needs-design` `status:ready`

---

## 6) 执行原则（落实“按照计划进行开发”）

1. 默认按 Sprint 顺序推进，允许在不破坏依赖关系前提下并行子任务。
2. 每个 Sprint 先完成“契约与观测”，再扩展“策略与体验”。
3. 如遇外部依赖阻塞（MCP/网络/第三方），优先保主链路可用并输出降级方案。
4. 所有延期项必须记录在对应 Sprint 的风险备注和 backlog 标签中。

---

维护建议：每次 Sprint 收口后，在本文档对应小节追加“完成记录（提交哈希、测试报告、文档链接）”，确保可追踪审计。
