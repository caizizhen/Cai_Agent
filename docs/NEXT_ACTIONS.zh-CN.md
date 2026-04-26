# NEXT_ACTIONS.zh-CN.md

> 低 token 开发入口。新的开发会话先读本页，再按本页指向读取少量文件。
>
> 最后同步：2026-04-26。状态来源：`DEVELOPER_TODOS.zh-CN.md`、`TEST_TODOS.zh-CN.md`、`PRODUCT_GAP_ANALYSIS.zh-CN.md`、`ROADMAP_EXECUTION.zh-CN.md`、`IMPLEMENTATION_STATUS.zh-CN.md`。

## 维护契约

本页是“当前开发状态”的短摘要，不承载完整 backlog。每次完成开发、调整优先级、更新测试结论或变更 roadmap 时，必须同步更新本页。

- 新任务进入当前轮：加入“现在做”。
- 当前任务完成：移到“刚完成”，并写清验证命令。
- 任务降级：移到“稍后/条件项”，并写清原因。
- 细节太长：只保留一句话和链接，详情放回 `DEVELOPER_TODOS.zh-CN.md` / `TEST_TODOS.zh-CN.md`。

## 当前结论

上一轮 `CC-N01-D05` 命令中心发现链路和 `CC-N02-D02` feedback bug 结构化字段已经完成。当前最好继续沿着“安装/修复/反馈闭环”和“profile/home/sync 产品化”推进，避免重新打开已经 Done 的 gateway、runtime、model gateway 大块。

`ECC-N04-D03`（provenance/signature/trust 中英策略 + `ecc_ingest_provenance_trust_v1` 快照 + `test_ecc_ingest_schema_snapshots`）已交付并归档；ingest 下一里程碑在 **`ECC-N02-D03/D04`**（pack import/repair）与 **`CC-N03-D04`**（**`plugins sync-home --apply`** 覆盖保护），而非重复扩写 D01～D03 文档。

**`CC-N02`** 能力级 **Done**。**`HM-N01-D03`** 与 **`ECC-N01-D02`～`D04`**、**`ECC-N02-D01`/`D02`**、**`CC-N01-D04`**（upgrade 命令面）已于本轮收口（见下表「刚完成」）。下一优先建议从 **`DEVELOPER_TODOS.zh-CN.md` §8** 取 **`CC-N03-D04`**、**`ECC-N02-D03`** 或 **`HM-N01-D01`**（profile home schema 深化）。

`DEVELOPER_TODOS.zh-CN.md` §4～§8、`PRODUCT_GAP_ANALYSIS.zh-CN.md` §2/§4、`docs/PRODUCT_GAP_ANALYSIS.md` 已与 ROADMAP 中 `HM-N05`～`HM-N10` 与 **`ECC-N04-D01`～`D03`** 等交付态对齐（2026-04-26）。

## 现在做

| 顺位 | ID | 状态 | 目标 | 主要入口 | 最小验证 |
|---|---|---|---|---|---|
| 1 | `CC-N03-D04` | Ready | **`plugins sync-home --apply`**：冲突策略、备份/回滚提示（承接 D02 计划 + D03 drift） | `plugin_registry.py`、`exporter.py`、`__main__.py` | pytest + smoke；与 **`plugins_sync_home_plan_v1`** / **`plugins_home_sync_drift_v1`** 对齐 |

## 刚完成

