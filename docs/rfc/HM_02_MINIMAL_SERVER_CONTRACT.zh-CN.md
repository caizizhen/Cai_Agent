# RFC：Hermes 最小只读 HTTP API（HM-02a 契约草案）

> 状态：**已实现 v0**（**`cai-agent api serve`**，仓库 **`cai_agent.api_http_server`**）。与 **`ops serve`** 不同：本契约面向「外部驱动 Agent / 自动化」的通用 JSON API，而非仅运营看板。

## 1. 目标与边界

- **目标**：在单工作区内提供 **只读**（或「显式触发单次任务」型）HTTP JSON，便于 CI、外部 UI 或另一个进程查询状态。
- **不在范围**：OpenAI-compatible chat completions、长连接流式补全、多租户认证中心、写会话/写记忆（默认拒绝）。

## 2. 进程与配置

- **入口**：建议独立子命令 **`cai-agent api serve`**（与 **`ops serve`** 端口不冲突；默认端口 **`CAI_API_PORT`**，如 **`8788`**）。
- **鉴权**：环境变量 **`CAI_API_TOKEN`** 非空时，所有路径（除 **`GET /healthz`**）要求 **`Authorization: Bearer <token>`**。
- **工作区**：启动时 **`cwd`** 为唯一工作区根；禁止路径参数越界到上级目录。

## 3. 建议路由（v0）

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/healthz` | **`{ "ok": true }`**，无鉴权 |
| `GET` | `/v1/status` | 与 CLI **`gateway status --json`** 同源的 **`gateway_summary_v1`** 子集 + **`schema_version`: `api_status_v1`** |
| `GET` | `/v1/doctor/summary` | 复用 **`build_doctor_payload`** 中仅白名单字段（版本、mock、profile_contract 摘要、memory_policy 摘要），避免泄露密钥 |
| `POST` | `/v1/tasks/run-due` | **可选波次 2**：若需要「任务触发」，则 body **`{ "dry_run": true }`** 时仅返回将运行项列表；默认 **`dry_run`** 为 true |

## 4. 版本与错误

- 响应头 **`X-Cai-Agent-Api-Version: 0`**。
- 错误体 **`{ "ok": false, "error": "<code>", "message": "…" }`**；鉴权失败 **401**，未知路径 **404**。

## 5. 验收

- 安全：**`/v1/doctor/summary`** 使用 **`api_doctor_summary_v1`** 白名单字段；不得返回未打码 **`api_key`** 或 **`base_url`** / **`model`** 明文。
- **`POST /v1/tasks/run-due`**：HTTP 面仅 **dry_run**；真实执行请走 CLI **`schedule run-due --execute`**。
- 自动化：**`cai-agent/tests/test_api_http_server.py`**。
