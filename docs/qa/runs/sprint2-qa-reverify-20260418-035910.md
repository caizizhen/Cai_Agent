# Sprint 2 冻结后 QA 复核报告（post-freeze reverify）

> 承接 [sprint2-qa-20260418-035002.md](sprint2-qa-20260418-035002.md) 的 Go 决议，本报告由新 QA 在相同 HEAD 上独立复核自动化层，记录与前次偏差。

## 0. 基本信息

| 项 | 内容 |
|----|------|
| Sprint | S2（多供应商 + 路由） — **冻结后复核** |
| 分支 | `feat/model-switcher`（工作树） |
| 本报告生成时间 | 2026-04-18 03:59:10（UTC+8 本机） |
| Repo HEAD | `4e5f26799df3e442ef872479a6d3956afe6ec832`（与前次同一 commit） |
| Python | 3.13.13 / Windows 11 (10.0.26200) |
| 工作树状态 | dirty（大量 untracked + `cai-agent.toml` 本地改动，未影响测试结果） |

## 1. 复核结论

**复核通过（Confirm Go）** — 自动化维度无任何退步；手工矩阵脚本已不可复现，留作下轮改进项。

## 2. 复核明细

### 2.1 自动化基线（PASS）

| 项 | 命令 | 本次结果 | 前次结果 | 比对 |
|----|------|----------|----------|------|
| pytest 全量 | `py -m pytest -q cai-agent/tests` | **100 passed / 0.61s** | 100 passed / 0.62s | 一致 |
| Model Switcher 专项 | `py -m pytest -q cai-agent/tests/test_model_profiles_* test_llm_anthropic_adapter.py test_llm_factory_dispatch.py test_factory_routing_and_security.py` | **70 passed / 0.35s** | — | 首次细分 |
| 脚本回归 | `py scripts/run_regression.py` | **PASS（27/27）** | PASS（27/27） | 一致 |
| 本次回归报告 | `docs/qa/runs/regression-20260418-035300.md` | Overall PASS | — | 同 HEAD 新快照 |

### 2.2 手工矩阵（§5.1.1 六条供应商用例）

| 场景 | pytest 覆盖证据（本次实跑确认） | 状态 |
|------|----------------------------------|------|
| ChatGPT 官方 `provider=openai` | `test_llm_factory_dispatch::ChatCompletionByRoleTests::test_active_openai_dispatches_to_openai_adapter` | PASS |
| Claude 原生 `provider=anthropic` | `test_llm_anthropic_adapter::AnthropicAdapterTests::test_happy_path_request_and_parse`（断言 `/v1/messages` + `x-api-key` + `anthropic-version` + `system` 独立字段 + `max_tokens`） | PASS |
| Claude via OpenRouter | `test_llm_factory_dispatch::ChatCompletionByRoleTests::test_subagent_role_routes_to_subagent_profile`（openai_compatible → openai 适配器） | PASS |
| 本地 LM Studio / Ollama | `test_model_profiles_cli::test_add_then_list_then_use_then_rm`（preset=lmstudio）+ legacy `[llm]` 合成 default profile 回归 | PASS |
| `/use-model` 跨 provider 切换 | `test_factory_routing_and_security::FactoryDispatchProjectionTests::test_planner_role_projects_to_anthropic` + `test_subagent_role_projects_to_local_openai_compatible` | PASS |
| `--preset anthropic` add→use | `test_model_profiles_config::test_apply_preset_merges_user_fields` + CLI 闭环 | PASS |

### 2.3 安全规则（M13）

- `test_factory_routing_and_security::SecurityScanProfileRuleTests`：
  - `test_anthropic_sk_ant_flagged_high` — PASS（命中 `anthropic_api_key` + `cai_profile_plaintext_api_key`，`ok=False`）
  - `test_openrouter_sk_or_flagged_high` — PASS
  - `test_placeholder_api_key_not_flagged_high` — PASS（`api_key = "lm-studio"` 不阻断）
  - `test_api_key_env_does_not_trigger_profile_rule` — PASS
- `cai-agent security-scan --json`（回归脚本内）：exit 0，对当前仓 `ok=True`。

## 3. 与前次报告的差异

| 项 | 前次报告 | 本次复核 | 说明 |
|----|----------|----------|------|
| 手工 15 条矩阵驱动脚本 | `.tmp_qa/sprint2_matrix.py` | **脚本已不存在于工作树** | git 状态快照含该路径，但物理文件已删。一次性脚本未入仓，本次无法复现 PASS。 |
| 引用的回归报告 | `regression-20260418-034808.md` | `regression-20260418-035300.md` | 都是同一 HEAD 的绿回归，步骤结果逐行一致 |
| 全量 pytest 数量 | 100 passed | 100 passed | 无退步 |

## 4. 风险与后续建议

### 4.1 低风险（不阻断 beta）

1. **一次性脚本消失**：手工矩阵 15 条只有文本证据。建议把 `sprint2_matrix.py` 落到 `scripts/qa/sprint2_matrix.py` 或直接把其断言合入 `cai-agent/tests/test_sprint2_qa_matrix.py`，Sprint 3 冻结前补齐。
2. **真实供应商冒烟仍空缺**：backlog §5.1.1 明确"有真实 key 时手工验证"。内测按 devplan §6.2 指引在各自环境跑。QA 侧保持 mock-only 基线。
3. **用户级 `~/.cai-agent/models.toml` 回退**：backlog §2.3 列为可选，beta 允许不实装。

### 4.2 Sprint 3 需要补齐的 QA 测试（建议列表）

| # | 建议补测 | 理由 |
|---|----------|------|
| T1 | OpenAI adapter wire-level mock（断言 `Authorization: Bearer` + `POST /v1/chat/completions` body） | §5.1.1 第 1 条目前只走到 factory 层，没下沉到 HTTP 断言 |
| T2 | `--preset anthropic` CLI 链路：`models add --preset anthropic` → `use` → `ping` mock | 目前 preset=anthropic 只在 `apply_preset` 单测，没 CLI e2e |
| T3 | `cai-agent doctor` 对 **每个 profile** 做 ping 并标记 AUTH_FAIL（backlog §3.3） | `doctor.py` 目前只展示 active profile 的状态，不逐个 profile 检查 |
| T4 | `session.json` 不含 `api_key` 明文的回归断言（backlog §5.2 倒数第 2 条） | 目前无显式断言，仅 `_mask_api_key` 在 doctor 上生效 |
| T5 | TUI `/use-model` 跨 provider 切换（M5） | S3 DoD 强相关，目前 factory 层已 OK，TUI 还没测 |

## 5. Go / No-Go

**Confirm Go** — 维持前次 QA 的 beta 发版建议，`v-model-switcher-beta` tag 可推。

理由：
- 同一 HEAD 的自动化全部复核通过，100 pytest + 27 脚本回归零退步；
- 六条供应商用例在 pytest 层有明确证据链；
- 新发现的缺口（脚本未入仓、doctor 多 profile ping 未接）都是 **S3 改进项**，不阻断 beta。

---

*本报告维护者：QA（复核岗）；承接：[sprint2-qa-20260418-035002.md](sprint2-qa-20260418-035002.md)；关联：[MODEL_SWITCHER_BACKLOG.zh-CN.md](../../MODEL_SWITCHER_BACKLOG.zh-CN.md)、[MODEL_SWITCHER_DEVPLAN.zh-CN.md](../../MODEL_SWITCHER_DEVPLAN.zh-CN.md)。*
