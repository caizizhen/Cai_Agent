# Hermes 对齐开发总计划（Sprint-by-Sprint）

> 目标：对齐 https://github.com/NousResearch/hermes-agent 的核心能力，并在当前 Cai_Agent 基础上形成可持续交付路线。
>
> 读者：开发负责人、架构师、产品、QA。
>
> 使用方式：每个 Sprint 按“范围 -> 任务拆解 -> DoD -> 风险 -> 联调/验收”执行；每次迭代结束同步更新 `README*` / `CHANGELOG*` / `docs/qa/*`。

---

## 1. 当前能力基线（已完成）

当前仓库已具备以下 Hermes 对齐能力（MVP/可用态）：

- **Memory Loop**：`memory extract/list/search/prune`、`memory nudge`、`memory nudge-report`
- **Recall Loop**：`recall`、`recall-index build/refresh/search/info/clear`（含增量刷新）
- **Scheduler**：`schedule add/list/rm/run-due/daemon`、`schedule add-memory-nudge`
- **Observability**：`stats`、`insights`、`observe`（基础聚合）
- **Quality/Security**：`quality-gate`、`security-scan`

说明：以上能力已满足“单机 CLI 工作流”基础闭环，但与 Hermes 的平台化能力（多端网关、并行子代理、生产级调度治理）仍有差距。

---

## 2. 总体对齐目标（能力域）

按能力域分层推进：

1. 交互层（CLI/TUI 体验与可发现性）
2. 模型与配置层（profile/provider 路由）
3. Memory/Recall 闭环（质量、趋势、可解释性）
4. Scheduler 生产化（重试、并发、审计）
5. Subagents 并行编排（fan-out/fan-in）
6. Messaging Gateway（Telegram 优先）
7. Observability Pro（运营/质量看板）
8. 安全与发布收敛（GA）

---

## 3. Sprint 计划（建议 8 个 Sprint）

> 注：不做日历时间估算；仅按技术范围和依赖关系组织。

### Sprint 1：Parity 基线收敛 + 命令一致性

**目标**：冻结对齐基线，统一命令体验与输出 schema。

**范围**：
- 清理命令参数命名一致性（`--json`、`--index-path`、`--history-file`、`--days` 等）
- 统一关键命令 JSON schema 版本标识与字段约定
- 完成 Parity Matrix（Done / In Progress / Gap）并形成 backlog

**开发任务**：
- [ ] `__main__.py` 命令帮助与参数命名统一
- [ ] 输出 schema 文档化（`docs/`）
- [ ] 补齐错误码规范（0/2）

**DoD**：
- 命令 help 与 README 示例一致
- schema 文档可被 QA 直接引用
- 关键命令有最少 1 条契约测试

**依赖/风险**：
- 风险：历史测试依赖旧字段
- 缓解：逐命令兼容字段 + deprecation 提示

---

### Sprint 2：Memory Loop 2.0（质量治理）

**目标**：从“可提醒”升级到“可治理”。

**范围**：
- `memory nudge-report` 增加质量评分（health score）
- 增加记忆冲突/过期/覆盖率统计
- 增加阈值守门（CI/schedule 可直接消费）

**开发任务**：
- [ ] 增加 `memory health` 或在 `nudge-report` 增加 `health_score`
- [ ] 追加质量指标字段：freshness/coverage/conflict_rate
- [ ] 增加 `--fail-on-health-below`

**DoD**：
- 可输出单值健康分 + 解释项
- QA 可复现 high/medium/low 三档场景

---

### Sprint 3：Recall Loop 2.0（质量 + 可解释）

**目标**：提升 recall 命中质量与可解释性。

**范围**：
- recall 排序策略（时间衰减 + 命中密度）
- no-hit explain（无命中解释）
- index health 检查命令

**开发任务**：
- [ ] `recall` 增加 ranking mode
- [ ] `recall --explain-no-hit`
- [ ] `recall-index doctor`（一致性/损坏/过期检查）

