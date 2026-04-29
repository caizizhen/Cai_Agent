from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cai_agent.config import Settings
from cai_agent.tool_provider import build_tool_mcp_bridge_payload, build_tool_provider_registry_payload
from cai_agent.tools import dispatch


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
        "audit_file": str(root / "audit.jsonl"),
        "manifest_file": str(root / "artifacts-manifest.json"),
    }


def _browser_artifact_manifest(settings: Settings, calls: list[dict[str, Any]]) -> dict[str, Any]:
    paths = _artifact_paths(settings)
    files: list[dict[str, Any]] = []
    for kind, key in (("screenshot", "screenshots_dir"), ("download", "downloads_dir"), ("trace", "trace_dir")):
        root = Path(str(paths[key]))
        if not root.is_dir():
            continue
        for item in sorted(root.rglob("*")):
            if not item.is_file():
                continue
            try:
                rel = item.relative_to(Path(str(paths["root"])))
            except ValueError:
                rel = item.name
            try:
                stat = item.stat()
            except OSError:
                continue
            files.append(
                {
                    "kind": kind,
                    "path": str(item),
                    "relative_path": str(rel).replace("\\", "/"),
                    "size_bytes": int(stat.st_size),
                    "mtime_iso": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                },
            )
    statuses: dict[str, int] = {}
    for call in calls:
        status = str(call.get("status") or "unknown")
        statuses[status] = statuses.get(status, 0) + 1
    return {
        "schema_version": "browser_artifact_manifest_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(Path(settings.workspace).expanduser().resolve()),
        "root": paths["root"],
        "files_count": len(files),
        "files": files,
        "calls_count": len(calls),
        "call_status_counts": statuses,
    }


def _persist_browser_audit(
    settings: Settings,
    *,
    execution: dict[str, Any],
    calls: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    paths = _artifact_paths(settings)
    root = Path(str(paths["root"]))
    for key in ("screenshots_dir", "downloads_dir", "trace_dir"):
        Path(str(paths[key])).mkdir(parents=True, exist_ok=True)
    root.mkdir(parents=True, exist_ok=True)
    manifest = _browser_artifact_manifest(settings, calls)
    manifest_path = Path(str(paths["manifest_file"]))
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    event = {
        "schema_version": "browser_audit_event_v1",
        "event": "browser.execution",
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(Path(settings.workspace).expanduser().resolve()),
        "ok": bool(execution.get("ok")),
        "dry_run": bool(execution.get("dry_run")),
        "confirmed": bool(execution.get("confirmed")),
        "error": execution.get("error"),
        "calls_count": len(calls),
        "call_status_counts": manifest.get("call_status_counts") or {},
        "artifact_manifest": str(manifest_path),
    }
    audit_path = Path(str(paths["audit_file"]))
    with audit_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    audit = {
        "schema_version": "browser_audit_summary_v1",
        "audit_file": str(audit_path),
        "event": event,
    }
    manifest["manifest_file"] = str(manifest_path)
    return audit, manifest


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
    execution = build_browser_mcp_execution_payload(
        settings,
        steps=plan_steps,
        dry_run=dry_run,
        confirmed=False,
    )
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
        "execution": execution,
    }


def _browser_step_to_mcp_call(step: dict[str, Any]) -> dict[str, Any]:
    action = str(step.get("action") or "").strip().lower()
    if action == "navigate":
        return {
            "tool": "browser_navigate",
            "args": {"url": str(step.get("url") or "")},
        }
    if action == "delegate_to_browser_mcp":
        return {
            "tool": "browser_snapshot",
            "args": {},
            "note": "Goal review starts from an audited page snapshot; further actions require a new explicit step plan.",
        }
    return {
        "tool": "",
        "args": {},
        "error": "unsupported_browser_step",
    }


def build_browser_mcp_execution_payload(
    settings: Settings,
    *,
    steps: list[dict[str, Any]],
    dry_run: bool = True,
    confirmed: bool = False,
) -> dict[str, Any]:
    """BRW-N04: map browser_task_v1 steps to explicit Playwright MCP calls."""
    calls: list[dict[str, Any]] = []
    errors: list[str] = []
    for raw in steps:
        step = raw if isinstance(raw, dict) else {}
        mapped = _browser_step_to_mcp_call(step)
        idx = int(step.get("index") or len(calls) + 1)
        tool_name = str(mapped.get("tool") or "")
        call = {
            "index": idx,
            "source_action": str(step.get("action") or ""),
            "permission_key": "mcp_call_tool",
            "tool": tool_name,
            "args": mapped.get("args") if isinstance(mapped.get("args"), dict) else {},
            "status": "planned" if dry_run else "pending",
            "note": mapped.get("note"),
        }
        if not tool_name:
            call["status"] = "blocked"
            call["error"] = str(mapped.get("error") or "unsupported_browser_step")
            errors.append(str(call["error"]))
        calls.append(call)

    if dry_run:
        return {
            "schema_version": "browser_mcp_execution_v1",
            "implemented": True,
            "ok": not errors,
            "dry_run": True,
            "confirmed": bool(confirmed),
            "error": errors[0] if errors else None,
            "errors": errors,
            "calls": calls,
        }
    if not confirmed:
        for call in calls:
            if call.get("status") != "blocked":
                call["status"] = "refused"
        payload = {
            "schema_version": "browser_mcp_execution_v1",
            "implemented": True,
            "ok": False,
            "dry_run": False,
            "confirmed": False,
            "error": "explicit_confirmation_required",
            "errors": ["explicit_confirmation_required", *errors],
            "calls": calls,
        }
        audit, manifest = _persist_browser_audit(settings, execution=payload, calls=calls)
        payload["audit"] = audit
        payload["artifact_manifest"] = manifest
        return payload

    for call in calls:
        if call.get("status") == "blocked":
            continue
        result = dispatch(settings, "mcp_call_tool", {"name": call.get("tool"), "args": call.get("args") or {}})
        call["status"] = "failed" if str(result).startswith("[mcp_call_tool 失败]") else "executed"
        call["result_preview"] = str(result)[:1000]
        if call["status"] == "failed":
            call["error"] = "mcp_call_tool_failed"
            errors.append("mcp_call_tool_failed")
    payload = {
        "schema_version": "browser_mcp_execution_v1",
        "implemented": True,
        "ok": not errors,
        "dry_run": False,
        "confirmed": True,
        "error": errors[0] if errors else None,
        "errors": errors,
        "calls": calls,
    }
    audit, manifest = _persist_browser_audit(settings, execution=payload, calls=calls)
    payload["audit"] = audit
    payload["artifact_manifest"] = manifest
    return payload


__all__ = [
    "build_browser_mcp_execution_payload",
    "build_browser_provider_check_payload",
    "build_browser_task_payload",
]
