# 开发计划：界面化模型切换 + 多供应商（2026-04-17）

> 本计划是 [`MODEL_SWITCHER_BACKLOG.zh-CN.md`](MODEL_SWITCHER_BACKLOG.zh-CN.md) 的 **执行版**：把 M1–M13 拆到三个 Sprint，明确人、时、交付、验收、内测节奏。
> 无真实日历，时间以 **T+Nd（T 为开发启动日）** 标注；如团队统一换算为日历日，请在评审会上一次性对齐。

---

## 0. 一页纸摘要

| 项 | 内容 |
|----|------|
| **目标** | 任意用户可以在 TUI / CLI 里 **选择或新增** 模型（ChatGPT / Claude / 本地 / 其他 OpenAI 兼容），并可设置主/子代理路由。 |
| **周期** | ~3 周（3 个 Sprint，每 Sprint 5 个工作日） |
| **投入** | 2 名开发（Dev A、Dev B） + 1 名 QA + PM + 3–5 名内测用户 |
| **分支** | 主开发分支 `feat/model-switcher`；每个 Sprint 结束合并到 `main` 后再基于 `main` 打 `alpha/beta/ga` tag |
| **对外 Tag** | `v-model-switcher-alpha`（T+5d）→ `beta`（T+10d）→ `ga`（T+15d） |
| **阻塞/回滚** | 任一 Sprint 冻结日未达 DoD，**只发前一个可用 tag**，不带病合并 |

### 里程碑总表

| Sprint | 周期 | 主题 | 范围（来自 backlog） | 结束标志（Demo / Tag） |
|--------|------|------|----------------------|------------------------|
| **S1** | T+0d → T+5d | 基础：配置层 + CLI | M1, M2, M3, M12（预设骨架）, M6（ping 最小版） | `models add/use/list/ping` 可用；`run` 走 profile；内测发 **alpha** |
| **S2** | T+5d → T+10d | 多供应商 + 路由 | M10（Anthropic 原生）、M11（provider 工厂）、M8（主/子路由生效）、M12（预设补全）、M13（security-scan 规则） | ChatGPT / Claude 原生 / Claude via OpenRouter / 本地 四条线均跑通；内测发 **beta** |
| **S3** | T+10d → T+15d | TUI + 发版收尾 | M4（TUI 面板）、M5（`/use-model` 升级）、M7（`/status` + session）、M9（文档/CHANGELOG） | TUI 可视化切换；文档与示例齐全；内测发 **GA**，合入 `main` |

---

## 1. 分工矩阵（RACI 简化版）

| 任务 | Dev A | Dev B | QA | PM | 内测 |
|------|:-----:|:-----:|:--:|:--:|:----:|
| M1 配置层 `[[models.profile]]` + 兼容 | **R** |  | C | A |  |
| M2 Settings 投影 | **R** |  | C | A |  |
| M3 CLI `models` 子命令 | **R** |  | C | A | I（alpha 试用） |
| M6 `models ping` 健康检查 | **R** |  | C | A |  |
| M10 Anthropic 原生适配器 |  | **R** | C | A |  |
| M11 Provider 调度工厂 |  | **R** | C | A |  |
| M12 `--preset openai/anthropic/...` |  | **R** | C | A | I（beta 试用） |
| M8 主/子代理路由生效 |  | **R** | C | A |  |
| M13 `security-scan` 扩展 | C | **R** | C | A |  |
| M4 TUI 模型面板 | **R** |  | C | A | I（GA 试用） |
| M5 `/use-model` 行为升级 | **R** |  | C | A |  |
| M7 `/status` + session 字段补齐 | **R** |  | C | A |  |
| M9 README / CHANGELOG / Parity | C | C | C | **R** | I |
| QA 回归 & 验收 |  |  | **R** | A | C |
| 内测沟通 & 反馈收集 | I | I | I | **R** | **R** |

> R=负责, A=审批, C=咨询, I=知悉

---

## 2. Sprint 1 — 基础（T+0d → T+5d）

**主题**：配置层打通；命令行可管理；`cai-agent run` 用新 profile。

### 2.1 任务 & 时间片

| 工作日 | Dev A | Dev B |
|--------|-------|-------|
| D1 | M1 配置层骨架 + 单测（老配置兼容） | 阅读 backlog §8；搭 `llm_anthropic.py` 空壳 + mock server 环境 |
| D2 | M2 Settings 投影 + 老字段映射 | M10 打通 `/v1/messages` 最小调用（system/messages/max_tokens） |
| D3 | M3 CLI `models list/use/add` | M10 response 解析 + usage 映射；单测 |
| D4 | M3 `edit/rm`；M6 `ping` 最小版 | M11 provider 工厂骨架（openai→llm.py, anthropic→llm_anthropic.py） |
| D5 | 合并、冻结、打 **alpha** | 合并、冻结、打 **alpha** |

### 2.2 Sprint 1 DoD（Definition of Done）