**DoD**：
- 性能回归不退化
- 命中质量对比测试通过

---

### Sprint 4：Scheduler 2.0（生产可用）

**目标**：让 schedule 可支撑长期无人值守运行。

**范围**：
- 重试与指数退避
- 并发控制（全局/任务级）
- 任务依赖（A->B）
- 执行审计增强（事件类型与状态机）

**开发任务**：
- [ ] `.cai-schedule.json` schema 扩展（retry/backoff/deps）
- [ ] `run-due/daemon` 状态机升级
- [ ] 日志事件标准化（JSONL）

**DoD**：
- 失败任务可自动重试且可追溯
- 手工 kill/restart 后状态可恢复

---

### Sprint 5：Subagents 并行编排

**目标**：对齐 Hermes 并行子任务能力。

**范围**：
- 子代理任务 DSL
- fan-out/fan-in 汇总
- 结果冲突解决策略（last-wins/priority/manual）

**开发任务**：
- [ ] workflow schema 增加并行阶段
- [ ] 执行器增加并行调度与聚合
- [ ] 预算/失败策略（fail-fast / continue-on-error）

**DoD**：
- 单任务可拆并行并自动汇总
- 输出包含每个子任务 trace

---

### Sprint 6：Messaging Gateway（Telegram MVP）

**目标**：补齐多端接入。

**范围**：
- Telegram Bot 接入
- 用户身份绑定与会话映射
- 网关安全策略（allowlist / pairing）

**开发任务**：
- [ ] `gateway setup/start/status` 命令组
- [ ] 会话存储适配（CLI <-> TG）
- [ ] 安全策略与配置项

**DoD**：
- Telegram 与 CLI 可连续会话
- 基础安全策略可验证

---

### Sprint 7：Observability Pro（运营看板）

**目标**：形成可运营的质量/成本/稳定性视图。

**范围**：
- 统一指标模型（success/error/latency/token/cost）
- 周报/日报导出（json/csv/markdown）
- memory/recall/schedule 跨域关联洞察

**开发任务**：
- [ ] `observe report` 子命令
- [ ] metrics schema versioning
- [ ] 看板摘要（top regressions）

**DoD**：
- 产出可直接投放 QA/运维例会
- 指标定义在文档中闭环

---

### Sprint 8：GA 收敛（性能+安全+发布）

**目标**：发布级质量门禁。

**范围**：
- 回归矩阵全绿
- 关键路径压测
- 安全审计与发布清单

**开发任务**：
- [ ] 回归测试整合脚本升级
- [ ] recall/schedule/gateway 压测
- [ ] 发布说明与迁移指南

**DoD**：
- 发布门禁 checklist 全通过
- 关键风险项关闭

---

## 4. 跨 Sprint 非功能性约束

每个 Sprint 必做：

- 文档同步：`README.md` / `README.zh-CN.md` / `CHANGELOG.md` / `CHANGELOG.zh-CN.md`
- QA 文档同步：`docs/qa/*-testplan.md`
- 自动化最小集合：新增功能必须有 CLI 测试 + 回归入口
- Schema 变更：必须标注版本与向后兼容策略

---

## 5. 开发执行规范（给开发）

1. 每个 Story 必须包含：
   - 变更文件列表
   - 命令示例
   - JSON 输出样例
   - 回归命令

2. 每个 PR 必须包含：
   - 影响面说明
   - 风险与回滚策略
   - 文档与测试同步说明

3. 禁止事项：
   - 不带测试的 CLI 参数变更
   - 只改中文/英文单侧文档
   - schema 破坏性变更无版本号

---

## 6. 建议 backlog 标签体系

- `parity-core`：与 Hermes 核心能力直接对齐
- `parity-ops`：运维/质量/可观测性
- `parity-gateway`：多端接入
- `parity-subagent`：并行与编排
- `hardening`：稳定性/安全/性能

