# Sprint 3 TUI 模型面板手工测试计划（pre-GA）

> 本计划由 QA 在 Sprint 3 启动前编写，冻结日前一天起执行并出报告到 `docs/qa/runs/s3-tui-YYYYMMDD-HHmmss.md`。
> 与 devplan §4.2 DoD、backlog §3.1 / §5.1 / §7 对齐；覆盖 PM 在本 Sprint 给 QA 的明确要求：**add / edit / rm / ping / switch 五个子动作 + 空态 + 切换时 `/compact` 提示**。

---

## 0. 元信息

| 项 | 内容 |
|----|------|
| Sprint | S3（TUI + 发版收尾） |
| 关联故事 | M4（面板）、M5（`/use-model` 升级）、M7（`/status` + session 字段） |
| 执行时机 | 冻结日前一天（T+14d）开始；冻结日当天（T+15d）出最终报告 |
| 缺陷等级 | P0：阻断发版（崩溃 / 数据丢失 / 密钥泄漏）；P1：Sprint 内必修；P2：GA 前可修 |
| Go/No-Go 阈值 | 任一 P0 → No-Go；> 1 条 P1 未闭环 → No-Go；仅剩 P2 → Go |

## 1. 环境准备

### 1.1 机器与依赖

- Windows 11 / macOS / Linux 各至少一台（终端宽度 ≥ 100 列）
- Python 3.11+；`pip install -e "cai-agent[dev]"`
- Textual 能正常启动（`cai-agent ui -w "$PWD"` 进入 TUI 不报错）
- 本地已启动 LM Studio（或 Ollama），用于真实 `ping` 一条通路

### 1.2 Fixtures（冻结日前一天由 QA 统一准备）

| Fixture | 内容 | 用途 |
|---------|------|------|
| `.cai-qa/empty/cai-agent.toml` | 只含 `[agent]`，**无** `[llm]`、**无** `[[models.profile]]` | 空态引导（UC-EMPTY-*） |
| `.cai-qa/legacy/cai-agent.toml` | 只含 `[llm]`（LM Studio）| 兼容回归（`default` 合成 profile） |
| `.cai-qa/trio/cai-agent.toml` | 三个 profile：`local`（lmstudio）、`oai`（preset openai）、`c`（preset anthropic），`active=local` | add/edit/rm/switch 主线 |
| 环境变量 | `OPENAI_API_KEY=sk-qa-oai-fake`、`ANTHROPIC_API_KEY=sk-qa-ant-fake`、`LM_API_KEY=lm-studio` | ping / 切换 |
| 可选 | `OPENROUTER_API_KEY=sk-qa-or-fake` | 仅跨供应商切换场景 |

> **注意**：所有 fake key 只用于 `ping` 层面的 HTTP 往返测试，不应进入真实 chat；遇到返回 401 视为 AUTH_FAIL 命中而非缺陷。

### 1.3 记录模板

每执行一条用例，记录为：

```
UC-XX-Y | PASS/FAIL/BLOCKED | 耗时 / 截图路径 / 详情
```

最终汇总为 `docs/qa/runs/s3-tui-YYYYMMDD-HHmmss.md`，结构对齐 `sprint2-qa-20260418-035002.md`。

---

## 2. 用例矩阵

总计 **40 条**，分八组：入口、add、edit、rm、ping、switch、**上下文进度条（0.5.0 新增）**、集成（空态 / `/compact` / `/status` / session）。

### 2.1 入口与面板骨架（UC-ENTRY-*）

