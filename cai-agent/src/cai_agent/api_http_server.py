"""最小只读 HTTP API（HM-02b / HM-02c）：``cai-agent api serve``。

契约见仓库 ``docs/rfc/HM_02_MINIMAL_SERVER_CONTRACT.zh-CN.md``。与 ``ops serve`` 端口分离；
鉴权环境变量 ``CAI_API_TOKEN``（非空则除 ``/healthz`` 外要求 ``Authorization: Bearer``）。

``HM-02c`` 在 ``HM-02b`` 基础上增加三条只读扩展：
``GET /v1/models/summary``（``api_models_summary_v1``，仅暴露 ``profile_contract_v1`` 白名单字段），
``GET /v1/models/capabilities``（``api_models_capabilities_v1``，仅暴露非敏感模型能力元数据），
``GET /v1/plugins/surface``（``api_plugins_surface_v1``，复用 ``list_plugin_surface``，可选 ``?compat=1`` 附加
``plugin_compat_matrix_v1``），以及 ``GET /v1/release/runbook``（``api_release_runbook_v1``，复用 release
runbook 摘要，不含仓库绝对路径）。**HM-N03-D01**：``GET /v1/health``（``api_health_v1``）、``GET /v1/ready``（``api_ready_v1``）；
``GET /healthz`` / ``GET /health`` 返回 ``api_liveness_v1``（仍无 Bearer）。均不扩大写操作面、不改默认鉴权策略。
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, TextIO, cast
from urllib.parse import parse_qs, urlparse

from cai_agent import __version__
from cai_agent.config import Settings
from cai_agent.doctor import build_api_doctor_summary_v1
from cai_agent.gateway_lifecycle import build_gateway_summary_payload, build_status_payload
from cai_agent.gateway_lifecycle import build_gateway_proxy_route_preview
from cai_agent.gateway_production import build_gateway_federation_summary_payload
from cai_agent.model_gateway import build_model_capabilities_payload
from cai_agent.llm_factory import chat_completion_response
from cai_agent.metrics import maybe_append_metrics_from_env, metrics_event_v1
from cai_agent.plugin_registry import build_plugin_compat_matrix, list_plugin_surface
from cai_agent.profiles import (
    Profile,
    build_profile_contract_payload,
    profile_to_public_dict,
    project_base_url,
)
from cai_agent.release_runbook import build_release_runbook_payload, resolve_release_repo_root
from cai_agent.schedule import compute_due_tasks
from cai_agent.server_auth import resolve_bearer_token


def _json_schema_ref(schema_version: str) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "schema_version": {"const": schema_version},
        },
        "additionalProperties": True,
    }


def _error_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "ok": {"type": "boolean"},
            "error": {"type": "string"},
            "message": {"type": "string"},
        },
        "additionalProperties": True,
    }


def _json_response(description: str, schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "description": description,
        "content": {
            "application/json": {
                "schema": schema,
            },
        },
    }


def _op(
    *,
    method: str,
    summary: str,
    schema_version: str | None = None,
    security: bool = True,
    request_schema: dict[str, Any] | None = None,
    parameters: list[dict[str, Any]] | None = None,
    content_type: str = "application/json",
) -> dict[str, Any]:
    responses: dict[str, Any] = {}
    if content_type == "text/event-stream":
        responses["200"] = {
            "description": "Server-sent event stream",
            "content": {
                "text/event-stream": {
                    "schema": {"type": "string"},
                },
            },
        }
    elif content_type == "text/html":
        responses["200"] = {
            "description": "HTML dashboard",
            "content": {
                "text/html": {
                    "schema": {"type": "string"},
                },
            },
        }
    else:
        responses["200"] = _json_response(
            "OK",
            _json_schema_ref(schema_version) if schema_version else {"type": "object"},
        )
    responses["400"] = _json_response("Bad request", _error_schema())
    responses["401"] = _json_response("Bearer token required", _error_schema())
    responses["403"] = _json_response("Forbidden", _error_schema())
    responses["404"] = _json_response("Not found", _error_schema())
    spec: dict[str, Any] = {
        "summary": summary,
        "operationId": method,
        "responses": responses,
    }
    if parameters:
        spec["parameters"] = parameters
    if security:
        spec["security"] = [{"bearerAuth": []}]
    else:
        spec["security"] = []
    if request_schema is not None:
        spec["requestBody"] = {
            "required": False,
            "content": {
                "application/json": {
                    "schema": request_schema,
                },
            },
        }
    if schema_version:
        spec["x-cai-schema-version"] = schema_version
    return spec


def _workspace_query_param() -> dict[str, Any]:
    return {
        "name": "workspace",
        "in": "query",
        "required": True,
        "schema": {"type": "string"},
        "description": "Workspace path allowed by ops serve.",
    }


def build_api_openapi_v1() -> dict[str, Any]:
    """Build the non-sensitive OpenAPI contract for API and ops HTTP surfaces."""

    route_preview_body = {
        "type": "object",
        "properties": {
            "platform": {"type": "string"},
            "channel_id": {"type": ["string", "null"]},
            "target_workspace": {"type": ["string", "null"]},
            "target_profile_id": {"type": ["string", "null"]},
            "dry_run": {"type": "boolean", "default": True},
        },
        "additionalProperties": False,
    }
    run_due_body = {
        "type": "object",
        "properties": {"dry_run": {"type": "boolean", "default": True}},
        "additionalProperties": True,
    }
    chat_body = {
        "type": "object",
        "properties": {
            "model": {"type": "string"},
            "messages": {"type": "array", "items": {"type": "object"}},
            "temperature": {"type": "number"},
            "stream": {"type": "boolean"},
        },
        "required": ["messages"],
        "additionalProperties": True,
    }
    ops_interaction_body = {
        "type": "object",
        "properties": {
            "workspace": {"type": "string"},
            "action": {"type": "string"},
            "mode": {"type": "string", "enum": ["preview", "apply", "audit"]},
        },
        "required": ["workspace", "action"],
        "additionalProperties": True,
    }
    ops_params = [
        _workspace_query_param(),
        {"name": "observe_pattern", "in": "query", "schema": {"type": "string"}},
        {"name": "observe_limit", "in": "query", "schema": {"type": "integer", "minimum": 1}},
        {"name": "schedule_days", "in": "query", "schema": {"type": "integer", "minimum": 1}},
        {"name": "cost_session_limit", "in": "query", "schema": {"type": "integer", "minimum": 1}},
        {"name": "audit_file", "in": "query", "schema": {"type": "string"}},
    ]
    paths: dict[str, Any] = {
        "/healthz": {"get": _op(method="getHealthz", summary="Liveness probe", schema_version="api_liveness_v1", security=False)},
        "/health": {"get": _op(method="getHealth", summary="Liveness probe alias", schema_version="api_liveness_v1", security=False)},
        "/openapi.json": {"get": _op(method="getOpenApi", summary="OpenAPI contract", security=True)},
        "/v1/health": {"get": _op(method="getV1Health", summary="Authenticated health summary", schema_version="api_health_v1")},
        "/v1/ready": {"get": _op(method="getV1Ready", summary="Configuration readiness summary", schema_version="api_ready_v1")},
        "/v1/status": {"get": _op(method="getStatus", summary="Gateway status summary", schema_version="api_status_v1")},
        "/v1/doctor/summary": {"get": _op(method="getDoctorSummary", summary="Sanitized doctor summary", schema_version="api_doctor_summary_v1")},
        "/v1/models": {"get": _op(method="listModels", summary="OpenAI-compatible model list", schema_version="api_openai_models_v1")},
        "/v1/models/summary": {"get": _op(method="getModelsSummary", summary="Profile contract summary", schema_version="api_models_summary_v1")},
        "/v1/models/capabilities": {"get": _op(method="getModelsCapabilities", summary="Model capability metadata", schema_version="api_models_capabilities_v1")},
        "/v1/profiles": {"get": _op(method="getProfiles", summary="Public profile list", schema_version="api_profiles_v1")},
        "/v1/plugins/surface": {
            "get": _op(
                method="getPluginsSurface",
                summary="Plugin surface summary",
                schema_version="api_plugins_surface_v1",
                parameters=[{"name": "compat", "in": "query", "schema": {"type": "boolean"}}],
            ),
        },
        "/v1/release/runbook": {"get": _op(method="getReleaseRunbook", summary="Release runbook summary", schema_version="api_release_runbook_v1")},
        "/v1/gateway/federation-summary": {"get": _op(method="getGatewayFederationSummary", summary="Gateway federation summary", schema_version="gateway_federation_summary_v1")},
        "/v1/gateway/route-preview": {"post": _op(method="postGatewayRoutePreview", summary="Dry-run gateway route preview", schema_version="gateway_proxy_route_v1", request_schema=route_preview_body)},
        "/v1/tasks/run-due": {"post": _op(method="postTasksRunDue", summary="Dry-run due schedule tasks", schema_version="api_tasks_run_due_v1", request_schema=run_due_body)},
        "/v1/chat/completions": {"post": _op(method="postChatCompletions", summary="OpenAI-compatible chat completion", schema_version="api_openai_chat_completion_v1", request_schema=chat_body)},
        "/v1/ops/dashboard": {"get": _op(method="getOpsDashboard", summary="Ops dashboard JSON", schema_version="ops_dashboard_v1", parameters=ops_params)},
        "/v1/ops/dashboard.html": {"get": _op(method="getOpsDashboardHtml", summary="Ops dashboard HTML", parameters=ops_params, content_type="text/html")},
        "/v1/ops/dashboard/events": {"get": _op(method="getOpsDashboardEvents", summary="Ops dashboard SSE events", parameters=ops_params, content_type="text/event-stream")},
        "/v1/ops/dashboard/interactions": {
            "get": _op(
                method="getOpsDashboardInteractions",
                summary="Preview or audit dashboard action",
                schema_version="ops_dashboard_interactions_v1",
                parameters=[
                    *ops_params,
                    {"name": "action", "in": "query", "required": True, "schema": {"type": "string"}},
                    {"name": "mode", "in": "query", "schema": {"type": "string", "enum": ["preview", "audit"]}},
                ],
            ),
            "post": _op(
                method="postOpsDashboardInteractions",
                summary="Preview, apply, or audit dashboard action",
                schema_version="ops_dashboard_interactions_v1",
                request_schema=ops_interaction_body,
            ),
        },
    }
    schema_versions = sorted(
        {
            str(op.get("x-cai-schema-version"))
            for item in paths.values()
            for op in item.values()
            if isinstance(op, dict) and op.get("x-cai-schema-version")
        },
    )
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "cai-agent API and Ops Gateway",
            "version": __version__,
            "description": "Non-sensitive discovery contract for cai-agent API and ops HTTP surfaces.",
        },
        "jsonSchemaDialect": "https://json-schema.org/draft/2020-12/schema",
        "paths": paths,
        "components": {
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "CAI_API_TOKEN or CAI_OPS_API_TOKEN",
                },
            },
        },
        "x-cai-contract": {
            "schema_version": "api_openapi_v1",
            "generated_at": datetime.now(UTC).isoformat(),
            "surfaces": ["api", "ops"],
            "auth": {
                "api": "CAI_API_TOKEN or CAI_OPS_API_TOKEN; /healthz and /health are liveness-only and unauthenticated",
                "ops": "CAI_OPS_API_TOKEN or CAI_API_TOKEN",
            },
            "schema_versions": schema_versions,
            "sensitive_fields_excluded": ["api_key", "base_url", "workspace_runtime_values"],
        },
    }


def build_api_models_summary_v1(settings: Settings) -> dict[str, Any]:
    """HTTP ``GET /v1/models/summary`` 白名单视图：仅包含 ``profile_contract_v1`` 与 ID 列表。"""
    contract = build_profile_contract_payload(
        settings.profiles,
        profiles_explicit=bool(getattr(settings, "profiles_explicit", False)),
        active_profile_id=settings.active_profile_id,
        subagent_profile_id=getattr(settings, "subagent_profile_id", None),
        planner_profile_id=getattr(settings, "planner_profile_id", None),
        env_active_override=os.getenv("CAI_ACTIVE_MODEL"),
        workspace_root=settings.workspace,
    )
    return {
        "schema_version": "api_models_summary_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "active_profile_id": settings.active_profile_id,
        "subagent_profile_id": getattr(settings, "subagent_profile_id", None),
        "planner_profile_id": getattr(settings, "planner_profile_id", None),
        "profiles_count": len(settings.profiles),
        "profile_ids": [p.id for p in settings.profiles],
        "profile_contract": contract,
    }


def build_api_models_capabilities_v1(settings: Settings) -> dict[str, Any]:
    """HTTP ``GET /v1/models/capabilities`` non-secret model metadata view."""

    payload = build_model_capabilities_payload(
        settings.profiles,
        active_profile_id=settings.active_profile_id,
        context_window_fallback=int(getattr(settings, "context_window", 0) or 0) or None,
    )
    return {
        "schema_version": "api_models_capabilities_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "model_capabilities": payload,
    }


def build_api_profiles_v1(settings: Settings) -> dict[str, Any]:
    contract = build_profile_contract_payload(
        settings.profiles,
        profiles_explicit=bool(getattr(settings, "profiles_explicit", False)),
        active_profile_id=settings.active_profile_id,
        subagent_profile_id=getattr(settings, "subagent_profile_id", None),
        planner_profile_id=getattr(settings, "planner_profile_id", None),
        env_active_override=os.getenv("CAI_ACTIVE_MODEL"),
        workspace_root=settings.workspace,
    )
    rows = [profile_to_public_dict(p, include_resolved_key=True) for p in settings.profiles]
    return {
        "schema_version": "api_profiles_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(settings.workspace),
        "active_profile_id": settings.active_profile_id,
        "subagent_profile_id": getattr(settings, "subagent_profile_id", None),
        "planner_profile_id": getattr(settings, "planner_profile_id", None),
        "profiles_count": len(rows),
        "profiles": rows,
        "profile_contract": contract,
    }


def build_api_openai_models_v1(settings: Settings) -> dict[str, Any]:
    """OpenAI-compatible ``GET /v1/models`` list backed by configured profiles."""

    data: list[dict[str, Any]] = []
    seen: set[str] = set()
    for profile in settings.profiles:
        model_id = str(profile.model or profile.id).strip()
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        data.append(
            {
                "id": model_id,
                "object": "model",
                "created": 0,
                "owned_by": profile.provider,
                "cai_profile_id": profile.id,
            },
        )
    return {
        "schema_version": "api_openai_models_v1",
        "object": "list",
        "data": data,
    }


def _profile_for_openai_model(settings: Settings, model: str) -> Profile | None:
    wanted = str(model or "").strip()
    if not wanted:
        return None
    for profile in settings.profiles:
        if wanted in {str(profile.id), str(profile.model)}:
            return profile
    return None


def _settings_for_openai_chat_request(
    settings: Settings,
    body: dict[str, Any],
) -> Settings:
    model = str(body.get("model") or "").strip()
    profile = _profile_for_openai_model(settings, model)
    if profile is not None:
        updates: dict[str, Any] = {
            "provider": profile.provider,
            "base_url": project_base_url(profile),
            "model": profile.model,
            "api_key": profile.resolve_api_key() or settings.api_key,
            "temperature": max(0.0, min(2.0, float(profile.temperature))),
            "llm_timeout_sec": max(5.0, min(3600.0, float(profile.timeout_sec))),
            "active_profile_id": profile.id,
            "active_api_key_env": profile.api_key_env,
        }
        if profile.provider == "anthropic":
            updates["anthropic_version"] = profile.anthropic_version or "2023-06-01"
            updates["anthropic_max_tokens"] = int(profile.max_tokens or settings.anthropic_max_tokens)
        if profile.context_window:
            updates["context_window"] = int(profile.context_window)
            updates["context_window_source"] = "profile"
        settings = replace(settings, **updates)
    elif model:
        settings = replace(settings, model=model)

    if "temperature" in body:
        try:
            settings = replace(settings, temperature=max(0.0, min(2.0, float(body.get("temperature")))))
        except (TypeError, ValueError):
            pass
    return settings


def _normalize_openai_messages(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise ValueError("messages must be an array")
    messages: list[dict[str, Any]] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"messages[{idx}] must be an object")
        role = str(item.get("role") or "user").strip() or "user"
        content_raw = item.get("content", "")
        if isinstance(content_raw, str):
            content = content_raw
        elif isinstance(content_raw, list):
            parts: list[str] = []
            for part in content_raw:
                if isinstance(part, dict) and part.get("type") == "text":
                    parts.append(str(part.get("text") or ""))
                elif isinstance(part, str):
                    parts.append(part)
            content = "\n".join(p for p in parts if p)
        else:
            content = str(content_raw or "")
        messages.append({"role": role, "content": content})
    return messages


def build_api_openai_chat_completion_v1(
    settings: Settings,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Non-streaming OpenAI-compatible chat completion backed by ``ModelResponse``."""

    if bool(body.get("stream")):
        raise ValueError("streaming is not supported by this endpoint yet")
    messages = _normalize_openai_messages(body.get("messages"))
    projected = _settings_for_openai_chat_request(settings, body)
    resp = chat_completion_response(projected, messages)
    cai_response = resp.to_public_dict()
    maybe_append_metrics_from_env(
        {
            **metrics_event_v1(
                module="api",
                event="api.chat_completions",
                latency_ms=float(resp.latency_ms),
                tokens=int(resp.usage.get("total_tokens") or 0),
                success=True,
            ),
            "provider": resp.provider,
            "model": resp.model,
            "profile_id": resp.profile_id,
            "usage": dict(resp.usage),
        },
    )
    return {
        "schema_version": "api_openai_chat_completion_v1",
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": resp.model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": resp.content,
                },
                "finish_reason": resp.finish_reason or "stop",
            },
        ],
        "usage": dict(resp.usage),
        "cai_model_response": cai_response,
    }


