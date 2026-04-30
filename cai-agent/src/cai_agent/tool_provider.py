from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cai_agent.config import Settings
from cai_agent.gateway_danger import (
    GATEWAY_DANGER_APPROVE_CONTRACT_SCHEMA_VERSION,
    gateway_danger_approve_tokens,
)
from cai_agent.mcp_presets import (
    allowed_mcp_preset_choices,
    build_mcp_preset_report,
    expand_mcp_preset_choice,
    mcp_preset_doc_path,
)
from cai_agent.tools import dispatch
from cai_agent.voice import build_voice_provider_contract_payload

_TOOL_PROVIDER_CATEGORIES = ("web", "image", "browser", "tts")


def build_tool_provider_contract_payload(settings: Settings) -> dict[str, Any]:
    """HM-N10-D01: unified tool provider contract for web/image/browser/tts."""
    ws = Path(settings.workspace).expanduser().resolve()
    voice = build_voice_provider_contract_payload()
    tts_health = voice.get("health") if isinstance(voice.get("health"), dict) else {}
    tts_cfg = bool(tts_health.get("configured"))
    web_cfg = bool(settings.fetch_url_enabled)
    return {
        "schema_version": "tool_provider_contract_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(ws),
        "providers": {
            "web": {
                "configured": web_cfg,
                "provider": "builtin_fetch_url",
                "permissions": {"key": "fetch_url", "mode": settings.permission_fetch_url},
                "surface": {"allow_hosts_count": len(settings.fetch_url_allowed_hosts), "unrestricted": bool(settings.fetch_url_unrestricted)},
            },
            "image": {
                "configured": False,
                "provider": "none",
                "permissions": {"key": "mcp_call_tool", "mode": "ask"},
                "surface": {"hint": "image provider registry comes in HM-N10-D02+"},
            },
            "browser": {
                "configured": bool(settings.mcp_enabled and settings.mcp_base_url),
                "provider": "mcp_bridge" if bool(settings.mcp_enabled and settings.mcp_base_url) else "none",
                "permissions": {"key": "mcp_call_tool", "mode": "ask"},
                "surface": {
                    "preset": "browser",
                    "mcp_enabled": bool(settings.mcp_enabled),
                    "mcp_base_url_present": bool(settings.mcp_base_url),
                    "doc_path": mcp_preset_doc_path("browser"),
                    "recommended_server": "microsoft/playwright-mcp",
                    "recommended_command": "npx @playwright/mcp@latest --isolated",
                    "isolation": "isolated browser session recommended",
                },
            },
            "tts": {
                "configured": tts_cfg,
                "provider": str(voice.get("provider") or "none"),
                "permissions": {"key": "run_command", "mode": settings.permission_run_command},
                "surface": {
                    "voice_contract_schema": str(voice.get("schema_version") or ""),
                    "tts_enabled": bool((voice.get("tts") if isinstance(voice.get("tts"), dict) else {}).get("enabled")),
                },
            },
        },
        "summary": {
            "configured_count": int(web_cfg) + int(tts_cfg) + int(bool(settings.mcp_enabled and settings.mcp_base_url)),
            "categories": ["web", "image", "browser", "tts"],
        },
        "guard": build_tool_gateway_guard_payload(settings),
    }


def _tool_provider_state_path(workspace: str | Path) -> Path:
    ws = Path(workspace).expanduser().resolve()
    p = ws / ".cai" / "tool-providers.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _read_tool_provider_state(workspace: str | Path) -> dict[str, Any]:
    p = _tool_provider_state_path(workspace)
    if not p.is_file():
        return {}
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _write_tool_provider_state(workspace: str | Path, obj: dict[str, Any]) -> Path:
    p = _tool_provider_state_path(workspace)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


def build_tool_provider_registry_payload(settings: Settings) -> dict[str, Any]:
    """HM-N10-D02: registry payload with category-level enable flags."""
    contract = build_tool_provider_contract_payload(settings)
    ws = Path(settings.workspace).expanduser().resolve()
    providers = contract.get("providers") if isinstance(contract.get("providers"), dict) else {}
    state = _read_tool_provider_state(ws)
    enabled_state = state.get("enabled") if isinstance(state.get("enabled"), dict) else {}
    rows: dict[str, Any] = {}
    enabled_count = 0
    for cat in _TOOL_PROVIDER_CATEGORIES:
        row = providers.get(cat) if isinstance(providers.get(cat), dict) else {}
        configured = bool(row.get("configured"))
        if cat in enabled_state:
            enabled = bool(enabled_state.get(cat))
            source = "config"
        else:
            enabled = configured
            source = "default"
        if enabled:
            enabled_count += 1
        rows[cat] = {
            **row,
            "enabled": enabled,
            "enabled_source": source,
        }
    return {
        "schema_version": "tool_provider_registry_v1",
        "generated_at": contract.get("generated_at"),
        "workspace": contract.get("workspace"),
        "categories": list(_TOOL_PROVIDER_CATEGORIES),
        "providers": rows,
        "state_file": str(_tool_provider_state_path(ws)),
        "summary": {
            "enabled_count": enabled_count,
            "configured_count": int((contract.get("summary") if isinstance(contract.get("summary"), dict) else {}).get("configured_count") or 0),
        },
        "ok": True,
    }