- [ ] 旧 `[llm]` 配置启动零变化（回归通过）
- [ ] `cai-agent models add/list/use/rm/ping` 闭环可用（pytest 覆盖）
- [ ] `cai-agent run "hello"` 可通过 `active` 指向本地 LM Studio 正常返回
- [ ] `api_key_env` 未设置时 `doctor` 明确标 `AUTH_FAIL`
- [ ] `alpha` tag 发布，附 **内测 Release Note**（§6.1）

### 2.3 Sprint 1 风险

- TOML 原子写入在 Windows 可能遇到文件锁 → Dev A 用 `write→fsync→rename` 并加一层 `try/except PermissionError` 重试。
- Anthropic mock server 搭建占时间 → Dev B 先用 `respx` / `httpx.MockTransport`，不引新依赖。

---

## 3. Sprint 2 — 多供应商 + 路由（T+5d → T+10d）

**主题**：ChatGPT / Claude 官方 / Claude via OpenRouter / 本地 四条线跑通；主/子代理可分模型。

### 3.1 任务 & 时间片

| 工作日 | Dev A | Dev B |
|--------|-------|-------|
| D6 | M12 `--preset` 预设条目（openai/anthropic/openrouter/lmstudio/ollama） | M11 工厂接入主循环 `graph.py` |
| D7 | M12 预设补全 + 错误提示（id 冲突 / env 缺失） | M8 子代理路由接入 `workflow.py` |
| D8 | M13 security-scan 新规则 + 白名单 | M8 planner 路由接入；端到端联调 |
| D9 | 与 Dev B 联调，修 bug | 与 Dev A 联调，修 bug |
| D10 | 合并、冻结、打 **beta** | 合并、冻结、打 **beta** |

### 3.2 Sprint 2 DoD

- [ ] §5.1.1 QA 矩阵 **6 条用例** 全绿
- [ ] `/use-model` 在 openai ↔ anthropic 之间切换不崩
- [ ] `subagent` / `planner` 路由通过 mock 断言正确分发到不同 provider
- [ ] `security-scan` 对 `models.profile.api_key` 明文高危告警
- [ ] `beta` tag 发布，附内测 Release Note（§6.2）

### 3.3 Sprint 2 风险

- Anthropic 模型命名会变 / 版本更新 → 文档中 `model` 字段标注 "示例，以官方最新命名为准"，避免文档腐化。
- OpenRouter 限流返回 429 → 复用 `llm.py` 的重试表（429/502/503/504 已覆盖）。

---

## 4. Sprint 3 — TUI 体验 + 发版（T+10d → T+15d）

**主题**：可视化；体验闭环；文档与发版材料齐全。

### 4.1 任务 & 时间片

| 工作日 | Dev A | Dev B |
|--------|-------|-------|
| D11 | M4 TUI 模型面板（列表 + 切换） | M5 `/use-model <profile_id>` 行为升级 |
| D12 | M4 新增/编辑/删除/测试子动作 | M7 `/status` 扩展 + `session.json` 加字段 |
| D13 | M4 细节打磨 + 空态引导 | 修交叉 bug；回归 `workflow` / `observe` |
| D14 | M9 文档：README / 导航 / 示例 gif（可选） | M9 CHANGELOG / Parity 矩阵行 |
| D15 | 合并、冻结、打 **GA**，合入 `main` | 合并、冻结、打 **GA**，合入 `main` |

### 4.2 Sprint 3 DoD

- [ ] TUI `/models` 面板完成所有子动作（add/edit/rm/ping/switch）
- [ ] `/status` 显示 profile + 路由；session 文件含 `profile`
- [ ] [`PARITY_MATRIX.zh-CN.md`](PARITY_MATRIX.zh-CN.md) 增一行 Done
- [ ] `CHANGELOG` 4 条用户语言（已在 backlog §10 起草，PM 合入时审阅）
- [ ] **全量回归**：`python scripts/run_regression.py` 绿
- [ ] `GA` tag 发布；内测公告见 §6.3

---

## 5. QA 计划（给 QA 同学）

### 5.1 环境

- 必备：Python 3.11+、`pip install -e .`、本地 LM Studio 或 Ollama
- 可选：`OPENAI_API_KEY`、`ANTHROPIC_API_KEY`、`OPENROUTER_API_KEY`（若未获取，走 respx/MockTransport 的 mock 用例）

### 5.2 回归矩阵

| 场景 | Sprint 内触达 | 动作 |
|------|---------------|------|
| 老 `[llm]` 配置 | S1 | 启动 + `run` |
| `models add/list/use/rm` | S1 | 基本闭环 |
| `doctor` 健康检查 | S1 | env 未设置 / 错误 URL / 超时 |
| ChatGPT（真实或 mock） | S2 | `run "hello"` |
| Claude 原生 | S2 | `run "hello"` |
| Claude via OpenRouter | S2 | `run "hello"` |
| 本地 LM Studio / Ollama | S1/S2 | 回归 |
| `/use-model` 跨 provider 切换 | S2 | 不崩、下一条消息正确路由 |
| 主/子/planner 路由 | S2 | mock 断言 |
| TUI 面板 | S3 | 五个子动作全走一遍 |
| `security-scan` 新规则 | S2 | 明文 key 高危 |
| 全量回归脚本 | S3 | `python scripts/run_regression.py` 绿 |

