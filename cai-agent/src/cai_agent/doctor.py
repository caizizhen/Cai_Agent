from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any

from cai_agent import __version__
from cai_agent.command_registry import build_command_discovery_payload
from cai_agent.config import Settings
from cai_agent.context import INSTRUCTION_FILE_NAMES
from cai_agent.ecc_layout import iter_hooks_json_paths
from cai_agent.model_gateway import KNOWN_MODEL_HEALTH_STATUSES, build_model_capabilities_payload
from cai_agent.models import ping_profile
from cai_agent.profiles import (
    build_profile_contract_payload,
    build_profile_home_migration_diag_v1,
)
from cai_agent.feedback import feedback_stats
from cai_agent.memory import resolve_active_memory_provider
from cai_agent.plugin_registry import build_plugin_compat_matrix, list_plugin_surface
from cai_agent.provider_registry import provider_readiness_snapshot
from cai_agent.release_runbook import build_release_runbook_payload, resolve_release_repo_root
from cai_agent.runtime.registry import get_runtime_backend
from cai_agent.tool_provider import build_tool_provider_contract_payload
from cai_agent.voice import build_voice_provider_contract_payload


def build_installation_guidance() -> dict[str, Any]:
    return {
        "schema_version": "doctor_installation_guidance_v1",
        "onboarding_doc": "docs/ONBOARDING.zh-CN.md",
        "docs_index": "docs/README.zh-CN.md",
        "upgrade_docs": ["CHANGELOG.zh-CN.md", "CHANGELOG.md"],
        "repair_command": "cai-agent repair --dry-run --json",
        "recommended_flow": [
            "cai-agent init",
            "cai-agent doctor",
            "cai-agent repair --dry-run",
            'cai-agent run "用一句话描述当前工作区用途"',
        ],
    }


def _template_available(name: str) -> bool:
    try:
        resources.files("cai_agent").joinpath(f"templates/{name}").read_bytes()
        return True
    except Exception:
        return False


def _root_config_status(settings: Settings, root: Path) -> tuple[Path | None, bool]:
    config_path = root / "cai-agent.toml"
    configured = str(settings.config_loaded_from or "").strip()
    configured_path = Path(configured).expanduser().resolve() if configured else None
    if configured_path is not None:
        try:
            configured_path.relative_to(root)
        except ValueError:
            configured_path = None
    visible_path = configured_path or config_path
    exists = config_path.is_file() or bool(configured_path and configured_path.is_file())
    return visible_path, exists


def build_doctor_install_diagnostic(settings: Settings) -> dict[str, Any]:
    """Installation surface diagnostics for `doctor --json`.

    This block intentionally stays local and cheap: it checks whether the
    workspace has the minimum files and bundled templates needed for init/repair.
    """
    root = Path(settings.workspace).expanduser().resolve()
    visible_config_path, config_exists = _root_config_status(settings, root)
    checks = [
        {
            "id": "workspace_exists",
            "ok": root.is_dir(),
            "severity": "error",
            "path": str(root),
            "repair_action": "create_workspace_dir",
        },
        {
            "id": "config_exists",
            "ok": config_exists,
            "severity": "warning",
            "path": str(visible_config_path),
            "repair_action": "create_config_from_template",
        },
        {
            "id": "template_default_available",
            "ok": _template_available("cai-agent.example.toml"),
            "severity": "error",
            "repair_action": None,
        },
        {
            "id": "template_starter_available",
            "ok": _template_available("cai-agent.starter.toml"),
            "severity": "warning",
            "repair_action": None,
        },
        {
            "id": "cai_dir_exists",
            "ok": (root / ".cai").is_dir(),
            "severity": "warning",
            "path": str(root / ".cai"),
            "repair_action": "create_cai_dir",
        },
    ]
    return {
        "schema_version": "doctor_install_v1",
        "workspace": str(root),
        "config_path": str(visible_config_path),
        "python_executable": os.sys.executable,
        "python_version": os.sys.version.split()[0],
        "ok": all(bool(c.get("ok")) or c.get("severity") == "warning" for c in checks),
        "checks": checks,
        "recommended_commands": [
            "cai-agent repair --dry-run --json",
            "cai-agent repair --apply",
            "cai-agent doctor --json",
        ],
    }