| # | 用例 | 步骤 | 预期 | 影响 DoD |
|---|------|------|------|----------|
| UC-ENTRY-1 | 快捷键打开 | 进 TUI → 按 `Ctrl+M` | 弹出模型面板（ModalScreen），顶部显示 `active=local` 与 `subagent / planner` 行（未设路由时显示 `-`） | M4 / M7 |
| UC-ENTRY-2 | 斜杠命令打开 | 进 TUI → 输入 `/models` 回车 | 同 UC-ENTRY-1（回归旧 `/models` 拉远端列表改到 `/models refresh` 或面板内） | M4 |
| UC-ENTRY-3 | `/models refresh` 不退化 | 打开面板或直接 `/models refresh` | 若直接命令 → 输出可用 model 字符串列表（保留 S2 行为，不影响面板） | M4 兼容 |
| UC-ENTRY-4 | ESC 关闭面板 | 面板打开状态下按 `Esc` | 面板关闭，回到主聊天；当前 active 未变 | M4 |
| UC-ENTRY-5 | 列表列格式 | 打开面板 | 每行含 `id / model / provider / base_url / notes / [active]` 标记；active 行有视觉高亮 | M4 |

### 2.2 新增子动作（UC-ADD-*）

| # | 用例 | 步骤 | 预期 | 严重级上限 |
|---|------|------|------|-----------|
| UC-ADD-1 | 预设新增（openai） | 面板按 `a` → 选 preset `openai` → 填 `id=qa-oai` `model=gpt-4o-mini` → 保存 | 列表新增一行；磁盘 `cai-agent.toml` 出现对应 `[[models.profile]]` 段；`cai-agent.toml.bak` 存在；active 不变 | P0（若 toml 半写 / 崩溃） |
| UC-ADD-2 | 预设新增（anthropic） | 同上 preset 改 `anthropic`，`id=qa-c`，`model=claude-sonnet-4-5-20250929` | `api_key_env=ANTHROPIC_API_KEY`、`anthropic_version`、`max_tokens` 字段自动落位 | P0 |
| UC-ADD-3 | ID 冲突 | `a` 新增，`id` 填已存在的 `local` | 面板弹错误提示（或内联 banner），不写入磁盘，`cai-agent.toml.bak` 不变 | P1 |
| UC-ADD-4 | `api_key` 与 `api_key_env` 互斥 | 手填两个字段 | 保存时拒绝，提示 "不可同时设置 api_key 与 api_key_env" | P1 |
| UC-ADD-5 | 空必填项 | `id` 留空 | 禁用保存按钮 / 保存后报错；不写磁盘 | P2 |
| UC-ADD-6 | 写入即激活 | `a` 新增时勾选 "set active" | 列表新行显示 `[active]`；`/status` 同步 | M4 / M7 |

### 2.3 编辑子动作（UC-EDIT-*）

| # | 用例 | 步骤 | 预期 |
|---|------|------|------|
| UC-EDIT-1 | 改 model 字段 | 选中 `oai` 按 `e` → 把 `model` 改为 `gpt-4o-mini` → 保存 | 磁盘更新；`.bak` 落地；列表刷新；未改变 active |
| UC-EDIT-2 | 改 provider 会触发派生字段 | `e` 把 `oai` 的 provider 从 `openai` 改成 `anthropic` | 系统提示会清空 `base_url` / `api_key_env` 并按预设回填；保存后重新加载 profile |
| UC-EDIT-3 | 编辑当前 active | 选中 `[active]` 行 `e` | 保存后 `Settings` 重新投影，`/status` 立即反映新 model |
| UC-EDIT-4 | 取消编辑 | `e` 打开后按 `Esc` | 磁盘无改动；`.bak` 无新内容 |

### 2.4 删除子动作（UC-RM-*）

| # | 用例 | 步骤 | 预期 | 严重级上限 |
|---|------|------|------|-----------|
| UC-RM-1 | 删非 active | 选中 `c` 按 `d` → 确认 | 磁盘该行消失；active 保持 `local`；`.bak` 存在 | P0（崩溃/遗漏） |
| UC-RM-2 | 删 active | 选中 `local`（active）按 `d` → 确认 | 删除后 active 自动回退到列表第一条（alpha 字典顺) 或下一条；不崩溃；banner 提示 "active 已切到 X"；`/status` 同步 | P0 |
| UC-RM-3 | 删最后一条 | 只剩 1 条时 `d` | 拒绝删除 / 强制保留；如允许，退出面板后 `cai-agent doctor` 明确报 `no profile` | P1 |
| UC-RM-4 | 取消删除 | 确认对话框选 "取消" | 无磁盘变化 | P2 |
| UC-RM-5 | 删除后 ping 无残留 | UC-RM-1 后 `t` 测试剩余 profile | `ping` 正常，不引用已删条目 | P2 |

