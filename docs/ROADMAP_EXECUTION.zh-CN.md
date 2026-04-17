# Cai_Agent P0-P2 开发落地清单

本清单对应「功能对比后的工程执行与验收」，并与产品北极星对齐：**在单一运行时（Python / LangGraph / OpenAI 兼容）内实现三源融合「完全体」**——详见 [PRODUCT_VISION_FUSION.zh-CN.md](PRODUCT_VISION_FUSION.zh-CN.md)；发版前 parity 勾选约定见 [PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md)；维度级缺口与发布门禁见 [PRODUCT_GAP_ANALYSIS.zh-CN.md](PRODUCT_GAP_ANALYSIS.zh-CN.md)。

## P0（2-4 周）可用性底座

### 1) 插件化扩展骨架
- 已落地：
  - 扩展面注册模块：`cai-agent/src/cai_agent/plugin_registry.py`
  - CLI 清单命令：`cai-agent plugins`（支持 `--json`）
- 验收标准：
  - 能输出 `skills/commands/agents/hooks/rules/mcp-configs` 存在性与文件数
  - 在无配置文件和有配置文件场景都能正常识别项目根

### 2) 统一命令入口
- 现状：`plan/run/continue/commands/command/agents/agent/workflow` 已形成主链路
- 下一步：
  - 补齐 `fix-build`、`security-scan` 命令模板与 CLI 快捷入口
  - 在 TUI 中映射常用命令模板

### 3) 权限与安全最小体系
- 现状：`sandbox.py` 路径越界防护 + `tools.py` 命令白名单
- 下一步：
  - 增加敏感信息扫描命令（针对 prompt 与文件）
  - 增加高危命令二次确认策略（可配置）

### 4) 任务状态与可观测
- 现状：`sessions`、`stats`、`workflow` 已有最小统计
- 下一步：
  - 统一任务 ID 与状态流（pending/running/completed/failed）
  - 输出结构化事件日志，支持后续 Dashboard 消费

## P1（4-8 周）效率引擎

### 1) 记忆与学习系统 v1
- 目标：将会话经验沉淀为可检索“项目记忆”
- 里程碑：
  - 定义记忆 schema（来源、置信度、TTL）
  - 支持导入导出与检索排序

### 2) 上下文与成本治理
- 目标：把 token/cost 从“统计”升级为“策略”
- 里程碑：
  - 模型路由建议（复杂任务高配，常规任务低成本）
  - compact 建议时机（研究完成、里程碑后、失败重试前）

### 3) 多 Agent 编排 v1
- 目标：提供“探索-实现-评审”模板化协作
- 里程碑：
  - 标准子代理输入/输出协议
  - 汇总冲突检测与结果融合

### 4) 质量门禁
- 已落地：
  - `cai-agent quality-gate`（compileall、pytest、可选 ruff、可选 mypy、可选 `[[quality_gate.extra]]`、可选内嵌 security-scan）
  - 模块：`cai-agent/src/cai_agent/quality_gate.py`
- 下一步：
  - 按仓库语言栈扩展默认 gate 模板（如前端 monorepo）
  - 报告与 CI 徽章消费示例

## P2（8-12 周）生态与平台化

### 1) 跨工具兼容层
- 目标：对齐 Cursor/Codex/OpenCode 主要配置维度
- 输出物：
  - 兼容性映射规范：`docs/CROSS_HARNESS_COMPATIBILITY.zh-CN.md`
  - 配置生成脚本（目标格式转换）

### 2) 可视化运营面板
- 目标：从“命令行可用”升级到“团队可运营”
- 指标：
  - 任务队列、失败率、token 成本、规则命中、安全告警

### 3) 插件市场与版本治理
- 目标：形成可发布、可回滚、可评估的生态机制
- 里程碑：
  - 插件版本兼容矩阵
  - 插件健康评分与风险提示

## 推荐 KPI

- 首次可用时间（安装到首次成功任务）
- 端到端任务成功率（计划到可合并改动）
- 人工干预率
- 单任务 token 成本
- 安全拦截有效率
- 技能/命令复用率