def build_doctor_sync_diagnostic(settings: Settings) -> dict[str, Any]:
    """Local sync/drift diagnostics for home and workspace support assets."""
    root = Path(settings.workspace).expanduser().resolve()
    expected = [
        {
            "id": "cai_dir",
            "path": root / ".cai",
            "kind": "directory",
            "repair_action": "create_cai_dir",
        },
        {
            "id": "gateway_dir",
            "path": root / ".cai" / "gateway",
            "kind": "directory",
            "repair_action": "create_gateway_dir",
        },
        {
            "id": "commands_dir",
            "path": root / "commands",
            "kind": "directory",
            "repair_action": "create_commands_dir",
        },
        {
            "id": "skills_dir",
            "path": root / "skills",
            "kind": "directory",
            "repair_action": "create_skills_dir",
        },
        {
            "id": "rules_common_dir",
            "path": root / "rules" / "common",
            "kind": "directory",
            "repair_action": "create_rules_common_dir",
        },
        {
            "id": "rules_python_dir",
            "path": root / "rules" / "python",
            "kind": "directory",
            "repair_action": "create_rules_python_dir",
        },
        {
            "id": "hooks_dir",
            "path": root / "hooks",
            "kind": "directory",
            "repair_action": "create_hooks_dir",
        },
        {
            "id": "hooks_json",
            "path": root / "hooks" / "hooks.json",
            "kind": "file",
            "repair_action": "create_hooks_json_minimal",
        },
    ]
    rows: list[dict[str, Any]] = []
    hooks_json_exists = any(p.is_file() for p in iter_hooks_json_paths(root))
    for item in expected:
        p = Path(item["path"])
        exists = hooks_json_exists if item["id"] == "hooks_json" else (
            p.is_dir() if item["kind"] == "directory" else p.exists()
        )
        rows.append(
            {
                "id": item["id"],
                "kind": item["kind"],
                "path": str(p),
                "exists": exists,
                "status": "ok" if exists else "missing",
                "repair_action": None if exists else item["repair_action"],
            },
        )
    return {
        "schema_version": "doctor_sync_v1",
        "workspace": str(root),
        "ok": all(bool(r.get("exists")) for r in rows),
        "items": rows,
        "repair_command": "cai-agent repair --dry-run --json",
    }


def build_feedback_triage_payload(settings: Settings) -> dict[str, Any]:
    install = build_doctor_install_diagnostic(settings)
    sync = build_doctor_sync_diagnostic(settings)
    install_missing = [
        str(c.get("id"))
        for c in install.get("checks") or []
        if isinstance(c, dict) and not bool(c.get("ok"))
    ]
    sync_missing = [
        str(r.get("id"))
        for r in sync.get("items") or []
        if isinstance(r, dict) and not bool(r.get("exists"))
    ]
    needs_repair = bool(install_missing or sync_missing)
    return {
        "schema_version": "doctor_feedback_triage_v1",
        "needs_repair_before_feedback": needs_repair,
        "missing_checks": install_missing + sync_missing,
        "recommended_flow": [
            "cai-agent doctor --json",
            "cai-agent repair --dry-run --json",
            "cai-agent repair --apply",
            "cai-agent feedback bug <summary> --detail <steps> --json",
            "cai-agent feedback bundle --dest dist/feedback-bundle.json --json",
        ],
    }