### 2.5 连通性测试（UC-PING-*）

| # | 用例 | 步骤 | 预期 |
|---|------|------|------|
| UC-PING-1 | 本地 OK | 选 `local` 按 `t` | banner 显示 `OK`；无真实 chat token 消耗；日志不打印 key |
| UC-PING-2 | env 未设 | 临时 `unset LM_API_KEY` 后 `t` | banner `ENV_MISSING`，点名 `LM_API_KEY` |
| UC-PING-3 | 401 | 用假 key 打命中 401 的路径 | banner `AUTH_FAIL` + `http_status=401` |
| UC-PING-4 | 网络超时 | 改 `base_url` 到不可达地址 | banner `TIMEOUT` 或 `NET_FAIL`，≤ profile.timeout_sec + 2s |
| UC-PING-5 | Anthropic ping 头 | 选 `c` 按 `t` | 若开 Wireshark/mock，`x-api-key` 与 `anthropic-version` 头齐全；URL 为 `{base}/v1/models` |

### 2.6 切换（UC-SWITCH-*） — **本 Sprint 核心**

| # | 用例 | 步骤 | 预期 | 严重级上限 |
|---|------|------|------|-----------|
| UC-SWITCH-1 | Enter 切换 | 选中 `oai` → Enter | 列表 `[active]` 标记迁移到 `oai`；`cai-agent.toml` 中 `[models] active = "oai"`；`/status` 立刻同步 | P0（若 active 不持久化） |
| UC-SWITCH-2 | CLI `/use-model <profile_id>`（M5） | 主输入框 `/use-model oai` | 按 profile id **整组切换**；`/status` 显示 profile 名 | P0 |
| UC-SWITCH-3 | `/use-model <model_id>` 回退 | `/use-model gpt-4o-mini`（无同 id 的 profile） | 回退旧行为：仅换 `model` 字段，提示 "未命中 profile id，按 model id 处理"；不污染 TOML | P1 |
| UC-SWITCH-4 | **跨 provider 切换弹确认（§7 风险）** | 当前 active=`local`（OpenAI 兼容）→ Enter 切到 `c`（anthropic） | **弹确认对话框**："上下文窗口可能不一致，建议 `/compact` 或 `/clear`"；用户可选择 "继续切换 / 继续并 /compact / 取消" | P0（漏弹即阻断） |
| UC-SWITCH-5 | 选 `/compact` 路径 | UC-SWITCH-4 中选 "继续并 /compact" | 切换完成 + 触发 compact；对话区新增一次压缩摘要 | P1 |
| UC-SWITCH-6 | 同 provider 不弹确认 | `local` (openai_compatible) → `oai`（openai） | **不弹**跨 provider 提示（只在 openai 系 ↔ anthropic 系之间弹） | P2 |
| UC-SWITCH-7 | 切换后首条消息路由 | UC-SWITCH-1 后发一句 `hello` | 抓包/mock 命中的 base_url 为新 profile；首条无延迟错配 | P0 |
| UC-SWITCH-8 | `CAI_ACTIVE_MODEL` 覆盖 | 退出 TUI → `export CAI_ACTIVE_MODEL=c` → 重进 TUI | 面板顶部 `active=c`；磁盘 `[models] active` 保持原值（env 仅运行时覆盖） | P1 |

### 2.7a 上下文使用进度条（UC-CTX-*） — **0.5.0 新增**

