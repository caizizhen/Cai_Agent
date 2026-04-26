# Implementation status (rolling summary)

> **English** (default for this file). Chinese: [`IMPLEMENTATION_STATUS.zh-CN.md`](IMPLEMENTATION_STATUS.zh-CN.md).  
> Authoritative execution checklist: [`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md). Detailed changes: root **`CHANGELOG.md`** / **`CHANGELOG.zh-CN.md`**.

Current product target: integrate **Claude Code + Hermes Agent + Everything Claude Code** in one runtime. Planning details live in [`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md) and [`PRODUCT_GAP_ANALYSIS.zh-CN.md`](PRODUCT_GAP_ANALYSIS.zh-CN.md).

## Recently shipped (developer-facing)

The following landed on **`main`** around the **0.7.0** window (see **CHANGELOG §0.7.0** for the full list):

| Area | What shipped | Where to look |
|------|----------------|---------------|
| **Design backlog contracts (HM-04c / HM-03e / HM-05d)** | Added **`ops_dashboard_interactions_v1`** for dashboard dry-run previews, **`gateway_production_summary_v1`** via **`gateway prod-status --json`**, and **`memory_provider_contract_v1`** via **`memory provider --json`**; all are local/read-side contracts with no external service dependency | `ops_dashboard.py`, `ops_http_server.py`, `gateway_production.py`, `memory.py`, `test_ops_http_server.py`, `test_gateway_lifecycle_cli.py`, `test_memory_provider_contract_cli.py` |
| **Cloud runtime conditional tranche (HM-N11-D01 / D02)** | Added explicit cloud-runtime go/no-go gating docs (`CLOUD_RUNTIME_OOS` zh/en) and exposed **`runtime_backend_interface_v1`** through `runtime_registry_v1.interface`, aligning `local/docker/ssh` interface + config-key surfaces for future conditional backend onboarding | `docs/CLOUD_RUNTIME_OOS.zh-CN.md`, `docs/CLOUD_RUNTIME_OOS.md`, `runtime/registry.py`, `test_runtime_local.py` |
| **CC-N02-D04 feedback export redaction** | Tightened `sanitize_feedback_text`, sanitized persistence for `append_feedback`, re-sanitized JSONL export rows, `<workspace>` metadata for stats/export/bundle CLI envelopes, `dest_placement` + `redaction.warnings` for out-of-tree bundle destinations, and documented `feedback bundle` in the release runbook | `feedback.py`, `release_runbook.py`, `test_feedback_*.py`, `test_doctor_cli.py` |
| **ECC ingest draft tranche (ECC-N04-D01–D03)** | Added/extended ingest draft snapshots: **`ecc_asset_registry_v1`**, **`ecc_ingest_sanitizer_policy_v1`**, and **`ecc_ingest_provenance_trust_v1`** under `docs/schema/`, plus bilingual **`ECC_04B`** (sanitizer) and **`ECC_04C`** (provenance/signature/trust gates) policy docs; registry snapshot `boundaries` now marks provenance policy coverage | `docs/schema/ecc_*.snapshot.json`, `docs/ECC_04B_*`, `docs/ECC_04C_*`, `cai-agent/tests/test_ecc_ingest_schema_snapshots.py` |
| **Plugin compat matrix CI snapshot (ECC-03c)** | Added **`scripts/gen_plugin_compat_snapshot.py`** to generate/check **`docs/schema/plugin_compat_matrix_v1.snapshot.json`**; the snapshot embeds **`plugin_compat_matrix_v1`** and **`plugin_compat_matrix_check_v1`**, and smoke runs `--check` | `scripts/gen_plugin_compat_snapshot.py`, `plugin_compat_matrix_v1.snapshot.json`, `test_plugin_compat_matrix.py` |
| **SSH Runtime (HM-06c)** | **`runtime.ssh`** diagnostics now include `ssh_binary_present`, key/known_hosts existence, strict host key mode, and connect timeout; optional **`runtime_ssh_audit_v1`** JSONL audit logging is available without recording command text by default (`audit_include_command=true` opt-in) | `runtime/ssh.py`, `runtime/registry.py`, `config.py`, `test_runtime_ssh_mock.py` |
| **Docker Runtime (HM-06b)** | **`runtime.docker`** supports the existing `container` / `docker exec` mode plus a new `image` / `docker run --rm` mode; config now includes **`workdir`**, **`volume_mounts`**, **`cpus`**, and **`memory`**, surfaced through **`doctor_runtime_v1.describe`** as mode/image/workdir/volumes/limits | `runtime/docker.py`, `runtime/registry.py`, `config.py`, `test_runtime_docker_mock.py` |
| **Teams Gateway (HM-03d)** | **`gateway teams`** now provides session mapping (`bind/get/list/unbind`), allowlist, `health`, Teams app `manifest` scaffold, and a Bot Framework Activity **`serve-webhook`**; `gateway platforms` / `gateway maps` include Teams; machine-readable payloads include **`gateway_teams_map_v1`**, **`gateway_teams_health_v1`**, and **`gateway_teams_manifest_v1`** | `cai_agent/gateway_teams.py`, `gateway_platforms.py`, `gateway_maps.py`, `test_gateway_discord_slack_cli.py` |
| **Undeveloped-feature P0 batch (HM-02c / CC-03c / ECC-03b)** | Read-only API extensions (**`/v1/models/summary`**, **`/v1/plugins/surface`**, **`/v1/release/runbook`**); TUI **`#context-label`** route/migration hint + shared **`profile_switched: <id>`** one-liner; **`plugins --compat-check`** → **`plugin_compat_matrix_check_v1`** and matrix **`maintenance_checklist`** | `cai_agent/api_http_server.py`, `cai_agent/tui_session_strip.py`, `cai_agent/plugin_registry.py`, `docs/COMPLETED_TASKS_ARCHIVE.zh-CN.md` |
| **Explore assessment batch (HM-03c / ECC-03a / HM-06a / HM-07a)** | RFC conclusions under **`docs/rfc/`** (`HM_03C_*`, `ECC_03A_*`, `HM_06A_*`, `HM_07A_*`); roadmap §10 items marked **Done** (document-only deliverables). Completed-task history now lives in **`COMPLETED_TASKS_ARCHIVE.zh-CN.md`**. | `docs/COMPLETED_TASKS_ARCHIVE.zh-CN.md` |
| **Minimal HTTP API (HM-02b)** | **`cai-agent api serve`** on **`CAI_API_PORT`** (default **8788**); optional **`CAI_API_TOKEN`** (**Bearer**; **`/healthz`** exempt); **`GET /v1/status`**, **`GET /v1/doctor/summary`**, **`POST /v1/tasks/run-due`** (dry-run only) | `cai_agent/api_http_server.py`, `doctor.build_api_doctor_summary_v1`, `test_api_http_server.py`, RFC [`rfc/HM_02_MINIMAL_SERVER_CONTRACT.zh-CN.md`](rfc/HM_02_MINIMAL_SERVER_CONTRACT.zh-CN.md) |
| **Ops / observability** | **`cai-agent ops dashboard`** JSON/text/html; **`--html-refresh-seconds`** for HTML auto-refresh; **`cai-agent ops serve`** read-only HTTP (**`/v1/ops/dashboard`**, **`/v1/ops/dashboard.html`**); optional **`CAI_OPS_API_TOKEN`** | [`OPS_DYNAMIC_WEB_API.md`](OPS_DYNAMIC_WEB_API.md), `cai_agent/ops_dashboard.py`, `cai_agent/ops_http_server.py` |
| **Memory / user model** | **`cai-agent memory user-model export`** → **`user_model_bundle_v1`** (wraps **`memory_user_model_v1`** overview) | `cai_agent/user_model.py`, RFC [`rfc/HONCHO_USER_MODEL_EPIC.zh-CN.md`](rfc/HONCHO_USER_MODEL_EPIC.zh-CN.md) |
| **ECC / routing & budget** | **`models routing-test`** text/JSON with bilingual **`explain`**; **`cost budget`** embeds **`cost_budget_explain_v1`** (**ECC-02a**) | `cai_agent/model_routing.py`, `cai_agent/cost_aggregate.py`, [`MODEL_ROUTING_RULES.md`](MODEL_ROUTING_RULES.md) |
| **Tests / smoke** | **`test_ops_http_server.py`**, **`test_ops_dashboard_html.py`** (refresh), **`test_memory_user_model_export.py`**; **`scripts/smoke_new_features.py`** extended | `cai-agent/tests/`, `scripts/smoke_new_features.py` |