def build_repair_plan(settings: Settings, *, preset: str = "default") -> dict[str, Any]:
    """Build a conservative local repair plan; no writes are performed here."""
    root = Path(settings.workspace).expanduser().resolve()
    config_path = root / "cai-agent.toml"
    preset_norm = "starter" if str(preset or "").strip().lower() == "starter" else "default"
    actions: list[dict[str, Any]] = []
    dirs = [
        ("create_workspace_dir", root),
        ("create_cai_dir", root / ".cai"),
        ("create_gateway_dir", root / ".cai" / "gateway"),
        ("create_commands_dir", root / "commands"),
        ("create_skills_dir", root / "skills"),
        ("create_rules_common_dir", root / "rules" / "common"),
        ("create_rules_python_dir", root / "rules" / "python"),
        ("create_hooks_dir", root / "hooks"),
    ]
    for action_id, path in dirs:
        exists = path.is_dir()
        actions.append(
            {
                "id": action_id,
                "type": "mkdir",
                "path": str(path),
                "needed": not exists,
                "status": "skip_exists" if exists else "pending",
            },
        )
    _, config_exists = _root_config_status(settings, root)
    actions.append(
        {
            "id": "create_config_from_template",
            "type": "write_template",
            "path": str(config_path),
            "template": (
                "templates/cai-agent.starter.toml"
                if preset_norm == "starter"
                else "templates/cai-agent.example.toml"
            ),
            "needed": not config_exists,
            "status": "skip_exists" if config_exists else "pending",
        },
    )
    hooks_json_path = root / "hooks" / "hooks.json"
    hooks_json_exists = any(p.is_file() for p in iter_hooks_json_paths(root))
    actions.append(
        {
            "id": "create_hooks_json_minimal",
            "type": "write_template",
            "path": str(hooks_json_path),
            "template": "templates/ecc/hooks.min.json",
            "needed": not hooks_json_exists,
            "status": "skip_exists" if hooks_json_exists else "pending",
        },
    )
    return {
        "schema_version": "repair_plan_v1",
        "workspace": str(root),
        "preset": preset_norm,
        "ok": True,
        "actions": actions,
        "summary": {
            "actions_total": len(actions),
            "actions_needed": sum(1 for a in actions if bool(a.get("needed"))),
        },
    }


