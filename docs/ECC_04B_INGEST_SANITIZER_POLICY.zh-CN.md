# ECC-N04-D02：资产生态 ingest sanitizer 策略（草案）

> 状态：`draft`（条件立项阶段）。本文件给出“外部资产进入本仓前”的最小净化策略，目标是 **不可信资产不直接执行**。

## 1. 目标与边界

### 1.1 目标

- 对外部资产（rules/skills/hooks/plugins）做统一预检与风险分级。
- 在未完成 `ECC-N04-D03`（provenance/signature/trust）前，默认按“低信任输入”处理。
- 输出可机读结论，供后续 `import/install` 或 review 流程消费。

### 1.2 本轮不做

- 不实现在线市场拉取与自动安装。
- 不在本轮引入真实签名验签链路（仅保留字段与判定位）。
- 不自动执行外部资产中的 `hooks` / `script` / `command`。

## 2. 输入对象与风险面

sanitizer 处理对象（按 `ecc_asset_registry_v1` 草案）：

1. 资产元数据：`source`、`license`、`signature`、`version`、`trust`。
2. 资产文件内容：`rules`、`skills`、`hooks`、`plugins`。
3. 执行面字段：`hooks[*].command`、`hooks[*].script`、插件启动入口/外部命令声明。

高风险面（当前必须拦截或人工确认）：

- 明显破坏性命令（`rm -rf`、`format`、`del /f` 等）。
- 下载并立即执行模式（`curl ... | bash`、`wget ... | sh`）。
- 试图逃逸工作区边界的脚本路径（`../`、绝对路径越界）。
- 混淆执行链（多段 shell 拼接、可疑 PowerShell 编码执行）。

## 3. 最小策略（v1 草案）

## 3.1 默认策略

- 默认 `deny-exec`：外部 ingest 资产在通过审查前一律不可执行。
- 默认 `metadata-first`：先校验 metadata 完整性，再决定是否进入内容审查。
- 默认 `workspace-only`：所有脚本路径必须可解析且位于工作区内。

## 3.2 决策分层

1. **结构层**：JSON/schema/字段完整性检查，不通过即 `reject`。
2. **策略层**：命令与脚本静态规则匹配。
   - 命中危险模式：`block`
   - 需进一步审查：`review`
   - 无高危命中：`allow_metadata_only`（注意：仍不代表可执行）
3. **执行层（预留）**：仅在后续 trust policy 满足时开放。

## 3.3 与现有 hooks 安全规则对齐

现有 `hook_runtime.py` 已具备：

- 危险命令片段识别（standard/strict 模式）。
- 脚本路径必须位于工作区下。
- `minimal/standard/strict` profile 的执行门控。

`ECC-N04-D02` 约定直接复用这套判定语义作为 ingest 预检基线，避免出现“导入允许、运行阻断”口径漂移。

## 4. 机读输出建议

建议输出 `ecc_ingest_sanitizer_policy_v1`：

- `policy_mode`: `deny_exec` | `review_required`
- `checks[]`: 每项含 `id`、`status`（`pass`/`warn`/`fail`）、`reason`
- `decision`: `reject` | `review` | `allow_metadata_only`
- `blocked_patterns[]`: 触发的危险模式
- `next_actions[]`: 建议操作（人工 review、补 license、补 source 等）

## 5. 验收口径（D02）

- 有独立 sanitizer policy 文档（本文件）。
- 有机读快照样例，能表达 `reject/review/allow_metadata_only` 三态之一。
- ROADMAP/TODOS/CHANGELOG 与文档结论一致。

## 6. 后续：`ECC-N04-D03`

来源、签名与信任等级与 sanitizer 的合流口径见 **`docs/ECC_04C_INGEST_PROVENANCE_TRUST.zh-CN.md`** 与 **`docs/schema/ecc_ingest_provenance_trust_v1.snapshot.json`**。