## Still open (not claimed “done” in product docs)

High-level only; details live in **`PRODUCT_PLAN.zh-CN.md`** §0.2 / §3.2 and **`PRODUCT_GAP_ANALYSIS.zh-CN.md`**.

| Theme | Status |
|-------|--------|
| **Claude Code experience line** | Install/update/feedback flow, MCP-first WebSearch/Notebook entrypoints, task/status UX are still being tightened |
| **Hermes productization line** | Profiles, API/server, more gateway platforms, dynamic dashboard, memory providers, runtime backends are still open |
| **ECC governance line** | Rules/skills/hooks assetization, model-route/cost governance, plugin/distribution story still need productization |
| **Shared release loop** | Feedback, semantic changelog, parity write-back, and release gating are now explicit roadmap work rather than ad-hoc follow-up |
| **OOS / conditional** | Native WebSearch/Notebook reimplementation, default cloud backends, and closed enterprise-only features remain out of scope or conditional |

## Latest regression run (QA)

- **Date**: 2026-04-25 (repo root `D:\gitrepo\Cai_Agent`, local timezone).  
- **`pytest cai-agent/tests`** (repo root: **`python -m pytest -q cai-agent/tests`**): **825 passed**, **3 subtests passed**; **`PYTHONPATH=cai-agent\src`**.
- **`python scripts/smoke_new_features.py`**: **NEW_FEATURE_CHECKS_OK**.  
- **`QA_SKIP_LOG=1 python scripts/run_regression.py`**: exit **0** (after HM-04c / HM-03e / HM-05d). Latest checked-in machine log remains **[`docs/qa/runs/regression-20260424-191511.md`](qa/runs/regression-20260424-191511.md)**; unset **`QA_SKIP_LOG=1`** to write a fresh log (see **QA_REGRESSION_LOGGING**).

## QA pointers

- Automated: **`pytest cai-agent/tests`** (see **PRODUCT_PLAN** §3 T1 for latest counts).  
- Smoke: **`python scripts/smoke_new_features.py`** from repo root.  
- Release checklist: [`docs/qa/T7_RELEASE_GATE_CHECKLIST.zh-CN.md`](qa/T7_RELEASE_GATE_CHECKLIST.zh-CN.md).
