# Dynamic ops web: HTTP API contract and MVP scope

> **Status**: Contract and phased scope are fixed. **Phase B read-only HTTP** is implemented as **`cai-agent ops serve`** (stdlib **`ThreadingHTTPServer`**, routes **`GET /v1/ops/dashboard`** and **`GET /v1/ops/dashboard.html`**; optional **`CAI_OPS_API_TOKEN`** bearer auth). The primary CLI entry remains **`cai-agent ops dashboard`**, aligned with **`build_ops_dashboard_payload`** / **`ops_dashboard_v1`**.

Chinese mirror (same normative content, Chinese prose): [`OPS_DYNAMIC_WEB_API.zh-CN.md`](OPS_DYNAMIC_WEB_API.zh-CN.md).

## 1. What exists today

| Capability | Entry | Notes |
|------------|-------|-------|
| JSON payload | `ops dashboard --format json` (or `--json`) | Same object as **`cai_agent.ops_dashboard.build_ops_dashboard_payload`**, **`schema_version`=`ops_dashboard_v1`** |
| Text summary | `ops dashboard` (default `--format text`) | One-line KPI summary |
| Single-file HTML | `ops dashboard --format html [-o FILE]` | **`build_ops_dashboard_html`**; optional **`--html-refresh-seconds`** embeds **`meta http-equiv=refresh`** (Phase A) |
| Read-only HTTP (Phase B) | `ops serve [--host H] [--port P] [--allow-workspace DIR…]` | **`cai_agent.ops_http_server`**: **`GET /v1/ops/dashboard`** (JSON) and **`GET /v1/ops/dashboard.html`**; **`workspace`** query parameter is **required** and must be on the server allowlist |

CLI flags for `ops dashboard` (see **`cai_agent/__main__.py`**): **`--pattern`**, **`--limit`**, **`--schedule-days`**, **`--audit-file`**, **`--html-refresh-seconds`**.

HTTP **`GET /v1/ops/dashboard.html`** accepts the same query keys as JSON plus optional **`html_refresh_seconds`** (0–86400; when >0, same behaviour as **`--html-refresh-seconds`**). **`cost_session_limit`** is exposed as a query parameter on both HTTP routes (default **200**).

## 2. Design rules (must hold for HTTP)

1. **Read-only**: no mutating workspace, schedule, memory, or gateway via this API; no triggering **`run`** / **`workflow`**.
2. **Single resolved workspace root** per request (same semantics as CLI **`cwd`**); reject path escape (`..`) and ambiguous roots.
3. **Same payload as CLI**: HTTP **200** JSON body must match **`build_ops_dashboard_payload`** for the same parameters (golden-friendly).

## 3. REST contract (implemented by **`ops serve`**)

Base path is fixed as below (integrators may reverse-proxy under **`/api`**, etc.).

### 3.1 `GET /v1/ops/dashboard`

Returns **`ops_dashboard_v1`** JSON.

**Query** (aligned with CLI / Python API)

| Parameter | Type | Default | Maps to |
|-----------|------|---------|---------|
| `workspace` | string | **required** | Resolved directory **`cwd`**; must match allowlist |
| `observe_pattern` | string | `.cai-session*.json` | `observe_pattern` |
| `observe_limit` | int | `100` | `observe_limit` |
| `schedule_days` | int | `30` | `schedule_days` |
| `audit_file` | string? | `null` | `audit_path` (must stay under workspace when resolved) |
| `cost_session_limit` | int | `200` | `cost_session_limit` |

**Responses**: **200** JSON; **400** bad integers / bad pattern / not a directory; **403** workspace not allowed; **401** when token is configured but missing/wrong (**§3.3**).

### 3.2 `GET /v1/ops/dashboard.html`

Same queries as §3.1, plus optional **`html_refresh_seconds`**. Response **200** **`text/html; charset=utf-8`**, **`Cache-Control: no-store`**.

### 3.3 Authentication

- If **`CAI_OPS_API_TOKEN`** is set (non-empty), requests must send **`Authorization: Bearer <token>`** or the server returns **401**.
- Disabling auth is possible for trusted LANs; not recommended as the default for production.

## 4. Explicitly out of scope (first HTTP slice / OOS)

- **Writes**: no POST/PUT/PATCH that change workspace, schedule, memory, or gateway.
- **Push streams**: no WebSocket / SSE for live session streams (separate from **`run --json`** streaming).
- **Multi-tenant isolation**: no quotas / hard isolation across unrelated workspaces in one process (future product work).

## 5. MVP phases

| Phase | Contents | Dependency |
|-------|----------|--------------|
| **Phase A** | Optional auto-refresh on HTML (**`meta refresh`**) | Static file or browser; **`ops_dashboard_v1`** schema unchanged |
| **Phase B** | Sidecar **`cai-agent ops serve`** (stdlib) serving §3 | Deployed next to **`cai-agent`**; auth §3.3 |
| **Phase C** | Product hardening: SSE / polling deltas, RBAC, multi-workspace routing, CI dashboard tie-ins | Separate initiative |

**Conclusion**: **PRODUCT_PLAN** §26 MVP (CLI + static HTML) is done; **Phase A** (refresh) and **Phase B** (HTTP) are in-repo; **Phase C** remains future work.

## 6. Related links

- Schema index: [`docs/schema/README.zh-CN.md`](schema/README.zh-CN.md) § **`ops dashboard`** (English repo docs index is Chinese-first for JSON contracts).
- Code: **`cai_agent/ops_dashboard.py`**, **`cai_agent/ops_http_server.py`**
- Product table: [`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md) §2 item **26** and §3.2 “26 follow-up”