def apply_repair_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Apply actions from `build_repair_plan` without overwriting existing files."""
    applied: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for action in plan.get("actions") or []:
        if not isinstance(action, dict) or not bool(action.get("needed")):
            continue
        aid = str(action.get("id") or "")
        typ = str(action.get("type") or "")
        path = Path(str(action.get("path") or "")).expanduser().resolve()
        try:
            if typ == "mkdir":
                path.mkdir(parents=True, exist_ok=True)
                applied.append({"id": aid, "path": str(path), "status": "applied"})
            elif typ == "write_template":
                if path.exists():
                    applied.append({"id": aid, "path": str(path), "status": "skip_exists"})
                    continue
                tpl = str(action.get("template") or "templates/cai-agent.example.toml")
                data = resources.files("cai_agent").joinpath(tpl).read_bytes()
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                applied.append({"id": aid, "path": str(path), "status": "applied"})
            else:
                errors.append({"id": aid, "path": str(path), "error": "unknown_action_type"})
        except Exception as e:
            errors.append({"id": aid, "path": str(path), "error": str(e)})
    return {
        "schema_version": "repair_result_v1",
        "workspace": plan.get("workspace"),
        "ok": not errors,
        "applied": applied,
        "errors": errors,
        "plan": plan,
    }


def build_doctor_cai_dir_health(root: Path) -> dict[str, Any]:
    """`.cai/` 目录健康检查：gateway map、hooks.json 存在性与快速可读性。"""
    cai = root / ".cai"
    gw_dir = cai / "gateway"
    tg_map = gw_dir / "telegram-session-map.json"
    dc_map = gw_dir / "discord-session-map.json"
    sl_map = gw_dir / "slack-session-map.json"
    hooks_candidates = [
        root / "hooks" / "hooks.json",
        cai / "hooks" / "hooks.json",
    ]
    hooks_found = next((str(p) for p in hooks_candidates if p.is_file()), None)
    hooks_valid: bool | None = None
    if hooks_found:
        try:
            raw = json.loads(Path(hooks_found).read_text(encoding="utf-8"))
            hooks_valid = isinstance(raw, dict) and isinstance(raw.get("hooks"), list)
        except Exception:
            hooks_valid = False

    def _map_readable(p: Path) -> bool | None:
        if not p.is_file():
            return None
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
            return isinstance(obj, dict)
        except Exception:
            return False

    discord_map_summary: dict[str, Any] = {
        "bindings_count": 0,
        "allowlist_enabled": False,
        "map_path": str(dc_map),
    }
    try:
        from cai_agent.gateway_discord import discord_list_bindings

        _dl = discord_list_bindings(root)
        _b = _dl.get("bindings") if isinstance(_dl.get("bindings"), dict) else {}
        discord_map_summary = {
            "bindings_count": len(_b),
            "allowlist_enabled": bool(_dl.get("allowlist_enabled")),
            "map_path": str(_dl.get("map_path") or dc_map),
        }
    except Exception:
        pass

    return {
        "cai_dir_exists": cai.is_dir(),
        "gateway_dir_exists": gw_dir.is_dir(),
        "telegram_map_exists": tg_map.is_file(),
        "telegram_map_readable": _map_readable(tg_map),
        "discord_map_exists": dc_map.is_file(),
        "discord_map_readable": _map_readable(dc_map),
        "discord_map_summary": discord_map_summary,
        "slack_map_exists": sl_map.is_file(),
        "slack_map_readable": _map_readable(sl_map),
        "hooks_file": hooks_found,
        "hooks_file_valid": hooks_valid,
    }


def _mask_api_key(key: str) -> str:
    if not key:
        return "(空)"
    if len(key) <= 6:
        return "******"
    return f"{key[:3]}…{key[-2:]}（已打码）"


def _git_inside_worktree(root: Path) -> bool:
    try:
        r = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            timeout=3.0,
            shell=False,
        )
        return r.returncode == 0 and (r.stdout or "").strip() == "true"
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def build_doctor_payload(settings: Settings) -> dict[str, Any]:
    """结构化诊断（`doctor --json`），字段与文本 doctor 同源信息。"""
    root = Path(settings.workspace).resolve()
    release_root = resolve_release_repo_root(root)
    key_line = _mask_api_key(settings.api_key)
    env_name = settings.active_api_key_env
    if env_name:
        key_line += f" | env={env_name}"
        if not settings.api_key:
            key_line += " (AUTH_FAIL: env not set)"
    ping_on = os.getenv("CAI_DOCTOR_PING", "").strip().lower() in (
        "1", "true", "yes", "on",
    )
    pings: list[dict[str, Any]] = []
    if ping_on:
        for p in settings.profiles:
            r = ping_profile(p, trust_env=settings.http_trust_env, timeout_sec=8.0)
            pings.append(
                {
                    "id": p.id,
                    "status": r.get("status", "?"),
                    "http_status": r.get("http_status"),
                    "message": (r.get("message") or "").strip(),
                },
            )
    instruction_files: dict[str, bool] = {}
    if root.is_dir():
        for name in INSTRUCTION_FILE_NAMES:
            instruction_files[name] = (root / name).is_file()
    inside = _git_inside_worktree(root)
    api_present = bool(str(settings.api_key or "").strip())
    _rb = str(getattr(settings, "runtime_backend", "local") or "local").strip().lower() or "local"
    _rt = get_runtime_backend(_rb, settings=settings)
    profile_contract = build_profile_contract_payload(
        settings.profiles,
        profiles_explicit=bool(settings.profiles_explicit),
        active_profile_id=settings.active_profile_id,
        subagent_profile_id=settings.subagent_profile_id,
        planner_profile_id=settings.planner_profile_id,
        env_active_override=os.getenv("CAI_ACTIVE_MODEL"),
        workspace_root=settings.workspace,
    )
    profile_home_migration = build_profile_home_migration_diag_v1(
        settings.profiles,
        profiles_explicit=bool(settings.profiles_explicit),
        workspace_root=settings.workspace,
    )
    memory_provider = resolve_active_memory_provider(root)
    return {
        "schema_version": "doctor_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "cai_agent_version": __version__,
        "config_loaded_from": settings.config_loaded_from,
        "provider": settings.provider,
        "workspace": str(root),
        "base_url": settings.base_url,
        "model": settings.model,
        "api_key_present": api_present,
        "api_key_masked_line": key_line,
        "active_profile_id": settings.active_profile_id,
        "profile_contract": profile_contract,
        "profile_home_migration": profile_home_migration,
        "profiles_count": len(settings.profiles),
        "subagent_profile_id": settings.subagent_profile_id or None,
        "planner_profile_id": settings.planner_profile_id or None,
        "model_routing_enabled": bool(getattr(settings, "model_routing_enabled", True)),
        "model_routing_rules_count": len(getattr(settings, "model_routing_rules", ()) or ()),
        "models_profile_routes_count": len(getattr(settings, "models_profile_routes", ()) or ()),
        "model_gateway": {
            "schema_version": "doctor_model_gateway_v1",
            "capabilities": build_model_capabilities_payload(
                settings.profiles,
                active_profile_id=settings.active_profile_id,
                context_window_fallback=int(getattr(settings, "context_window", 0) or 0) or None,
            ),
            "known_health_statuses": list(KNOWN_MODEL_HEALTH_STATUSES),
            "onboarding_runbook": "docs/MODEL_ONBOARDING_RUNBOOK.zh-CN.md",
            "recommended_flow": [
                "cai-agent models onboarding --id <id> --preset <preset> --model <model> --json",
                "cai-agent models capabilities <id> --json",
                "cai-agent models ping <id> --json",
                "cai-agent models ping <id> --chat-smoke --json",
                "cai-agent models routing-test --role active --goal \"smoke test\" --json",
            ],
            "chat_smoke_default": "explicit_only",
        },
        "provider_registry_readiness": provider_readiness_snapshot(),
        "temperature": settings.temperature,
        "llm_timeout_sec": settings.llm_timeout_sec,
        "http_trust_env": settings.http_trust_env,
        "mock": settings.mock,
        "max_iterations": settings.max_iterations,
        "command_timeout_sec": settings.command_timeout_sec,
        "runtime": {
            "schema_version": "doctor_runtime_v1",
            "configured_backend": _rb,
            "resolved_backend": _rt.name,
            "reachable": bool(_rt.exists()),
            "describe": _rt.describe(),
        },
        "project_context": settings.project_context,
        "git_context": settings.git_context,
        "mcp_enabled": settings.mcp_enabled,
        "mcp_base_url": settings.mcp_base_url or None,
        "mcp_timeout_sec": settings.mcp_timeout_sec,
        "fetch_url_enabled": settings.fetch_url_enabled,
        "fetch_url_unrestricted": settings.fetch_url_unrestricted,
        "fetch_url_allowed_hosts_count": len(settings.fetch_url_allowed_hosts),
        "fetch_url_max_redirects": settings.fetch_url_max_redirects,
        "fetch_url_allow_private_resolved_ips": settings.fetch_url_allow_private_resolved_ips,
        "permission_fetch_url": settings.permission_fetch_url,
        "profile_ping_skipped": not ping_on,
        "profile_pings": pings,
        "instruction_files": instruction_files,
        "workspace_is_dir": root.is_dir(),
        "git_inside_work_tree": inside,
        "cai_dir_health": build_doctor_cai_dir_health(root),
        "install": build_doctor_install_diagnostic(settings),
        "sync": build_doctor_sync_diagnostic(settings),
        "command_center": build_command_discovery_payload(settings),
        "feedback_triage": build_feedback_triage_payload(settings),
        "plugins": {
            "schema_version": "doctor_plugins_bundle_v1",
            "surface": list_plugin_surface(settings),
            "compat_matrix": build_plugin_compat_matrix(),
        },
        "memory_policy": {
            "max_entries_per_day": int(getattr(settings, "memory_policy_max_entries_per_day", 10_000)),
            "default_ttl_days": getattr(settings, "memory_policy_default_ttl_days", None),
            "recall_negative_audit": bool(
                getattr(settings, "memory_policy_recall_negative_audit", True),
            ),
        },
        "memory_provider": memory_provider,
        "skills_auto_extract": {
            "enabled": bool(getattr(settings, "skills_auto_extract_enabled", False)),
            "mode": str(getattr(settings, "skills_auto_extract_mode", "template") or "template"),
            "min_goal_chars": int(getattr(settings, "skills_auto_extract_min_goal_chars", 8) or 8),
        },
        "skills_auto_improve": {
            "min_usage_count": int(getattr(settings, "skills_auto_improve_min_usage_count", 1) or 1),
            "min_days_since_last_improve": int(
                getattr(settings, "skills_auto_improve_min_days_since_last_improve", 0) or 0,
            ),
        },
        "voice": build_voice_provider_contract_payload(),
        "tool_provider": build_tool_provider_contract_payload(settings),
        "installation_guidance": build_installation_guidance(),
        "release_runbook": (
            release_runbook := build_release_runbook_payload(repo_root=release_root, workspace=root)
        ),
        "feedback": (
            release_runbook.get("feedback")
            if isinstance(release_runbook.get("feedback"), dict)
            else feedback_stats(root)
        ),
    }


def build_api_doctor_summary_v1(settings: Settings) -> dict[str, Any]:
    """HTTP ``GET /v1/doctor/summary`` 白名单视图：不含 ``base_url`` / ``model`` / 未打码密钥等。"""
    p = build_doctor_payload(settings)
    return {
        "schema_version": "api_doctor_summary_v1",
        "generated_at": p.get("generated_at"),
        "cai_agent_version": p.get("cai_agent_version"),
        "workspace": p.get("workspace"),
        "mock": p.get("mock"),
        "config_loaded_from": p.get("config_loaded_from"),
        "active_profile_id": p.get("active_profile_id"),
        "profiles_count": p.get("profiles_count"),
        "subagent_profile_id": p.get("subagent_profile_id"),
        "planner_profile_id": p.get("planner_profile_id"),
        "profile_contract": p.get("profile_contract"),
        "profile_home_migration": p.get("profile_home_migration"),
        "memory_policy": p.get("memory_policy"),
        "memory_provider": p.get("memory_provider"),
        "model_routing_enabled": p.get("model_routing_enabled"),
        "model_routing_rules_count": p.get("model_routing_rules_count"),
        "models_profile_routes_count": p.get("models_profile_routes_count"),
        "cai_dir_health": p.get("cai_dir_health"),
        "install": p.get("install"),
        "sync": p.get("sync"),
        "command_center": p.get("command_center"),
        "feedback_triage": p.get("feedback_triage"),
        "voice": p.get("voice"),
        "tool_provider": p.get("tool_provider"),
        "installation_guidance": p.get("installation_guidance"),
    }


def run_doctor(
    settings: Settings,
    *,
    json_output: bool = False,
    fail_on_missing_api_key: bool = False,
) -> int:
    root = Path(settings.workspace).resolve()
    if json_output:
        payload = build_doctor_payload(settings)
        print(json.dumps(payload, ensure_ascii=False))
        if fail_on_missing_api_key and not settings.mock:
            if not bool(str(settings.api_key or "").strip()):
                return 2
        return 0

    print(f"cai-agent {__version__} — doctor")
    print()
    print("配置来源:", settings.config_loaded_from or "（无 TOML，仅默认 + 环境变量）")
    print("提供方:  ", settings.provider)
    print("工作区:  ", root)
    print("API:     ", settings.base_url)
    print("模型:    ", settings.model)
    key_line = _mask_api_key(settings.api_key)
    env_name = settings.active_api_key_env
    if env_name:
        key_line += f" | env={env_name}"
        if not settings.api_key:
            key_line += " (AUTH_FAIL: env not set)"
    print("API Key: ", key_line)
    print("Profile: ", settings.active_profile_id, f"(共 {len(settings.profiles)} 个)")
    profile_contract = build_profile_contract_payload(
        settings.profiles,
        profiles_explicit=bool(settings.profiles_explicit),
        active_profile_id=settings.active_profile_id,
        subagent_profile_id=settings.subagent_profile_id,
        planner_profile_id=settings.planner_profile_id,
        env_active_override=os.getenv("CAI_ACTIVE_MODEL"),
        workspace_root=settings.workspace,
    )
    print(
        "Profile Contract:",
        f"{profile_contract.get('source_kind')} | migration={profile_contract.get('migration_state')}",
    )
    mig_diag = build_profile_home_migration_diag_v1(
        settings.profiles,
        profiles_explicit=bool(settings.profiles_explicit),
        workspace_root=settings.workspace,
    )
    orphans = mig_diag.get("orphan_profile_dirs") or []
    if orphans:
        print("Profile Home / 迁移:", f"未绑定目录={','.join(str(x) for x in orphans)}")
    else:
        print("Profile Home / 迁移:", "未绑定目录=-")
    for hz in mig_diag.get("hints_zh") or []:
        print("  ", hz)
    print("  机读: doctor --json -> profile_home_migration")
    if settings.subagent_profile_id or settings.planner_profile_id:
        print(
            "路由:    ",
            f"subagent={settings.subagent_profile_id or '-'} "
            f"planner={settings.planner_profile_id or '-'}",
        )
    print("温度:    ", settings.temperature)
    print("HTTP 超时:", settings.llm_timeout_sec, "s")
    print("信任代理:", settings.http_trust_env)
    print("Mock:    ", settings.mock)
    print(
        "模型路由: [[models.route]]",
        len(getattr(settings, "models_profile_routes", ()) or ()),
        "条 | [models.routing.rules]",
        len(getattr(settings, "model_routing_rules", ()) or ()),
        "条",
    )
    prr = provider_readiness_snapshot()
    ents = prr.get("entries") or []
    ready = sum(1 for e in ents if isinstance(e, dict) and e.get("env_present"))
    print(f"Provider Registry: {len(ents)} 项预设，其中密钥已导出 ≈ {ready} 项（详见 doctor --json）")
    print("最大轮次:", settings.max_iterations)
    print("命令超时:", settings.command_timeout_sec, "s")
    _rb2 = str(getattr(settings, "runtime_backend", "local") or "local").strip().lower() or "local"
    _rt2 = get_runtime_backend(_rb2, settings=settings)
    print(
        "运行后端:",
        _rb2,
        f"(解析为 {_rt2.name}, reachable={_rt2.exists()})",
    )
    print("项目说明:", settings.project_context)
    print("Git 摘要:", settings.git_context)
    print("MCP 开关:", settings.mcp_enabled)
    print("MCP URL: ", settings.mcp_base_url or "(未配置)")
    print("MCP 超时:", settings.mcp_timeout_sec, "s")
    print("fetch_url:", "启用" if settings.fetch_url_enabled else "关闭", end="")
    if settings.fetch_url_enabled:
        mode = (
            "无主机白名单(unrestricted)"
            if settings.fetch_url_unrestricted
            else f"白名单 {len(settings.fetch_url_allowed_hosts)} 项"
        )
        print(
            f" | {mode} | 权限={settings.permission_fetch_url} "
            f"| max_redirects={settings.fetch_url_max_redirects}"
            f" | allow_private_dns={settings.fetch_url_allow_private_resolved_ips}",
        )
    else:
        print()
    print()

    ping_on = os.getenv("CAI_DOCTOR_PING", "").strip().lower() in (
        "1", "true", "yes", "on",
    )
    if ping_on:
        print("Profile 健康检查 (GET …/models，不消耗 chat token):")
        for p in settings.profiles:
            r = ping_profile(p, trust_env=settings.http_trust_env, timeout_sec=8.0)
            status = r.get("status", "?")
            msg = (r.get("message") or "").strip()
            http = r.get("http_status")
            extra = f" http={http}" if http is not None else ""
            tail = f" | {msg}" if msg else ""
            print(f"  {p.id}: {status}{extra}{tail}")
        print()
    else:
        print(
            "Profile 健康检查: 已跳过（避免默认 doctor 触网变慢）。"
            "需要探测时请设置环境变量 CAI_DOCTOR_PING=1 后重跑 doctor。",
        )
        print()

    if root.is_dir():
        print("工作区根目录说明文件:")
        for name in INSTRUCTION_FILE_NAMES:
            p = root / name
            mark = "[有]" if p.is_file() else "[无]"
            print(f"  {mark} {name}")
    else:
        print("工作区目录不存在。")
    print()

    inside = _git_inside_worktree(root)

    print("Git:     ", "在工作树内" if inside else "非 Git 目录或未安装 git")
    print()
    cai_health = build_doctor_cai_dir_health(root)
    print(".cai/ 状态:")
    print(f"  cai_dir={cai_health['cai_dir_exists']} "
          f"gateway_dir={cai_health['gateway_dir_exists']} "
          f"tg_map={cai_health['telegram_map_exists']} "
          f"dc_map={cai_health['discord_map_exists']} "
          f"sl_map={cai_health['slack_map_exists']}")
    _dc_sum = cai_health.get("discord_map_summary") if isinstance(cai_health.get("discord_map_summary"), dict) else {}
    if cai_health.get("discord_map_exists") or int(_dc_sum.get("bindings_count") or 0) > 0:
        print(
            "  Discord: "
            f"绑定 {int(_dc_sum.get('bindings_count') or 0)} 条 | "
            f"白名单={'开' if _dc_sum.get('allowlist_enabled') else '关'} | "
            "API 自检: cai-agent gateway discord health --json（需 Token）",
        )
    hf = cai_health["hooks_file"]
    hv = cai_health["hooks_file_valid"]
    if hf:
        print(f"  hooks.json={hf} valid={hv}")
    else:
        print("  hooks.json=（未找到，可选）")
    print()
    install_diag = build_doctor_install_diagnostic(settings)
    sync_diag = build_doctor_sync_diagnostic(settings)
    install_missing = [
        c.get("id")
        for c in install_diag.get("checks") or []
        if isinstance(c, dict) and not bool(c.get("ok"))
    ]
    sync_missing = [
        r.get("id")
        for r in sync_diag.get("items") or []
        if isinstance(r, dict) and not bool(r.get("exists"))
    ]
    print("安装/同步自检:")
    print(
        f"  install_ok={install_diag.get('ok')} sync_ok={sync_diag.get('ok')} "
        f"missing={','.join(str(x) for x in (install_missing + sync_missing)) or '-'}",
    )
    print("  修复预览: cai-agent repair --dry-run --json")
    print("  反馈 bundle: cai-agent feedback bundle --dest dist/feedback-bundle.json --json")
    print()
    surf = list_plugin_surface(settings)
    hs = int(surf.get("health_score") or 0)
    print("插件扩展面:")
    print(f"  health_score={hs}（机读: cai-agent plugins --json）")
    print(
        "  兼容矩阵: cai-agent plugins --json --with-compat-matrix；"
        "说明见 docs/PLUGIN_COMPAT_MATRIX.zh-CN.md（英文: docs/PLUGIN_COMPAT_MATRIX.md）",
    )
    print()
    mepd = int(getattr(settings, "memory_policy_max_entries_per_day", 10_000) or 0)
    mtd = getattr(settings, "memory_policy_default_ttl_days", None)
    rna = bool(getattr(settings, "memory_policy_recall_negative_audit", True))
    print("记忆策略 [memory.policy]:")
    print(f"  max_entries_per_day={mepd}")
    print(f"  default_ttl_days={mtd!r}")
    print(f"  recall_negative_audit={'开' if rna else '关'}（零命中 recall 写负样本审计）")
    print("  机读: doctor --json -> memory_policy")
    print()
    rel = build_release_runbook_payload(repo_root=resolve_release_repo_root(root), workspace=root)
    rel_changelog = rel.get("changelog") if isinstance(rel.get("changelog"), dict) else {}
    rel_bilingual = rel_changelog.get("bilingual") if isinstance(rel_changelog.get("bilingual"), dict) else {}
    rel_semantic = rel_changelog.get("semantic") if isinstance(rel_changelog.get("semantic"), dict) else {}
    rel_feedback = rel.get("feedback") if isinstance(rel.get("feedback"), dict) else {}
    install = build_installation_guidance()
    print("发版闭环:")
    print(
        f"  CHANGELOG bilingual={bool(rel_bilingual.get('ok'))} "
        f"semantic={bool(rel_semantic.get('ok'))} "
        f"feedback_total={int(rel_feedback.get('total', 0) or 0)}",
    )
    print("  runbook: cai-agent doctor --json -> cai-agent release-changelog --json --semantic")
    print("  docs:    docs/CHANGELOG_SYNC.zh-CN.md | docs/qa/T7_RELEASE_GATE_CHECKLIST.zh-CN.md")
    print()
    print("安装 / 升级指引:")
    print(
        "  onboarding: "
        f"{install.get('onboarding_doc')} | docs index: {install.get('docs_index')}",
    )
    print(f"  upgrade:    {' | '.join(str(x) for x in (install.get('upgrade_docs') or []))}")
    print()
    print("建议下一步:")
    print("  1) 若尚未生成配置: cai-agent init（多后端入门: cai-agent init --preset starter）")
    print("  2) 编辑 cai-agent.toml 中 [llm] 或 [[models.profile]]（base_url / model / api_key_env）")
    print("  3) 试跑: cai-agent run \"用一句话描述当前工作区用途\"")
    print(
        "  4) 多模型: cai-agent models list；新增: models add --preset vllm|gateway|openrouter|zhipu …；"
        "新用户/CI 见 docs/ONBOARDING.zh-CN.md",
    )
    if fail_on_missing_api_key and not settings.mock:
        if not bool(str(settings.api_key or "").strip()):
            return 2
    return 0
