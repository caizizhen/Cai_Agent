from __future__ import annotations

import subprocess
from pathlib import Path

from cai_agent import __version__
from cai_agent.config import Settings
from cai_agent.context import INSTRUCTION_FILE_NAMES


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
    print("API Key: ", _mask_api_key(settings.api_key))
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
        print(
            f" | 白名单 {len(settings.fetch_url_allowed_hosts)} 项 | 权限={settings.permission_fetch_url}",
        )
    else:
        print()
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
    print("  2) 编辑 cai-agent.toml 中 [llm]（base_url / model / api_key）")
    print("  3) 试跑: cai-agent run \"用一句话描述当前工作区用途\"")
    print("  4) 新用户与 CI 说明见仓库 docs/ONBOARDING.zh-CN.md")
    return 0
