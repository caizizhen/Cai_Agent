# Test start list

This page is the English summary for the testing TODOs that mirror the current developer backlog. The detailed testing checklist lives in [`TEST_TODOS.zh-CN.md`](TEST_TODOS.zh-CN.md).

Canonical planning sources:

- [`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md)
- [`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md)
- [`ISSUE_BACKLOG.zh-CN.md`](ISSUE_BACKLOG.zh-CN.md)

## Current baseline

Validated on 2026-04-25 from the repo root:

- `python -m pytest -q cai-agent/tests`: **714 passed**, **3 subtests passed**
- `python scripts/smoke_new_features.py`: **PASS**
- `QA_SKIP_LOG=1 python scripts/run_regression.py`: **PASS**

## Priority testing set

| ID | Focus | Main test entry points |
|---|---|---|
| `REL-01a` | release / doctor / changelog / feedback flow | `test_release_ga_cli.py`, `test_doctor_cli.py`, `test_release_changelog_cli.py`, feedback tests |
| `CC-01a` | MCP presets and WebSearch/Notebook onboarding | `test_cli_misc.py`, `test_mcp_serve_roundtrip.py`, smoke |
| `CC-02a` | install / init / upgrade guidance | `test_init_presets.py`, `test_doctor_cli.py` |
| `HM-01a` | profile schema and persistence | `test_model_profiles_*`, `test_model_routing.py`, `test_tui_model_panel.py` |
| `HM-03a` | Discord production path | `test_gateway_discord_*`, `test_gateway_discord_slack_cli.py` |
| `HM-04` | ops/gateway/status payload unification + dynamic read-only dashboard | `test_ops_dashboard_html.py`, `test_ops_http_server.py`, ops CLI tests |
| `HM-05a` | user-model store/query/learn loop | `test_user_model_store.py`, `test_memory_user_model_export.py`, `test_memory_user_model_store_cli.py` |
| `ECC-01a` | rules/skills/hooks assetization | `test_ecc_layout_cli.py`, `test_hooks_*`, `test_skills_*`, `test_agentskills_*` |
| `ECC-02a` | routing/profile/budget product path | `test_model_routing.py`, `test_cli_misc.py` (cost budget), `test_cost_aggregate.py`, `test_factory_routing_and_security.py` |

## Usage

Use [`TEST_TODOS.zh-CN.md`](TEST_TODOS.zh-CN.md) as the QA companion to [`DEVELOPER_TODOS.zh-CN.md`](DEVELOPER_TODOS.zh-CN.md). Each task should normally cover at least:

- pytest
- smoke or regression
- manual / real-environment verification when the feature is user-facing or platform-facing
