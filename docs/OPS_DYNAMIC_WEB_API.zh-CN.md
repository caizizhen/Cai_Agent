# 动态运营 Web：HTTP API 契约草案与 MVP 范围

> **状态**：契约与分阶段范围已定稿；**Phase B 只读 HTTP** 由 **`cai-agent ops serve`** 提供（`ThreadingHTTPServer`，路径 **`GET /v1/ops/dashboard`** / **`GET /v1/ops/dashboard.html`**；可选 **`CAI_OPS_API_TOKEN`**）。运营聚合的 CLI 入口仍为 **`cai-agent ops dashboard`**（与 **`build_ops_dashboard_payload`** / **`ops_dashboard_v1`** 对齐）。

## 1. 现状（已实现）

| 能力 | 入口 | 说明 |
|------|------|------|
| JSON 载荷 | `ops dashboard --format json`（或 `--json`） | 与 **`cai_agent.ops_dashboard.build_ops_dashboard_payload`** 返回值一致，**`schema_version`=`ops_dashboard_v1`**，并内嵌共享的 `gateway_summary` |
| 文本摘要 | `ops dashboard`（默认 `--format text`） | 单行 KPI 摘要 |
| 单文件 HTML | `ops dashboard --format html [-o FILE]` | **`build_ops_dashboard_html`**，离线可打开；无服务端推送 |
| 只读 HTTP（Phase B） | `ops serve [--host H] [--port P] [--allow-workspace DIR…]` | **`cai_agent.ops_http_server`**：`GET /v1/ops/dashboard`（JSON）与 **`GET /v1/ops/dashboard.html`**；**`workspace`** query 必填且须在 allowlist 内 |

CLI 参数与实现对齐（见 **`cai_agent/__main__.py`** `ops dashboard`）：

- **`--pattern`** → `observe_pattern`（默认 **`.cai-session*.json`**）
- **`--limit`** → `observe_limit`（默认 **100**）
- **`--schedule-days`** → `schedule_days`（默认 **30**）
- **`--audit-file`** → `audit_path`（调度审计 JSONL，可选）
- 载荷内 **`cost_aggregate`** 使用 **`aggregate_sessions`**；**`cost_session_limit`**（默认 **200**）在 **`ops serve`** 的 HTTP query 中已暴露；**`ops dashboard`** CLI 仍使用默认值（未单独暴露 flag）。
- `board`、`ops dashboard`、`gateway status` 现在共享 `gateway_summary_v1`，用于统一展示 `status / bindings_count / webhook_running / allowlist_enabled` 这类运营态字段。

## 2. 设计原则（HTTP 化时须遵守）

1. **只读**：不得通过该 API 修改会话文件、调度任务、Gateway 映射或触发 `run`/`workflow`。
2. **工作区根边界**：每个请求必须绑定**单一已解析的**工作区根目录（与 CLI **`cwd`** 语义一致）；拒绝 `..` 逃逸与多根混淆。
3. **与 CLI 同源**：HTTP 200 的 JSON 体在字段上应与同参 **`build_ops_dashboard_payload`** 一致，便于 CI 与脚本共用 golden。

## 3. REST 契约草案（**`ops serve` 已实现**，供侧车或网关集成）

以下路径与字段为**约定**；实现时可挂载任意基路径（例如 **`/api`**）。

### 3.1 `GET /v1/ops/dashboard`

**用途**：返回 **`ops_dashboard_v1`** JSON。

**Query（建议与 CLI 对齐）**

| 参数 | 类型 | 默认 | 对应 payload 构造参数 |
|------|------|------|----------------------|
| `workspace` | string | （必填） | 解析为目录 **`cwd`**；须为绝对路径或由服务端配置允许列表 |
| `observe_pattern` | string | `.cai-session*.json` | `observe_pattern` |
| `observe_limit` | int | `100` | `observe_limit` |
| `schedule_days` | int | `30` | `schedule_days` |
| `audit_file` | string? | `null` | `audit_path` |
| `cost_session_limit` | int | `200` | `cost_session_limit` |

**响应**

- **`200`**：`Content-Type: application/json; charset=utf-8`，Body 与 **`build_ops_dashboard_payload(...)`** 一致。
- **`400`**：非法整数、非法 pattern、路径非目录等。
- **`403`**：`workspace` 不在服务端允许列表（若实现 allowlist）。
- **`401`**：见 §3.3。

