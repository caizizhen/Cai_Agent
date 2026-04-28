from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cai_agent.config import Settings
from cai_agent.tool_provider import build_tool_mcp_bridge_payload, build_tool_provider_registry_payload


def _coerce_max_steps(value: int | str | None) -> tuple[int, str | None]:
    try:
        n = int(value if value is not None else 10)
    except (TypeError, ValueError):
        return 10, "invalid_max_steps"
    if n < 1 or n > 50:
        return max(1, min(n, 50)), "max_steps_out_of_range"
    return n, None


def _normalize_allow_hosts(values: list[str] | tuple[str, ...] | None) -> tuple[list[str], str | None]:
    hosts: list[str] = []
    for raw in values or []:
        for part in str(raw or "").split(","):
            host = part.strip().lower()
            if not host:
                continue
            if "://" in host or "/" in host or "\\" in host or any(c.isspace() for c in host):
                return hosts, "invalid_allow_host"
            hosts.append(host)
    return list(dict.fromkeys(hosts)), None


def _artifact_paths(settings: Settings) -> dict[str, str]:
    root = Path(settings.workspace).expanduser().resolve() / ".cai" / "browser"
    return {
        "root": str(root),
        "screenshots_dir": str(root / "screenshots"),
        "downloads_dir": str(root / "downloads"),
        "trace_dir": str(root / "traces"),
    }


def build_browser_provider_check_payload(
    settings: Settings,
    *,
    max_steps: int | str | None = 10,
    allow_hosts: list[str] | tuple[str, ...] | None = None,
    headless: bool = True,
    isolated: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    """BRW-N02: stable browser provider readiness contract.

    This does not execute browser actions. It verifies the Tool Provider browser
    registry state and reuses the Browser MCP preset bridge so the later executor
    has a stable preflight envelope.
    """
    steps, step_error = _coerce_max_steps(max_steps)
    hosts, host_error = _normalize_allow_hosts(allow_hosts)
    registry = build_tool_provider_registry_payload(settings)
    providers = registry.get("providers") if isinstance(registry.get("providers"), dict) else {}
    browser = providers.get("browser") if isinstance(providers.get("browser"), dict) else {}
    bridge = build_tool_mcp_bridge_payload(settings, preset="browser", force=force)
    errors = [e for e in (step_error, host_error) if e]
    if not bool(browser.get("enabled")):
        errors.append("browser_provider_disabled")
    if not bool(browser.get("configured")):
        errors.append("browser_provider_not_configured")
    if not bool(bridge.get("ok")):
        errors.append("browser_mcp_not_ready")
    ok = not errors
    return {
        "schema_version": "browser_provider_check_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "ok": ok,
        "error": errors[0] if errors else None,
        "errors": errors,
        "provider": "mcp_bridge",
        "preset": "browser",
        "permissions": {"key": "mcp_call_tool", "mode": "ask"},
        "session": {
            "max_steps": steps,
            "allow_hosts": hosts,
            "headless": bool(headless),
            "isolated": bool(isolated),
        },
        "artifacts": _artifact_paths(settings),
        "steps": [],
        "registry": browser,
        "bridge": bridge,
    }


def build_browser_task_payload(
    settings: Settings,
    *,
    goal: str,
    url: str | None = None,
    max_steps: int | str | None = 10,
    allow_hosts: list[str] | tuple[str, ...] | None = None,
    headless: bool = True,
    isolated: bool = True,
    dry_run: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    check = build_browser_provider_check_payload(
        settings,
        max_steps=max_steps,
        allow_hosts=allow_hosts,
        headless=headless,
        isolated=isolated,
        force=force,
    )
    goal_text = str(goal or "").strip()
    errors = [str(e) for e in (check.get("errors") or []) if str(e).strip()]
    if not goal_text:
        errors.insert(0, "goal_empty")
    plan_steps: list[dict[str, Any]] = []
    if url:
        plan_steps.append({"index": 1, "action": "navigate", "url": str(url)})
    if goal_text:
        plan_steps.append({"index": len(plan_steps) + 1, "action": "delegate_to_browser_mcp", "goal": goal_text})
    return {
        "schema_version": "browser_task_v1",
        "ok": not errors,
        "error": errors[0] if errors else None,
        "errors": errors,
        "provider": check.get("provider"),
        "preset": "browser",
        "dry_run": bool(dry_run),
        "url": str(url or ""),
        "goal": goal_text,
        "session": check.get("session"),
        "artifacts": check.get("artifacts"),
        "steps": plan_steps,
        "preflight": check,
        "execution": {
            "implemented": False,
            "next_task": "BRW-N03 / browser executor: map plan steps to explicit mcp_call_tool confirmations",
        },
    }


__all__ = [
    "build_browser_provider_check_payload",
    "build_browser_task_payload",
]
