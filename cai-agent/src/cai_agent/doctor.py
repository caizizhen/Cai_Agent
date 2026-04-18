from __future__ import annotations

import os
import subprocess
from pathlib import Path

from cai_agent import __version__
from cai_agent.config import Settings
from cai_agent.context import INSTRUCTION_FILE_NAMES
from cai_agent.models import ping_profile


def _mask_api_key(key: str) -> str:
    if not key:
        return "(空)"
    if len(key) <= 6:
        return "******"
    return f"{key[:3]}…{key[-2:]}（已打码）"


def run_doctor(settings: Settings) -> int:
    root = Path(settings.workspace).resolve()
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

    try:
        r = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            timeout=3.0,
            shell=False,
        )
        inside = r.returncode == 0 and (r.stdout or "").strip() == "true"
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        inside = False

    print("Git:     ", "在工作树内" if inside else "非 Git 目录或未安装 git")
    print()
    print("建议下一步:")
    print("  1) 若尚未生成配置: cai-agent init")
    print("  2) 编辑 cai-agent.toml 中 [llm] 或 [[models.profile]]（base_url / model / api_key_env）")
    print("  3) 试跑: cai-agent run \"用一句话描述当前工作区用途\"")
    print(
        "  4) 多模型: cai-agent models list；新用户/CI 见 docs/ONBOARDING.zh-CN.md",
    )
    return 0
