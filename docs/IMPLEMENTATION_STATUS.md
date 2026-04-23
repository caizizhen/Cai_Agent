# Implementation status (rolling summary)

> **English** (default for this file). Chinese: [`IMPLEMENTATION_STATUS.zh-CN.md`](IMPLEMENTATION_STATUS.zh-CN.md).  
> Authoritative execution checklist: [`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md). Detailed changes: root **`CHANGELOG.md`** / **`CHANGELOG.zh-CN.md`**.

## Recently shipped (developer-facing)

The following landed on **`main`** around the **0.7.0** window (see **CHANGELOG §0.7.0** for the full list):

| Area | What shipped | Where to look |
|------|----------------|---------------|
| **Ops / observability** | **`cai-agent ops dashboard`** JSON/text/html; **`--html-refresh-seconds`** for HTML auto-refresh; **`cai-agent ops serve`** read-only HTTP (**`/v1/ops/dashboard`**, **`/v1/ops/dashboard.html`**); optional **`CAI_OPS_API_TOKEN`** | [`OPS_DYNAMIC_WEB_API.md`](OPS_DYNAMIC_WEB_API.md), `cai_agent/ops_dashboard.py`, `cai_agent/ops_http_server.py` |
| **Memory / user model** | **`cai-agent memory user-model export`** → **`user_model_bundle_v1`** (wraps **`memory_user_model_v1`** overview) | `cai_agent/user_model.py`, RFC [`rfc/HONCHO_USER_MODEL_EPIC.zh-CN.md`](rfc/HONCHO_USER_MODEL_EPIC.zh-CN.md) |
| **Tests / smoke** | **`test_ops_http_server.py`**, **`test_ops_dashboard_html.py`** (refresh), **`test_memory_user_model_export.py`**; **`scripts/smoke_new_features.py`** extended | `cai-agent/tests/`, `scripts/smoke_new_features.py` |

## Still open (not claimed “done” in product docs)

High-level only; details live in **`PRODUCT_PLAN.zh-CN.md`** §0.2 / §3.2 and **`PRODUCT_GAP_ANALYSIS.zh-CN.md`**.

| Theme | Status |
|-------|--------|
| **Ops web Phase C** | SSE / drag-drop queues / RBAC / multi-workspace product routing — **future** |
| **Gateway beyond MVP** | Discord/Slack production-grade features (monitoring, deeper slash, etc.) — **follow-up sprints** |
| **Honcho user-model full epic** | Persistent **`user_model_store_v1`**, online learning, **`memory user-model query`**, graph layer — **RFC E1–E4** beyond current **`export`** slice |
| **P1 gaps** | Built-in WebSearch/Notebook vs **MCP-first** decision; **true recall hit-rate** stats (vs index-probe metrics already labeled in **`insights --cross-domain`**) |
| **OOS** | Modal/Daytona cloud sandboxes (**`PARITY_MATRIX`** + **`CLOUD_RUNTIME_OOS`**); voice / official bridge — **out of scope** |
| **P2 product / ecosystem** | Installer-style distribution, unified feedback channels ( **`PRODUCT_GAP`** §4 ) |

## Latest regression run (QA)

- **Date**: 2026-04-24 (repo root `D:\gitrepo\Cai_Agent`, local timezone).  
- **`pytest cai-agent/tests`**: **564 passed**, **3 subtests passed**; **`PYTHONPATH=cai-agent\src`**.  
- **`python scripts/smoke_new_features.py`**: **NEW_FEATURE_CHECKS_OK**.  
- **`QA_SKIP_LOG=1 python scripts/run_regression.py`**: exit **0** (compileall, unittest discover, smoke, CLI subset); **no** new `docs/qa/runs/regression-*.md` (per **QA_REGRESSION_LOGGING** `QA_SKIP_LOG` policy).

## QA pointers

- Automated: **`pytest cai-agent/tests`** (see **PRODUCT_PLAN** §3 T1 for latest counts).  
- Smoke: **`python scripts/smoke_new_features.py`** from repo root.  
- Release checklist: [`docs/qa/T7_RELEASE_GATE_CHECKLIST.zh-CN.md`](qa/T7_RELEASE_GATE_CHECKLIST.zh-CN.md).