### 3.2 `GET /v1/ops/dashboard.html`

**用途**：返回与 CLI **`--format html`** 相同的 **单文件 HTML**（便于浏览器直接刷新）。

**Query**：与 §3.1 相同，并可选追加 **`html_refresh_seconds`**（`0`–`86400`；`>0` 时 HTML 内嵌 **`meta refresh`**，与 CLI **`--html-refresh-seconds`** 同源）。服务端先组 JSON 再 **`build_ops_dashboard_html(...)`**。

**响应**

- **`200`**：`Content-Type: text/html; charset=utf-8`；建议 **`Cache-Control: no-store`**（数据随会话变）。

### 3.3 认证（草案）

- 服务端环境变量 **`CAI_OPS_API_TOKEN`**（或等价配置）：非空时，请求须带 **`Authorization: Bearer <token>`**，否则 **`401`**。
- 内网信任场景可关闭校验（**不推荐生产默认开启「无鉴权」**）。

## 4. 明确不做（首版 HTTP / OOS）

- **写路径**：任何 POST/PUT/PATCH 修改工作区、调度、记忆、Gateway。
- **长连接推送**：WebSocket / SSE 会话事件流（与 **`run --json` 流式**无关）。
- **多租户**：单实例多 unrelated 工作区隔离与配额（留待后续产品化）。

## 5. MVP 分阶段（与「动态」的关系）

| 阶段 | 内容 | 依赖 |
|------|------|------|
| **Phase A** | 在现有 HTML 导出上增加**可选**自动刷新（例如 **`meta refresh`** 或轻量脚本定时 **`location.reload()`**） | 仅静态文件或简单托管；**不改变** **`ops_dashboard_v1`** schema |
| **Phase B** | **侧车**只读 HTTP 服务：CLI **`cai-agent ops serve`**（stdlib）实现 §3，读磁盘与 CLI 相同数据源 | 部署与 **`cai-agent` 版本**绑定；鉴权 §3.3（**`CAI_OPS_API_TOKEN`**） |
| **Phase C** | 产品化：SSE/轮询增量、RBAC、多 workspace 路由、与 CI 看板联动 | 单独立项 |

**结论**：**§26（PRODUCT_PLAN）运营面板 MVP** 已在 CLI + 静态 HTML 完成；**Phase A**（**`meta refresh`** / **`--html-refresh-seconds`**）与 **Phase B**（**`ops serve`** §3 HTTP）已在仓库内交付；**Phase C**（SSE、RBAC 等）仍为后续立项。

## 6. 相关索引

- Schema 索引：**[`docs/schema/README.zh-CN.md`](schema/README.zh-CN.md)** § **`ops dashboard`**
- 英文契约（与本文对齐）：**[`docs/OPS_DYNAMIC_WEB_API.md`](OPS_DYNAMIC_WEB_API.md)**
- 实现：**`cai_agent/ops_dashboard.py`**（**`build_ops_dashboard_payload`** / **`build_ops_dashboard_html`**）；HTTP 侧车 **`cai_agent/ops_http_server.py`**（**`ops serve`**）
- 产品表：**[`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md)** §二项 **26** 与 **§三之二 · 3.2「26 后续」**；滚动摘要 **[`IMPLEMENTATION_STATUS.zh-CN.md`](IMPLEMENTATION_STATUS.zh-CN.md)**

## HM-04b 补充说明（2026-04-25）

- `cai-agent ops serve` 已正式暴露 `GET /v1/ops/dashboard/events`，响应为只读 `text/event-stream`。
- `dashboard.html` 现在支持 `live_mode=sse|poll` 与 `live_interval_seconds`；其中 `sse` 会订阅 `/v1/ops/dashboard/events`，`poll` 会用定时刷新保持只读消费体验。
- `/v1/ops/dashboard/events` 额外支持 `max_events`，便于测试、轻量脚本与单次拉取场景。
- 本轮交付完成后，`HM-04b` 已从 backlog `Ready` 收口为 `Done`；后续动态运营面板只剩 RBAC、多 workspace 路由等更重的产品化议题。