def build_api_openai_chat_completion_stream_events_v1(
    settings: Settings,
    body: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build minimal OpenAI-compatible SSE chunk payloads.

    The provider call is still normalized through ``ModelResponse``; this layer
    only frames the already-complete response as SSE chunks for compatible
    clients that require ``stream=true``.
    """

    non_stream_body = dict(body)
    non_stream_body["stream"] = False
    full = build_api_openai_chat_completion_v1(settings, non_stream_body)
    choice = (full.get("choices") or [{}])[0]
    message = choice.get("message") if isinstance(choice, dict) else {}
    content = str((message or {}).get("content") or "")
    base = {
        "id": full.get("id"),
        "object": "chat.completion.chunk",
        "created": full.get("created"),
        "model": full.get("model"),
        "cai_model_response": full.get("cai_model_response"),
    }
    return [
        {
            "schema_version": "api_openai_chat_completion_chunk_v1",
            **base,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": content},
                    "finish_reason": None,
                },
            ],
        },
        {
            "schema_version": "api_openai_chat_completion_chunk_v1",
            **base,
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": choice.get("finish_reason") or "stop",
                },
            ],
        },
    ]


def _plugins_surface_whitelist(surface: dict[str, Any]) -> dict[str, Any]:
    comps = surface.get("components") if isinstance(surface.get("components"), dict) else {}
    safe_components: dict[str, dict[str, Any]] = {}
    for name, meta in comps.items():
        if not isinstance(meta, dict):
            continue
        safe_components[str(name)] = {
            "exists": bool(meta.get("exists")),
            "files_count": int(meta.get("files_count", 0) or 0),
        }
    return {
        "plugin_version": surface.get("plugin_version"),
        "health_score": int(surface.get("health_score") or 0),
        "compatibility": surface.get("compatibility"),
        "components": safe_components,
    }


def build_api_plugins_surface_v1(
    settings: Settings,
    *,
    include_compat_matrix: bool,
) -> dict[str, Any]:
    """HTTP ``GET /v1/plugins/surface`` 白名单视图；不暴露 ``project_root`` 绝对路径。"""
    surface = list_plugin_surface(settings)
    safe = _plugins_surface_whitelist(surface)
    payload: dict[str, Any] = {
        "schema_version": "api_plugins_surface_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        **safe,
    }
    if include_compat_matrix:
        payload["compat_matrix"] = build_plugin_compat_matrix()
    return payload


def _release_runbook_whitelist(payload: dict[str, Any]) -> dict[str, Any]:
    """裁剪 release runbook 供 HTTP 暴露：去掉仓库绝对路径字段。"""
    out: dict[str, Any] = {}
    for key in (
        "schema_version",
        "changelog",
        "feedback",
        "runbook_steps",
        "writeback_targets",
        "docs",
    ):
        if key in payload:
            out[key] = payload[key]
    return out


def build_api_liveness_v1() -> dict[str, Any]:
    """``GET /healthz`` / ``GET /health``：无鉴权存活探针（兼容原有 ``ok: true``）。"""
    return {
        "schema_version": "api_liveness_v1",
        "ok": True,
        "cai_agent_version": __version__,
    }


def build_api_health_v1(*, workspace: Path, auth_enforced: bool) -> dict[str, Any]:
    """``GET /v1/health``：需 Bearer（与 ``CAI_API_TOKEN`` 策略一致时）的进程/工作区摘要。"""
    root = workspace.expanduser().resolve()
    return {
        "schema_version": "api_health_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "ok": True,
        "cai_agent_version": __version__,
        "workspace": str(root),
        "auth_enforced": bool(auth_enforced),
    }


def build_api_ready_v1(settings: Settings, *, workspace: Path) -> dict[str, Any]:
    """``GET /v1/ready``：配置可加载后的就绪摘要（不含密钥与 ``base_url``）。"""
    root = workspace.expanduser().resolve()
    return {
        "schema_version": "api_ready_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "ok": True,
        "workspace": str(root),
        "mock": bool(settings.mock),
        "has_config_file": bool(str(settings.config_loaded_from or "").strip()),
        "profiles_count": len(getattr(settings, "profiles", ()) or ()),
        "active_profile_id": str(settings.active_profile_id or ""),
    }


def build_api_release_runbook_v1(workspace: Path) -> dict[str, Any]:
    """HTTP ``GET /v1/release/runbook`` 视图；包裹 ``release_runbook_v1`` 白名单字段。"""
    root = workspace
    rb = build_release_runbook_payload(
        repo_root=resolve_release_repo_root(root),
        workspace=root,
    )
    safe = _release_runbook_whitelist(rb if isinstance(rb, dict) else {})
    return {
        "schema_version": "api_release_runbook_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "release_runbook": safe,
    }


class AgentApiThreadingServer(ThreadingHTTPServer):
    workspace: Path
    api_token: str | None
    api_config_path: str | None


def load_settings_for_agent_api_server(server: AgentApiThreadingServer) -> Settings:
    """加载与 CLI 一致的模型配置，并把 ``Settings.workspace`` 对齐 ``api serve -w``（HM-N01-D03）。"""
    ws_path = Path(getattr(server, "workspace")).expanduser().resolve()
    raw_cp = getattr(server, "api_config_path", None)
    cp: str | None = None
    if isinstance(raw_cp, str) and raw_cp.strip():
        cp = str(Path(raw_cp.strip()).expanduser().resolve())
    base = Settings.from_env(config_path=cp, workspace_hint=str(ws_path))
    return replace(base, workspace=str(ws_path))


class AgentApiRequestHandler(BaseHTTPRequestHandler):
    server_version = "cai-agent-api/0"

    def log_message(self, fmt: str, *args: object) -> None:
        return

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Cai-Agent-Api-Version", "0")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code: int, obj: object) -> None:
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send(code, raw, "application/json; charset=utf-8")

    def _send_sse(self, code: int, events: list[dict[str, Any]]) -> None:
        lines: list[str] = []
        for event in events:
            lines.append(f"data: {json.dumps(event, ensure_ascii=False)}\n\n")
        lines.append("data: [DONE]\n\n")
        raw = "".join(lines).encode("utf-8")
        self._send(code, raw, "text/event-stream; charset=utf-8")

    def _auth_ok(self, *, path: str) -> bool:
        if path in ("/healthz", "/health"):
            return True
        token = getattr(self.server, "api_token", None)
        if not token:
            return True
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return False
        got = auth[7:].strip()
        return bool(got) and got == token

    def _read_json_body(self, *, max_bytes: int = 65536) -> dict[str, Any] | None:
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        if n > max_bytes:
            raise ValueError("body_too_large")
        raw = self.rfile.read(n)
        if len(raw) != n:
            raise ValueError("short_read")
        try:
            obj = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"invalid_json:{e}") from e
        return obj if isinstance(obj, dict) else {}

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path or ""
        if not self._auth_ok(path=path):
            self._send_json(401, {"ok": False, "error": "unauthorized", "message": "Bearer token required"})
            return
        ws: Path = getattr(self.server, "workspace")
        api_srv = cast(AgentApiThreadingServer, self.server)
        try:
            if path in ("/healthz", "/health"):
                self._send_json(200, build_api_liveness_v1())
                return
            if path == "/openapi.json":
                self._send_json(200, build_api_openapi_v1())
                return
            if path == "/v1/health":
                tok = getattr(self.server, "api_token", None)
                self._send_json(
                    200,
                    build_api_health_v1(workspace=ws, auth_enforced=bool(tok)),
                )
                return
            if path == "/v1/ready":
                settings = load_settings_for_agent_api_server(api_srv)
                self._send_json(200, build_api_ready_v1(settings, workspace=ws))
                return
            if path == "/v1/status":
                st = build_status_payload(ws)
                summary = st.get("gateway_summary") if isinstance(st.get("gateway_summary"), dict) else {}
                payload = {
                    "schema_version": "api_status_v1",
                    "generated_at": datetime.now(UTC).isoformat(),
                    "workspace": str(ws),
                    "gateway_summary": summary or build_gateway_summary_payload(ws),
                    "gateway_lifecycle": {
                        "schema_version": st.get("schema_version"),
                        "config_exists": st.get("config_exists"),
                        "webhook_running": st.get("webhook_running"),
                        "webhook_pid": st.get("webhook_pid"),
                        "bindings_count": st.get("bindings_count"),
                        "allowlist_enabled": st.get("allowlist_enabled"),
                    },
                }
                self._send_json(200, payload)
                return
            if path == "/v1/profiles":
                settings = load_settings_for_agent_api_server(api_srv)
                self._send_json(200, build_api_profiles_v1(settings))
                return
            if path == "/v1/doctor/summary":
                settings = load_settings_for_agent_api_server(api_srv)
                doc = build_api_doctor_summary_v1(settings)
                self._send_json(200, doc)
                return
            if path == "/v1/models/summary":
                settings = load_settings_for_agent_api_server(api_srv)
                self._send_json(200, build_api_models_summary_v1(settings))
                return
            if path == "/v1/models/capabilities":
                settings = load_settings_for_agent_api_server(api_srv)
                self._send_json(200, build_api_models_capabilities_v1(settings))
                return
            if path == "/v1/models":
                settings = load_settings_for_agent_api_server(api_srv)
                self._send_json(200, build_api_openai_models_v1(settings))
                return
            if path == "/v1/plugins/surface":
                settings = load_settings_for_agent_api_server(api_srv)
                qs = parse_qs(parsed.query or "", keep_blank_values=False)
                compat_raw = (qs.get("compat") or [""])[0].strip().lower()
                include_compat = compat_raw in ("1", "true", "yes", "on")
                self._send_json(
                    200,
                    build_api_plugins_surface_v1(
                        settings,
                        include_compat_matrix=include_compat,
                    ),
                )
                return
            if path == "/v1/release/runbook":
                self._send_json(200, build_api_release_runbook_v1(ws))
                return
            if path == "/v1/gateway/federation-summary":
                self._send_json(200, build_gateway_federation_summary_payload(ws))
                return
        except Exception as e:
            self._send_json(500, {"ok": False, "error": "internal_error", "message": str(e)[:500]})
            return
        self._send_json(404, {"ok": False, "error": "not_found", "message": path})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path or ""
        if not self._auth_ok(path=path):
            self._send_json(401, {"ok": False, "error": "unauthorized", "message": "Bearer token required"})
            return
        ws: Path = getattr(self.server, "workspace")
        api_srv = cast(AgentApiThreadingServer, self.server)
        if path == "/v1/chat/completions":
            try:
                body = self._read_json_body(max_bytes=1_048_576)
                settings = load_settings_for_agent_api_server(api_srv)
                if bool((body or {}).get("stream")):
                    self._send_sse(
                        200,
                        build_api_openai_chat_completion_stream_events_v1(settings, body or {}),
                    )
                else:
                    self._send_json(200, build_api_openai_chat_completion_v1(settings, body or {}))
            except ValueError as e:
                maybe_append_metrics_from_env(
                    metrics_event_v1(module="api", event="api.chat_completions", success=False),
                )
                self._send_json(400, {"ok": False, "error": "bad_request", "message": str(e)})
            except Exception as e:
                maybe_append_metrics_from_env(
                    metrics_event_v1(module="api", event="api.chat_completions", success=False),
                )
                self._send_json(500, {"ok": False, "error": "internal_error", "message": str(e)[:500]})
            return
        if path != "/v1/tasks/run-due":
            if path == "/v1/gateway/route-preview":
                try:
                    body = self._read_json_body()
                except ValueError as e:
                    self._send_json(400, {"ok": False, "error": "bad_request", "message": str(e)})
                    return
                dry = body.get("dry_run")
                dry_run = True if dry is None else bool(dry)
                if not dry_run:
                    self._send_json(
                        403,
                        {
                            "ok": False,
                            "error": "execute_forbidden",
                            "message": "route-preview supports dry_run only",
                        },
                    )
                    return
                payload = build_gateway_proxy_route_preview(
                    root=ws,
                    platform=str(body.get("platform") or ""),
                    channel_id=body.get("channel_id"),
                    target_workspace=body.get("target_workspace"),
                    target_profile_id=body.get("target_profile_id"),
                    dry_run=True,
                )
                self._send_json(200, payload)
                return
            self._send_json(404, {"ok": False, "error": "not_found", "message": path})
            return
        try:
            body = self._read_json_body()
        except ValueError as e:
            self._send_json(400, {"ok": False, "error": "bad_request", "message": str(e)})
            return
        dry = body.get("dry_run")
        if dry is None:
            dry_run = True
        else:
            dry_run = bool(dry)
        if not dry_run:
            self._send_json(
                403,
                {
                    "ok": False,
                    "error": "execute_forbidden",
                    "message": "HTTP API only supports dry_run; use: cai-agent schedule run-due --execute",
                },
            )
            return
        try:
            due = compute_due_tasks(cwd=str(ws))
        except Exception as e:
            self._send_json(500, {"ok": False, "error": "internal_error", "message": str(e)[:500]})
            return
        self._send_json(
            200,
            {
                "schema_version": "api_tasks_run_due_v1",
                "mode": "dry-run",
                "workspace": str(ws),
                "due_jobs": due,
                "executed": [],
            },
        )


def run_agent_api_server(
    *,
    host: str,
    port: int,
    workspace: Path,
    config_path: str | os.PathLike[str] | None = None,
    stderr: TextIO | None = None,
) -> int:
    """阻塞运行直到 ``KeyboardInterrupt``。"""
    err = stderr if stderr is not None else sys.stderr
    root = workspace.expanduser().resolve()
    if not root.is_dir():
        err.write(f"api serve: not a directory: {root}\n")
        return 2
    api_token = resolve_bearer_token("CAI_API_TOKEN", "CAI_OPS_API_TOKEN")
    cfg_resolved: str | None = None
    if config_path is not None and str(config_path).strip():
        p = Path(config_path).expanduser().resolve()
        if not p.is_file():
            err.write(f"api serve: config file not found: {p}\n")
            return 2
        cfg_resolved = str(p)

    httpd = AgentApiThreadingServer((host, port), AgentApiRequestHandler)
    httpd.workspace = root
    httpd.api_token = api_token
    httpd.api_config_path = cfg_resolved

    err.write(
        f"api serve: listening http://{host}:{port}\n"
        f"  workspace: {root}\n"
        f"  config: {cfg_resolved or '(discover from workspace + CAI_CONFIG)'}\n"
        "  CAI_API_TOKEN/CAI_OPS_API_TOKEN: "
        f"{'set' if api_token else 'unset'}\n"
        "  GET /openapi.json\n"
        "  GET /healthz | GET /health | GET /v1/health | GET /v1/ready | GET /v1/status | GET /v1/profiles | GET /v1/doctor/summary\n"
        "  GET /v1/models | GET /v1/models/summary | GET /v1/plugins/surface[?compat=1] | GET /v1/release/runbook\n"
        "  GET /v1/gateway/federation-summary\n"
        "  POST /v1/chat/completions (non-streaming or stream=true SSE)\n"
        "  POST /v1/gateway/route-preview (dry_run only)\n"
        "  POST /v1/tasks/run-due (dry_run only)\n",
    )
    try:
        httpd.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        err.write("api serve: stopped\n")
        return 0
    finally:
        httpd.server_close()
    return 0