| ID | 完成日期 | 结果 | 验证/证据 |
|---|---|---|---|
| `CC-N03-D03` | 2026-04-26 | **`plugins_home_sync_drift_v1`**：与 **`ecc_home_sync_drift_v1`** 同源；**`doctor --json` → plugins.home_sync_drift**；**`repair_plan_v1.plugins_sync_home_preview_commands`**；**`api_doctor_summary_v1.plugins_home_sync_drift_targets`**；文本 doctor 插件区漂移摘要。 | python -m pytest -q cai-agent/tests: PASS (834 passed, 3 subtests)<br>python scripts/smoke_new_features.py: PASS |
| `CC-N03-D02` | 2026-04-26 | 新增 **`cai-agent plugins sync-home`**（**`plugins_sync_home_plan_v1`**，与 export/ecc 同源目录约定；codex manifest_only）；**`doctor_upgrade_hints_v1`** 增补推荐命令；smoke 覆盖。 | python -m pytest -q cai-agent/tests: PASS<br>python scripts/smoke_new_features.py: PASS |
| `ECC-N01-D02`/`D03`/`D04` + `ECC-N02-D01`/`D02` + `CC-N01-D04` + `HM-N01-D03` | 2026-04-26 | **`ecc sync-home`**（dry-run/apply）、**`export --dry-run`**；**`export_ecc_dir_diff_v1`** 支持 codex/opencode；**`ecc_home_sync_drift_v1`** 接入 doctor/API summary；**`repair_plan_v1.ecc_sync_commands`**；**`ecc pack-manifest`**（`ecc_asset_pack_manifest_v1`）；**`doctor_upgrade_hints_v1`**；**`load_agent_settings_for_workspace`** + gateway **discord/slack `--config`**。 | python -m pytest -q cai-agent/tests: PASS (830 passed, 3 subtests)<br>python scripts/smoke_new_features.py: PASS (NEW_FEATURE_CHECKS_OK) |
| `HM-N01-D02`/`D04`/`D05` | 2026-04-26 | 交付 `models clone` / `clone-all` / `alias`（`models_alias_v1` 等）与 doctor **`profile_home_migration`**（`profile_home_migration_diag_v1`）。 | python -m pytest -q cai-agent/tests: PASS (825 passed, 3 subtests)<br>python scripts/smoke_new_features.py: PASS (NEW_FEATURE_CHECKS_OK) |
| `CC-N02-D04` | 2026-04-26 | Harden feedback bundle and JSONL export redaction: sanitize_feedback_text workspace/home paths and Slack tokens, sanitize append_feedback, redact export rows, feedback_bundle_export_v1 dest_placement and warnings for external --dest, release runbook bundle step. | python -m pytest -q cai-agent/tests/test_feedback_cli.py cai-agent/tests/test_feedback_export.py cai-agent/tests/test_feedback_bundle_cli.py cai-agent/tests/test_doctor_cli.py: PASS<br>python -m pytest -q cai-agent/tests: 820 passed, 3 subtests passed<br>python scripts/smoke_new_features.py: PASS (NEW_FEATURE_CHECKS_OK) |
| `ECC-N04-D03` | 2026-04-26 | Deliver ECC-N04-D03 provenance/trust bilingual policy, ecc_ingest_provenance_trust_v1 snapshot, schema README and roadmap; add regression test for ingest draft JSON. | python -m pytest -q cai-agent/tests: 817 passed, 3 subtests passed<br>python scripts/smoke_new_features.py: PASS (NEW_FEATURE_CHECKS_OK) |
| `DOC-AUTO-FINALIZE` | 2026-04-26 | 建立任务完成后的自动文档同步脚本和低 token 完成协议 | pytest -q -p no:cacheprovider cai-agent/tests/test_finalize_task_script.py: 1 passed |
| `CC-N01-D05a-e` | 2026-04-26 | `command_discovery_v1`、TUI slash 模板命令、doctor/repair command_center、最小命令中心资产面已落地 | `test_command_registry.py`、`test_tui_slash_suggester.py`、repair/doctor CLI smoke |
| `CC-N02-D02a-d` | 2026-04-26 | `feedback bug` 支持 `repro_steps`、`expected`、`actual`、`attachments`，human/json 输出对齐 | `test_feedback_cli.py` 与 CLI smoke |
| `MODEL-P0` | 2026-04-25 前 | model gateway、capabilities、health/chat-smoke、routing explain、OpenAI-compatible API 地基已完成 | `PRODUCT_PLAN.zh-CN.md`、`COMPLETED_TASKS_ARCHIVE.zh-CN.md` |
| `HM-N05/HM-N07/HM-N08/HM-N09/HM-N10/HM-N11` 多项 | 2026-04-25 前 | gateway 新平台、federation、voice boundary、memory/tool/runtime contracts 已进入 Done 或持续维护 | `ROADMAP_EXECUTION.zh-CN.md`、`CHANGELOG.zh-CN.md` |

## 暂缓/条件项

| ID | 状态 | 原因 |
|---|---|---|
| `CC-N05` Desktop / GUI | Explore | 先做方案或 PoC，不抢 P0/P1 开发队列 |
| `CC-N07` Remote / web / mobile / cloud review | Conditional | 需要明确业务授权、部署边界和成本边界 |
| `HM-N11` Cloud runtime real backend | Conditional | 默认保持 local/docker/ssh，云后端只在授权后进入实现 |
| 原生 WebSearch / Notebook | OOS | 继续走 MCP 优先，不重写已有生态能力 |

## 开发前只读清单

- 修 feedback：读 `feedback.py` 和相关测试，不读全量 docs。
- 修 profile：读 `profiles.py`、`doctor.py`、相关 profile/model 测试。
- 修 ECC/home sync：读 `ecc_layout.py`、`exporter.py`、`plugin_registry.py` 和 `docs/CROSS_HARNESS_COMPATIBILITY.zh-CN.md` 的相关段落。
- 做文档/路线图：先读 `docs/README.zh-CN.md`，再读被点名的主文档。

## 开发结束回写

完成任何任务后，按顺序回写：

1. 跑对应测试，记录命令和结果。
2. 运行 `scripts/finalize_task.py --task-id <ID> --summary "<完成内容>" --verification "<验证命令: PASS>"`，自动更新本页、完成归档、测试验证记录和 QA run。
3. 如本次改动影响完整 backlog，再同步 `DEVELOPER_TODOS.zh-CN.md` 对应 ID。
4. 如本次改动是用户可见行为或发布项，再同步 `CHANGELOG.zh-CN.md` / `CHANGELOG.md`。
5. 确认工作区只包含本次应提交文件后，提交并推送。