def set_tool_provider_enabled(settings: Settings, *, category: str, enabled: bool) -> dict[str, Any]:
    """HM-N10-D02: persist enable/disable for a tool category."""
    cat = str(category or "").strip().lower()
    if cat not in _TOOL_PROVIDER_CATEGORIES:
        return {
            "schema_version": "tool_provider_toggle_v1",
            "ok": False,
            "error": "invalid_category",
            "category": cat,
            "categories": list(_TOOL_PROVIDER_CATEGORIES),
        }
    ws = Path(settings.workspace).expanduser().resolve()
    state = _read_tool_provider_state(ws)
    enabled_state = state.get("enabled") if isinstance(state.get("enabled"), dict) else {}
    enabled_state[cat] = bool(enabled)
    written = _write_tool_provider_state(
        ws,
        {
            "schema_version": "tool_provider_state_v1",
            "updated_at": datetime.now(UTC).isoformat(),
            "enabled": enabled_state,
        },
    )
    return {
        "schema_version": "tool_provider_toggle_v1",
        "ok": True,
        "category": cat,
        "enabled": bool(enabled),
        "state_file": str(written),
    }


def build_tool_mcp_bridge_payload(
    settings: Settings,
    *,
    preset: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """HM-N10-D03: Tool Gateway bridge view reusing existing MCP preset reports."""
    raw = str(preset or "").strip().lower() or "websearch/notebook"
    names = expand_mcp_preset_choice(raw)
    if not names:
        return {
            "schema_version": "tool_mcp_bridge_v1",
            "ok": False,
            "error": "invalid_preset",
            "preset": raw,
            "supported_presets": list(allowed_mcp_preset_choices()),
        }
    try:
        txt = dispatch(settings, "mcp_list_tools", {"force": bool(force)})
        listed_ok = not txt.startswith("[mcp_list_tools 失败]")
    except Exception as e:
        txt = f"{type(e).__name__}: {e}"
        listed_ok = False
    tool_list: list[str] = []
    for line in str(txt or "").splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("- "):
            s = s[2:].strip()
        if "\t" in s:
            s = s.split("\t", 1)[0].strip()
        if s and not s.startswith("[") and s != "(无 MCP 工具)":
            tool_list.append(s)
    reports = [build_mcp_preset_report(name=name, tool_list=tool_list) for name in names]
    matches: list[str] = []
    missing: list[str] = []
    for rp in reports:
        matches.extend([str(x) for x in (rp.get("matched_tools") or [])])
        missing.extend([str(x) for x in (rp.get("missing_tools") or [])])
    matches = list(dict.fromkeys(matches))
    missing = list(dict.fromkeys(missing))
    preset_ok = all(bool(r.get("ok")) for r in reports) if reports else False
    doc_paths = list(dict.fromkeys(str(r.get("doc_path") or "") for r in reports if str(r.get("doc_path") or "").strip()))
    isolation_hints = list(
        dict.fromkeys(str(r.get("isolation_hint") or "") for r in reports if str(r.get("isolation_hint") or "").strip()),
    )
    return {
        "schema_version": "tool_mcp_bridge_v1",
        "ok": bool(listed_ok and preset_ok),
        "preset": raw,
        "selected_presets": names,
        "mcp_enabled": bool(settings.mcp_enabled),
        "mcp_base_url": settings.mcp_base_url,
        "tools_listed_ok": bool(listed_ok),
        "tools_count": len(tool_list),
        "matched_tools": matches,
        "missing_tools": missing,
        "reports": reports,
        "doc_paths": doc_paths,
        "isolation_hints": isolation_hints,
        "hint": {
            "doc_path": doc_paths[0] if len(doc_paths) == 1 else "docs/ONBOARDING.zh-CN.md",
            "doc_paths": doc_paths,
            "onboarding_path": "docs/ONBOARDING.zh-CN.md",
            "suggested_command": f"cai-agent mcp-check --json --preset {raw} --list-only",
            "print_template_command": f"cai-agent mcp-check --preset {raw} --print-template",
            "isolation_hints": isolation_hints,
        },
    }


def run_tool_provider_web_fetch(
    settings: Settings,
    *,
    url: str,
    estimated_tokens: int = 200,
) -> dict[str, Any]:
    """HM-N10-D04: real web provider example via existing fetch_url tool chain."""
    reg = build_tool_provider_registry_payload(settings)
    providers = reg.get("providers") if isinstance(reg.get("providers"), dict) else {}
    web = providers.get("web") if isinstance(providers.get("web"), dict) else {}
    if not bool(web.get("enabled")):
        return {
            "schema_version": "tool_provider_web_fetch_v1",
            "ok": False,
            "error": "web_provider_disabled",
            "message": "web provider 当前已禁用，请先执行: cai-agent tools enable web",
            "url": str(url),
        }
    if not bool(web.get("configured")):
        return {
            "schema_version": "tool_provider_web_fetch_v1",
            "ok": False,
            "error": "web_provider_not_configured",
            "message": "fetch_url 未配置可用（检查 [fetch_url] 与权限配置）。",
            "url": str(url),
        }
    budget = int(getattr(settings, "cost_budget_max_tokens", 0) or 0)
    est = max(1, int(estimated_tokens))
    if budget > 0 and est > budget:
        return {
            "schema_version": "tool_provider_web_fetch_v1",
            "ok": False,
            "error": "cost_guard_exceeded",
            "message": "estimated_tokens 超出 cost budget",
            "url": str(url),
            "estimated_tokens": est,
            "cost_budget_max_tokens": budget,
        }
    try:
        out = dispatch(settings, "fetch_url", {"url": str(url)})
    except Exception as e:
        return {
            "schema_version": "tool_provider_web_fetch_v1",
            "ok": False,
            "error": "dispatch_failed",
            "message": str(e),
            "url": str(url),
        }
    ok = not str(out).startswith("[fetch_url 失败]")
    return {
        "schema_version": "tool_provider_web_fetch_v1",
        "ok": ok,
        "url": str(url),
        "provider": "builtin_fetch_url",
        "estimated_tokens": est,
        "output": str(out),
    }


def build_tool_gateway_guard_payload(settings: Settings) -> dict[str, Any]:
    """HM-N10-D05: approval/policy/cost guard summary for Tool Gateway."""
    max_tokens = int(getattr(settings, "cost_budget_max_tokens", 0) or 0)
    max_tokens = max(0, max_tokens)
    rr_mode = str(getattr(settings, "run_command_approval_mode", "block_high_risk") or "block_high_risk")
    rr_pats = tuple(getattr(settings, "run_command_high_risk_patterns", ()) or ())
    return {
        "schema_version": "tool_gateway_guard_v1",
        "approval": {
            "web": {"permission_key": "fetch_url", "mode": settings.permission_fetch_url},
            "image": {"permission_key": "mcp_call_tool", "mode": "ask"},
            "browser": {"permission_key": "mcp_call_tool", "mode": "ask"},
            "tts": {"permission_key": "run_command", "mode": settings.permission_run_command},
        },
        "policy": {
            "run_command_approval_mode": rr_mode,
            "run_command_high_risk_patterns_count": len(rr_pats),
            "fetch_url_enabled": bool(settings.fetch_url_enabled),
            "fetch_url_unrestricted": bool(settings.fetch_url_unrestricted),
            "unrestricted_mode": bool(getattr(settings, "unrestricted_mode", False)),
            "dangerous_confirmation_required": bool(
                getattr(settings, "dangerous_confirmation_required", True),
            ),
            "dangerous_audit_log_enabled": bool(
                getattr(settings, "dangerous_audit_log_enabled", False),
            ),
            "dangerous_write_file_critical_basenames_count": len(
                getattr(settings, "dangerous_write_file_critical_basenames", ()) or (),
            ),
            "dangerous_critical_write_skip_if_unchanged": bool(
                getattr(settings, "dangerous_critical_write_skip_if_unchanged", True),
            ),
            "run_command_extra_danger_basenames_count": len(
                getattr(settings, "run_command_extra_danger_basenames", ()) or (),
            ),
        },
        "cost_guard": {
            "max_tokens": max_tokens,
            "enabled": bool(max_tokens > 0),
            "estimated_tokens_hint": {
                "web_fetch_default": 200,
                "bridge_check": 50,
            },
        },
        "danger_gateway_contract_v1": {
            "schema_version": GATEWAY_DANGER_APPROVE_CONTRACT_SCHEMA_VERSION,
            "tokens_effective": list(gateway_danger_approve_tokens()),
            "tokens_env": "CAI_GATEWAY_DANGER_APPROVE_TOKENS",
            "slack_execute_on_event": True,
            "discord_execute_on_message": True,
        },
    }


__all__ = [
    "build_tool_provider_contract_payload",
    "build_tool_provider_registry_payload",
    "build_tool_mcp_bridge_payload",
    "build_tool_gateway_guard_payload",
    "run_tool_provider_web_fetch",
    "set_tool_provider_enabled",
]
