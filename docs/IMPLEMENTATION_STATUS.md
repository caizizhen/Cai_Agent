# Implementation status (rolling summary)

> **English** (default for this file). Chinese: [`IMPLEMENTATION_STATUS.zh-CN.md`](IMPLEMENTATION_STATUS.zh-CN.md).  
> Authoritative execution checklist: [`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md). Detailed changes: root **`CHANGELOG.md`** / **`CHANGELOG.zh-CN.md`**.

Current product target: integrate **Claude Code + Hermes Agent + Everything Claude Code** in one runtime. Planning details live in [`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md) and [`PRODUCT_GAP_ANALYSIS.zh-CN.md`](PRODUCT_GAP_ANALYSIS.zh-CN.md).

## Recently shipped (developer-facing)

The following landed on **`main`** around the **0.7.0** window (see **CHANGELOG §0.7.0** for the full list):

| Area | What shipped | Where to look |
|------|----------------|---------------|
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

- **Date**: 2026-04-24 (repo root `D:\gitrepo\Cai_Agent`, local timezone).  
- **`pytest cai-agent/tests`**: **641 passed**, **3 subtests passed**; **`PYTHONPATH=cai-agent\src`**.  
- **`python scripts/smoke_new_features.py`**: **NEW_FEATURE_CHECKS_OK**.  
- **`QA_SKIP_LOG=1 python scripts/run_regression.py`**: exit **0** (compileall, unittest discover, smoke, CLI subset); **no** new `docs/qa/runs/regression-*.md` (per **QA_REGRESSION_LOGGING** `QA_SKIP_LOG` policy).

## QA pointers

- Automated: **`pytest cai-agent/tests`** (see **PRODUCT_PLAN** §3 T1 for latest counts).  
- Smoke: **`python scripts/smoke_new_features.py`** from repo root.  
- Release checklist: [`docs/qa/T7_RELEASE_GATE_CHECKLIST.zh-CN.md`](qa/T7_RELEASE_GATE_CHECKLIST.zh-CN.md).
