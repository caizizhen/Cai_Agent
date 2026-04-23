from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cai_agent import __version__
from cai_agent.config import Settings
from cai_agent.context import INSTRUCTION_FILE_NAMES
from cai_agent.models import ping_profile


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

    return {
        "cai_dir_exists": cai.is_dir(),
        "gateway_dir_exists": gw_dir.is_dir(),
        "telegram_map_exists": tg_map.is_file(),
        "telegram_map_readable": _map_readable(tg_map),
        "discord_map_exists": dc_map.is_file(),
        "discord_map_readable": _map_readable(dc_map),
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
        "profiles_count": len(settings.profiles),
        "subagent_profile_id": settings.subagent_profile_id or None,
        "planner_profile_id": settings.planner_profile_id or None,
        "temperature": settings.temperature,
        "llm_timeout_sec": settings.llm_timeout_sec,
        "http_trust_env": settings.http_trust_env,
        "mock": settings.mock,
        "max_iterations": settings.max_iterations,
        "command_timeout_sec": settings.command_timeout_sec,
        "project_context": settings.project_context,
        "git_context": settings.git_context,
        "mcp_enabled": settings.mcp_enabled,
        "mcp_base_url": settings.mcp_base_url or None,
        "mcp_timeout_sec": settings.mcp_timeout_sec,
        "fetch_url_enabled": settings.fetch_url_enabled,
        "fetch_url_unrestricted": settings.fetch_url_unrestricted,
        "fetch_url_allowed_hosts_count": len(settings.fetch_url_allowed_hosts),
        "permission_fetch_url": settings.permission_fetch_url,
        "profile_ping_skipped": not ping_on,
        "profile_pings": pings,
        "instruction_files": instruction_files,
        "workspace_is_dir": root.is_dir(),
        "git_inside_work_tree": inside,
        "cai_dir_health": build_doctor_cai_dir_health(root),
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
    print("最大轮次:", settings.max_iterations)
    print("命令超时:", settings.command_timeout_sec, "s")
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
        print(f" | {mode} | 权限={settings.permission_fetch_url}")
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
    hf = cai_health["hooks_file"]
    hv = cai_health["hooks_file_valid"]
    if hf:
        print(f"  hooks.json={hf} valid={hv}")
    else:
        print("  hooks.json=（未找到，可选）")
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