| # | 用例 | 步骤 | 预期 | 严重级上限 |
|---|------|------|------|-----------|
| UC-CTX-1 | 启动即显 | 用 `.cai-qa/legacy`（只有 `[llm]`，无 `context_window`）进 TUI | 进度条立即显示，分母 = `8192`，值为 `~N`（估算，带 `·估算` 字样） | P1（缺失即不可见） |
| UC-CTX-2 | `[llm].context_window` 生效 | 在 `cai-agent.toml` 设 `[llm] context_window = 32768` 后进 TUI | 启动进度条分母 = `32,768` | P0（分母错） |
| UC-CTX-3 | profile 覆盖 `[llm]` | `.cai-qa/trio` + 给 `local` 加 `context_window = 16384`，其它不设；active=`local` | 分母 = `16,384`（profile 优先） | P1 |
| UC-CTX-4 | 环境变量兜底 | 删除 `[llm].context_window`；`export CAI_CONTEXT_WINDOW=12345` | 分母 = `12,345` | P2 |
| UC-CTX-5 | 首条响应后切真 | 估算态下发一次 `hello` | 一次响应回来后，`~` 与 `估算` 字样消失；条上分子 = 服务端 `usage.prompt_tokens`（可用 mock / 开发者工具核对） | P0（不切真 = 永远估算 = 误导） |
| UC-CTX-6 | 颜色阈值 | 准备能塞满 context 的长对话（或 `[llm] context_window = 1024` 故意调小）发几轮 | < 70% 绿，70–89% 黄，≥ 90% 红；阈值与实际百分比一致 | P1 |
| UC-CTX-7 | `/clear` 回落估算 | 任意对话后 `/clear` | 进度条回到 `~N 估算`，并按空对话重新估算；下一次响应再切真 | P2 |
| UC-CTX-8 | `/use-model` 切换重置 | 发过一次消息后 `/use-model c`（跨 provider） | 进度条 **分母立即更新** 为新 profile 的 `context_window`（若有），数字回落估算；跨 provider 确认框与 UC-SWITCH-4 叠加不冲突 | P1 |
| UC-CTX-9 | 空响应兜底 | 用 Qwen3 / DeepSeek-R1 等 reasoning 模型跑一段复杂问题，故意让 `content=""`、`reasoning_content` 很大 | 对话区出现 `{"type":"finish","message":"[empty-completion] ..."}` envelope；不崩溃、不空转到 `max_iterations`；进度条仍按服务端 `prompt_tokens` 正常刷新 | P0（回归崩溃即 No-Go） |
| UC-CTX-10 | 不泄露到网络 | 抓包 / mock 看请求 body | 任何请求体都 **不含** `context_window` 字段（该字段仅 TUI 显示，禁止随请求发送） | P0（合规） |
| UC-CTX-11 | 欢迎页诊断 | 进 TUI 看首屏 | 含 `配置:` 绝对路径、`上下文窗口: N tokens` 及来源说明（profile / llm / env / default 之一）；与 `/status` 的 `source=` 一致 | P1 |
| UC-CTX-12 | Enter 即时重估 | 首轮响应很慢时，输入长 user 按 Enter | 在模型返回前，进度条分子已更新为带 `~` 的估算（含刚提交内容）；响应后切真 | P2 |

> **关联代码路径**：`cai_agent.config.Settings.context_window` / `context_window_source`、`cai_agent.llm.get_last_usage() / estimate_tokens_from_messages()`、`cai_agent.graph.llm_node` 的 `phase="usage"` 事件、`cai_agent.tui.CaiAgentApp._refresh_context_bar`。自动化覆盖见 `cai-agent/tests/test_context_usage_bar.py`（21+ 条）与 `test_llm_empty_content_guard.py`（7 条）。

### 2.7 集成项（UC-INT-*）

