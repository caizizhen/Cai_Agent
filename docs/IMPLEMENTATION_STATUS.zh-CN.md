# 实现状态（滚动摘要）

> **中文**说明；英文对照见 [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md)。  
> **唯一执行清单**仍以 [`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md) 为准；逐条变更以根目录 **`CHANGELOG.md`** / **`CHANGELOG.zh-CN.md`** 为准。

## 近期已交付（面向开发/集成）

以下能力已在 **`main`** 落地（**0.7.0** 窗口及紧随补丁；完整列表见 **CHANGELOG §0.7.0**）：

| 领域 | 交付内容 | 代码/文档入口 |
|------|-----------|---------------|
| **运营 / 可观测** | **`cai-agent ops dashboard`**（json/text/html）；**`--html-refresh-seconds`**（HTML **`meta refresh`**）；**`cai-agent ops serve`** 只读 HTTP（**`/v1/ops/dashboard`**、**`/v1/ops/dashboard.html`**）；可选 **`CAI_OPS_API_TOKEN`** | [`OPS_DYNAMIC_WEB_API.zh-CN.md`](OPS_DYNAMIC_WEB_API.zh-CN.md)、**`cai_agent/ops_dashboard.py`**、**`cai_agent/ops_http_server.py`** |
| **记忆 / 用户模型** | **`cai-agent memory user-model export`** → **`user_model_bundle_v1`**（嵌 **`memory_user_model_v1`** **`overview`**） | **`cai_agent/user_model.py`**、RFC [`docs/rfc/HONCHO_USER_MODEL_EPIC.zh-CN.md`](rfc/HONCHO_USER_MODEL_EPIC.zh-CN.md) |
| **测试 / 冒烟** | **`test_ops_http_server.py`**、**`test_ops_dashboard_html.py`**（含刷新）、**`test_memory_user_model_export.py`**；**`scripts/smoke_new_features.py`** 已扩 **`memory user-model export`** | **`cai-agent/tests/`**、**`scripts/smoke_new_features.py`** |

## 仍未完成（产品文档口径）

以下为 **PRODUCT_PLAN / PRODUCT_GAP / RFC** 中仍标为后续或 OOS 的项（非本页详尽清单）：

| 主题 | 说明 |
|------|------|
| **运营 Web Phase C** | SSE、队列拖拽、RBAC、多 workspace 产品化路由等 |
| **Gateway 生产级** | Discord/Slack **MVP** 之外的频道监控、更深 Slash、多租户式能力等 |
| **Honcho 用户模型全量** | **`user_model_store_v1`** 持久化、在线学习、**`memory user-model query`**、图谱 **E4** 等（当前仅有 **`export`** 归档切片） |
| **P1 缺口** | 内置 WebSearch/Notebook 与 **MCP 定案**并行；**真实 recall 命中率**统计（与 **`insights --cross-domain`** 已标注的 index 探测区分） |
| **OOS** | Modal/Daytona 云沙箱（**PARITY_MATRIX** 与 **`CLOUD_RUNTIME_OOS`**）、语音/官方 Bridge 等 |
| **P2 产品与生态** | 官方安装器级分发、`/bug` 统一反馈等（**`PRODUCT_GAP`** §关键缺口-4） |

## 最近回归执行记录（QA）

- **日期**：2026-04-24（仓库根 `D:\gitrepo\Cai_Agent`，本地时区）。  
- **`pytest cai-agent/tests`**：**564 passed**，**3 subtests passed**；**`PYTHONPATH=cai-agent\src`**。  
- **`python scripts/smoke_new_features.py`**：**NEW_FEATURE_CHECKS_OK**。  
- **`QA_SKIP_LOG=1 python scripts/run_regression.py`**：退出码 **0**（含 compileall、unittest discover、`smoke_new_features` 及 CLI 子集）；**未**新建 `docs/qa/runs/regression-*.md`（与 **QA_REGRESSION_LOGGING** 中 `QA_SKIP_LOG` 约定一致）。

## QA 提示

- 自动化：**`pytest cai-agent/tests`**（用例数以 **PRODUCT_PLAN** §三 T1 为准）。  
- 冒烟：**仓库根**执行 **`python scripts/smoke_new_features.py`**。  
- 发版：**[`docs/qa/T7_RELEASE_GATE_CHECKLIST.zh-CN.md`](qa/T7_RELEASE_GATE_CHECKLIST.zh-CN.md)**。
