# Cai_Agent 功能能力地图与缺口分析

本文档以三个上游仓库为对照基线：

- [`anthropics/claude-code`](https://github.com/anthropics/claude-code)
- [`NousResearch/hermes-agent`](https://github.com/NousResearch/hermes-agent)
- [`affaan-m/everything-claude-code`](https://github.com/affaan-m/everything-claude-code)

产品定位见：[PRODUCT_VISION_FUSION.zh-CN.md](PRODUCT_VISION_FUSION.zh-CN.md)。发版勾选见：[PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md)。

## 当前基线

当前仓库已经具备的强项：

- Claude Code 风格的 CLI / TUI / plan / run / continue / workflow 主链路
- Hermes 第一阶段对齐的 recall / scheduler / gateway / observability / release gate
- ECC 风格的 rules / skills / hooks / export / plugin compatibility / cost routing 基础
- 清晰的权限边界、安全扫描、质量门禁与 JSON schema 索引

## 关键缺口（按优先级）

1. **P1 - Claude Code 体验缺口**
   - WebSearch / Notebook 仍以 MCP 为主，未形成内置产品体验
   - 安装 / 更新 / `/bug` 等用户体验仍偏工程化

2. **P1 - Hermes 产品化缺口**
   - profiles 契约与 CLI 已显著收口；**最小 HTTP API**（**`api serve`**，**`HM-02b`**）已落地 v0，后续可扩路由与鉴权策略
   - gateway 已有 Telegram full、Discord/Slack/Teams mvp；**下一批平台优先级**见 **`docs/rfc/HM_03C_NEXT_GATEWAY_PLATFORMS.zh-CN.md`**（**`HM-03c`** 文档已收口，**`HM-03d-teams`** 已落地），并已通过 **`gateway_production_summary_v1`** 提供本地生产状态摘要；后续重点转向多工作区联邦与频道监控
   - voice、dashboard 高级交互、memory providers、更多 runtime backends：Dashboard 已先以 **`ops_dashboard_interactions_v1`** dry-run 预览契约限定写入边界；Memory provider 已以 **`memory_provider_contract_v1`** 固定 local entries / user-model SQLite 与外部 adapter 边界；**Voice 默认 OOS** 见 **`docs/rfc/HM_07A_VOICE_BOUNDARY.zh-CN.md`**；**runtime 优先级**见 **`docs/rfc/HM_06A_RUNTIME_BACKEND_ASSESSMENT.zh-CN.md`**，其中 **docker 产品化（HM-06b）** 与 **SSH 产品化（HM-06c）** 已落地，云后端仍按 OOS/条件立项处理
   - recall 评估（**`recall --evaluate`**）与 memory policy（**`doctor` / `release-ga`**）已有机读与文本入口；负样本审计见 **`recall_audit`**

3. **P1 - ECC 治理生态缺口**
   - rules / skills / hooks 已有 **`ecc layout`** / 导出主路径；**安装→导出→共享** 叙事已收进 **`CROSS_HARNESS_COMPATIBILITY*.md`**（**ECC-01b**）
   - **成本视图**：**`cost report`** 已带 **`compact_policy_explain_v1`**（**ECC-02b**）；**插件/版本治理叙事**见 **`docs/rfc/ECC_03A_PLUGIN_VERSION_GOVERNANCE.zh-CN.md`**（**`ECC-03a`** 文档已收口）

4. **P1 - 文档与双语同步缺口**
   - 中文文档长期承担了大部分产品叙述，英文入口落后
   - 同一状态曾在多份文档重复维护，容易产生口径分叉

5. **P2 - 分发与反馈闭环**
   - 缺官方安装器级分发
   - 反馈闭环、自助诊断、发版叙事仍需继续产品化

6. **OOS / 条件性能力**
   - 依赖封闭服务、官方企业能力或独占平台接入的特性，不默认追求同形态复刻
   - 若不做，必须在 `PARITY_MATRIX` 中标注 `OOS`，或给出 MCP / 文档替代路径

## 发布门禁

每次对外发版前，至少满足：

- **文档一致性**：`README.md` / `README.zh-CN.md` / `docs/README.*` 的定位不冲突
- **矩阵更新**：`PARITY_MATRIX` 至少更新一处 `Done` / `Next` / `MCP` / `OOS`
- **缺口关闭**：每个小版本至少处理一个 P1 缺口，方式只能是：
  - 实现
  - MCP 替代并补文档
  - OOS 备案
- **路线图同步**：`ROADMAP_EXECUTION` 中的 todo 与 `PRODUCT_PLAN` 当前状态不冲突

## 落地原则

- 先把三上游的能力**汇成一个产品模型**，再决定代码实现顺序
- 先交付统一入口、统一 schema、统一体验，再补高级能力
- 复杂能力坚持“**先可用，再产品化，再生态化**”

## 相关文档

- 愿景与定位：[PRODUCT_VISION_FUSION.zh-CN.md](PRODUCT_VISION_FUSION.zh-CN.md)
- 当前执行清单：[PRODUCT_PLAN.zh-CN.md](PRODUCT_PLAN.zh-CN.md)
- 当前路线图：[ROADMAP_EXECUTION.zh-CN.md](ROADMAP_EXECUTION.zh-CN.md)
- 发版勾选矩阵：[PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md)