| # | 用例 | 步骤 | 预期 | DoD |
|---|------|------|------|-----|
| UC-INT-1 | **空态引导** | 用 `.cai-qa/empty` 配置进 TUI → `Ctrl+M` | 面板显示空态卡片："还没有模型 profile，按 `a` 添加第一个" + 预设按钮（openai / anthropic / lmstudio / ollama / openrouter） | M4 空态 |
| UC-INT-2 | 空态新增首条后变常态 | UC-INT-1 里按 `a` → preset lmstudio → 保存 | 面板切换到常规列表视图；`active` 自动设为新条目 | M4 |
| UC-INT-3 | `/status` 扩展（M7） | 任何状态下 `/status` | 输出含 `profile: <id>` 行；若设置了 subagent/planner，增 `subagent: <id>` / `planner: <id>` | M7 |
| UC-INT-4 | session.json 落盘含 profile（M7） | `/save session.json` → 用编辑器打开 | JSON 含 `profile` 字段（值为当前 active profile id）；不得出现 `api_key` 明文 | M7 + §5.2 |
| UC-INT-5 | `/load` 恢复 profile | 先切 `c` → `/save` → 切 `local` → `/load session.json` | 加载后 active 回到 `c`，TUI 顶部与 `/status` 同步 | M7 |
| UC-INT-6 | 回归：`workflow` / `observe` | 退出 TUI 跑 `cai-agent workflow .regression-workflow.json --json` 与 `cai-agent observe --json` | exit 0；输出 envelope 齐全，无字段缺失 | devplan §4.2 D13 |
| UC-INT-7 | 全量回归脚本 | `py scripts/run_regression.py` | 27/27 PASS；新 `regression-*.md` 落地 | devplan §4.2 最后一条 |

---

## 3. 配合 Sprint 3 的其它 QA 动作

### 3.1 回归节奏

- **T+14d 上午**：冻结前预演，跑 `py -m pytest -q cai-agent/tests`（阈值 ≥ 100 passed） + 本计划 UC-ADD-* / UC-RM-* / UC-SWITCH-1/2/4 共 ~12 条。
- **T+15d 上午**：冻结日正式跑全部 40 条 + `scripts/run_regression.py`。
- **T+15d 下午**：报告产出 + Go/No-Go 评审。

### 3.2 产出物

| 产物 | 路径 | 负责人 |
|------|------|--------|
| 用例执行记录 | `docs/qa/runs/s3-tui-YYYYMMDD-HHmmss.md` | QA |
| 自动化回归报告 | `docs/qa/runs/regression-YYYYMMDD-HHmmss.md`（脚本自动） | QA |
| 缺陷清单 | 以 GitHub Issue + 标签 `feat/model-switcher` / `qa-S3` 记录 | QA |
| Release Note 片段 | 合入 `CHANGELOG.zh-CN.md`（devplan §6.3 模板） | PM |

### 3.3 关联文件

- 需求：[`docs/MODEL_SWITCHER_BACKLOG.zh-CN.md`](../MODEL_SWITCHER_BACKLOG.zh-CN.md)（§3.1 TUI、§5 验收、§7 风险）
- 执行计划：[`docs/MODEL_SWITCHER_DEVPLAN.zh-CN.md`](../MODEL_SWITCHER_DEVPLAN.zh-CN.md)（§4.2 DoD、§5.2 矩阵）
- Beta 报告：[`docs/qa/runs/sprint2-qa-20260418-035002.md`](runs/sprint2-qa-20260418-035002.md)
- Beta 复核：[`docs/qa/runs/sprint2-qa-reverify-20260418-035910.md`](runs/sprint2-qa-reverify-20260418-035910.md)

---

## 4. 交接说明

- **给 Dev A（M4）**：UC-ENTRY-*、UC-ADD-*、UC-EDIT-*、UC-RM-*、UC-INT-1/2 是你的验收重点；UC-RM-2（删 active 自动回退）是历史容易遗漏点，请在 M4 单测里直接覆盖。
- **给 Dev B（M5 + M7）**：UC-SWITCH-*（尤其 4/5/7）与 UC-INT-3/4/5 对应你的模块；跨 provider 的 `/compact` 提示是 backlog §7 风险项的落地。
- **给 PM**：GA tag 推送前请确认所有 P0/P1 已闭环；P2 可并入 "GA+1 hotfix" 清单。
- **给内测用户（T+15d GA 公告）**：按 devplan §6.3 "升级后自检" 顺序走一遍 `doctor / /status / 打开 TUI 面板` 三步。

---

*本计划维护者：QA；版本：2026-04-18 初稿；Sprint 3 启动后视实现细节微调。*