### 5.3 缺陷等级（与现有一致）

- P0：崩溃 / 老配置无法启动 / 密钥泄漏 → 立刻停 tag
- P1：新路径不可用 / 路由错配 → Sprint 内必修
- P2：体验问题 / 文案 / 对齐 → 下 Sprint 或 GA 前修

### 5.4 产出

每个 Sprint 冻结日产出一份 `docs/qa/runs/regression-YYYYMMDD-HHmmss.md`（策略见 [`QA_REGRESSION_LOGGING.zh-CN.md`](QA_REGRESSION_LOGGING.zh-CN.md)），PM 在发版说明中引用。

---

## 6. 内测用户沟通（Release Note 模板）

> 渠道建议：GitHub Release（英文）+ README 顶部横幅链接中文说明。避免把未验收内容暴露给内测。

### 6.1 Alpha（T+5d）— 给 3–5 名愿意折腾的用户

- **能干什么**：`cai-agent models add/list/use/ping`，把多个模型配置并列，CLI 切换。
- **不能干什么**：Claude 原生 API 尚未接入（本期走 OpenAI 兼容网关体验）；TUI 面板未上线。
- **升级方式**：`pip install -e .` 后试 `cai-agent models list`。
- **反馈渠道**：GitHub Issue 模板 `feat/model-switcher`，附 `cai-agent doctor --json` 输出（已脱敏）。

### 6.2 Beta（T+10d）— 扩到更多用户

- **新增**：**ChatGPT / Claude 官方 API 原生** 接入；主/子代理路由；`--preset` 一键添加。
- **迁移提示**：建议把 `api_key` 改写成 `api_key_env`，beta 的 `security-scan` 会提示明文风险。
- **反馈重点**：跨 provider 切换、路由分发是否符合预期。

### 6.3 GA（T+15d）— 正式合入 `main`

- **新增**：TUI `/models` 面板；`/status` 展示 profile；session 带 profile 记录。
- **行为变化**：`/use-model <id>` 现在优先按 **profile id** 整组切换，未命中才回退为仅换 `model` 字段。
- **升级后自检**：`cai-agent doctor`、`/status`、打开一次 TUI 面板确认看到列表。

---

## 7. 沟通节奏

| 节奏 | 形式 | 参与 |
|------|------|------|
| **每日站会** 10 min | 昨日 / 今日 / 阻塞 | Dev A, Dev B, QA, PM |
| **Sprint 冻结日** 30 min | Demo + 冻结评审 + 打 tag 与否 | 全员 + 可选内测代表 |
| **内测同步** 每 Sprint 末一次 | Release Note + Issue 模板 | PM → 内测 |
| **阻塞升级** 随时 | PM 群里 at 相关人 | 任意角色发起 |

---

## 8. 开发启动 Checklist（今天就可以做）

PM 在启动日会议上用这张表逐条确认：

- [ ] `feat/model-switcher` 分支已创建，protect 规则正常（要求 PR + CI 通过）
- [ ] Dev A 已读完 [`MODEL_SWITCHER_BACKLOG.zh-CN.md`](MODEL_SWITCHER_BACKLOG.zh-CN.md) §2 §4 §5.1
- [ ] Dev B 已读完 backlog §8（供应商矩阵 + Anthropic 适配器要点）
- [ ] QA 已读完 §5 与 backlog §5.1.1，准备好 mock server
- [ ] CI 在本仓通过（`python scripts/run_regression.py` 基线绿）
- [ ] 至少 3 位内测用户确认可在 alpha 发布后 2 日内反馈
- [ ] 本计划（本文件）已在 README 导航链接

---

## 9. 一句话同步（可直接粘）

- **给开发**：按本文件排期，今天起跑 **Sprint 1**；Dev A 走 M1/M2/M3/M6，Dev B 走 M10/M11 骨架；D5 冻结打 **alpha**。需求细节以 [`MODEL_SWITCHER_BACKLOG.zh-CN.md`](MODEL_SWITCHER_BACKLOG.zh-CN.md) 为准，不一致以 PM 裁决。
- **给 QA**：按 §5 回归矩阵准备 mock server 与 key；Sprint 冻结日前一天起进行主回归，冻结日跑 `python scripts/run_regression.py` 并出报告。
- **给内测用户**：**T+5d 起** 有 alpha 包可以试，主要是 CLI `cai-agent models ...` 闭环；T+10d beta 起支持 **ChatGPT / Claude 官方接入**；T+15d GA 起有 TUI 可视化面板。反馈请走 GitHub Issue（模板 `feat/model-switcher`），记得**先跑 `cai-agent doctor` 附上脱敏输出**。

---

*文档版本：2026-04-17；维护者：产品。实现细节以 backlog 为准。*
