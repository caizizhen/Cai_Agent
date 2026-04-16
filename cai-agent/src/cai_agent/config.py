from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.lower() in ("1", "true", "yes", "on")


def _normalize_base_url(base: str) -> str:
    base = base.strip().rstrip("/")
    if not base.endswith("/v1"):
        return base + "/v1"
    return base


def _resolve_config_file(explicit: str | None) -> Path | None:
    """返回要加载的 TOML 路径；显式路径缺失时抛错；未配置则自动查找当前目录。"""
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if not p.is_file():
            msg = f"配置文件不存在: {p}"
            raise FileNotFoundError(msg)
        return p
    env_path = os.getenv("CAI_CONFIG")
    if env_path:
        p = Path(env_path).expanduser().resolve()
        if not p.is_file():
            msg = f"CAI_CONFIG 指向的文件不存在: {p}"
            raise FileNotFoundError(msg)
        return p
    for name in ("cai-agent.toml", ".cai-agent.toml"):
        p = (Path.cwd() / name).resolve()
        if p.is_file():
            return p
    return None


def _read_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def _section(data: dict[str, Any], key: str) -> dict[str, Any]:
    v = data.get(key)
    return v if isinstance(v, dict) else {}


def _optional_env_bool(name: str) -> bool | None:
    v = os.getenv(name)
    if v is None:
        return None
    return _env_bool(name)


@dataclass(frozen=True)
class Settings:
    provider: str
    workspace: str
    base_url: str
    model: str
    api_key: str
    http_trust_env: bool
    max_iterations: int
    command_timeout_sec: float
    mock: bool
    temperature: float
    llm_timeout_sec: float
    project_context: bool
    git_context: bool
    mcp_enabled: bool
    mcp_base_url: str | None
    mcp_api_key: str | None
    mcp_timeout_sec: float
    quality_gate_compile: bool
    quality_gate_test: bool
    quality_gate_lint: bool
    quality_gate_security_scan: bool
    security_scan_exclude_globs: tuple[str, ...]
    # 若由 TOML 解析则为该文件绝对路径，否则为 None
    config_loaded_from: str | None

    @classmethod
    def from_env(cls, *, config_path: str | None = None) -> Settings:
        """加载顺序：默认值 → TOML 文件 → 环境变量（环境变量优先）。"""
        return cls.from_sources(config_path=config_path)

    @classmethod
    def from_sources(cls, *, config_path: str | None = None) -> Settings:
        file_data: dict[str, Any] = {}
        resolved = _resolve_config_file(config_path)
        if resolved is not None:
            file_data = _read_toml(resolved)

        llm = _section(file_data, "llm")
        agent = _section(file_data, "agent")
        copilot = _section(file_data, "copilot")
        mcp = _section(file_data, "mcp")

        def _str_env(name: str, file_key: tuple[str, str], default: str) -> str:
            if os.getenv(name) is not None:
                return os.environ[name]
            sec, key = file_key
            raw = (llm if sec == "llm" else agent).get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
            return default

        def _bool_env(name: str, file_key: tuple[str, str], default: bool) -> bool:
            if os.getenv(name) is not None:
                return _env_bool(name)
            sec, key = file_key
            raw = (llm if sec == "llm" else agent).get(key)
            if isinstance(raw, bool):
                return raw
            return default

        def _int_env(name: str, file_key: tuple[str, str], default: int) -> int:
            if os.getenv(name) is not None:
                return int(os.environ[name])
            sec, key = file_key
            raw = (llm if sec == "llm" else agent).get(key)
            if isinstance(raw, bool):
                return int(raw)
            if isinstance(raw, int):
                return raw
            return default

        def _float_env(name: str, file_key: tuple[str, str], default: float) -> float:
            if os.getenv(name) is not None:
                return float(os.environ[name])
            sec, key = file_key
            raw = (llm if sec == "llm" else agent).get(key)
            if isinstance(raw, bool):
                return float(int(raw))
            if isinstance(raw, int | float):
                return float(raw)
            return default

        workspace_raw = os.getenv("CAI_WORKSPACE")
        if workspace_raw is not None and workspace_raw.strip():
            workspace = os.path.abspath(workspace_raw.strip())
        else:
            w_file = agent.get("workspace")
            if isinstance(w_file, str) and w_file.strip():
                workspace = os.path.abspath(w_file.strip())
            else:
                workspace = os.path.abspath(os.getcwd())

        provider = _str_env("LM_PROVIDER", ("llm", "provider"), "openai_compatible").lower()
        if provider not in ("openai_compatible", "copilot"):
            provider = "openai_compatible"

        def _str_optional(name: str, source: dict[str, Any], key: str) -> str | None:
            ev = os.getenv(name)
            if ev is not None and ev.strip():
                return ev.strip()
            raw = source.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
            return None

        copilot_base = _str_optional("COPILOT_BASE_URL", copilot, "base_url")
        copilot_model = _str_optional("COPILOT_MODEL", copilot, "model")
        copilot_key = _str_optional("COPILOT_API_KEY", copilot, "api_key")
        mcp_base_url = _str_optional("MCP_BASE_URL", mcp, "base_url")
        mcp_api_key = _str_optional("MCP_API_KEY", mcp, "api_key")

        base = _str_env(
            "LM_BASE_URL",
            ("llm", "base_url"),
            "http://localhost:1234/v1",
        )
        model = _str_env("LM_MODEL", ("llm", "model"), "google/gemma-4-31b")
        api_key = _str_env("LM_API_KEY", ("llm", "api_key"), "lm-studio")
        if provider == "copilot":
            # Copilot 建议通过本地/自托管 OpenAI 兼容代理接入。
            base = copilot_base or base or "http://localhost:4141/v1"
            model = copilot_model or model
            api_key = copilot_key or api_key
        base_url = _normalize_base_url(base)

        http_trust_env = _bool_env("LM_HTTP_TRUST_ENV", ("llm", "http_trust_env"), False)
        max_iterations = _int_env("CAI_MAX_ITER", ("agent", "max_iterations"), 16)
        command_timeout_sec = _float_env(
            "CAI_CMD_TIMEOUT",
            ("agent", "command_timeout_sec"),
            120.0,
        )
        mock = _bool_env("CAI_MOCK", ("agent", "mock"), False)

        temperature = _float_env("LM_TEMPERATURE", ("llm", "temperature"), 0.2)
        temperature = max(0.0, min(2.0, temperature))

        llm_timeout_sec = _float_env("LM_TIMEOUT", ("llm", "timeout_sec"), 120.0)
        llm_timeout_sec = max(5.0, min(3600.0, llm_timeout_sec))

        pc = _optional_env_bool("CAI_PROJECT_CONTEXT")
        if pc is not None:
            project_context = pc
        else:
            raw_pc = agent.get("project_context")
            project_context = raw_pc if isinstance(raw_pc, bool) else True

        gc = _optional_env_bool("CAI_GIT_CONTEXT")
        if gc is not None:
            git_context = gc
        else:
            raw_gc = agent.get("git_context")
            git_context = raw_gc if isinstance(raw_gc, bool) else True

        mcp_enabled = _bool_env("MCP_ENABLED", ("agent", "mcp_enabled"), False)
        raw_to = os.getenv("MCP_TIMEOUT")
        if raw_to is not None:
            mcp_timeout_sec = float(raw_to)
        else:
            raw = mcp.get("timeout_sec")
            if isinstance(raw, int | float) and not isinstance(raw, bool):
                mcp_timeout_sec = float(raw)
            else:
                mcp_timeout_sec = 20.0
        mcp_timeout_sec = max(3.0, min(300.0, mcp_timeout_sec))
        qg = _section(file_data, "quality_gate")
        sec = _section(file_data, "security_scan")

        quality_gate_compile = bool(qg.get("compile", True))
        quality_gate_test = bool(qg.get("test", True))
        quality_gate_lint = bool(qg.get("lint", False))
        quality_gate_security_scan = bool(qg.get("security_scan", False))
        sec_ex = sec.get("exclude_globs")
        if isinstance(sec_ex, list):
            security_scan_exclude_globs = tuple(str(x).strip() for x in sec_ex if str(x).strip())
        else:
            security_scan_exclude_globs = ()

        config_loaded_from = str(resolved) if resolved is not None else None

        return cls(
            provider=provider,
            workspace=workspace,
            base_url=base_url,
            model=model,
            api_key=api_key,
            http_trust_env=http_trust_env,
            max_iterations=max_iterations,
            command_timeout_sec=command_timeout_sec,
            mock=mock,
            temperature=temperature,
            llm_timeout_sec=llm_timeout_sec,
            project_context=project_context,
            git_context=git_context,
            mcp_enabled=mcp_enabled,
            mcp_base_url=mcp_base_url,
            mcp_api_key=mcp_api_key,
            mcp_timeout_sec=mcp_timeout_sec,
            quality_gate_compile=quality_gate_compile,
            quality_gate_test=quality_gate_test,
            quality_gate_lint=quality_gate_lint,
            quality_gate_security_scan=quality_gate_security_scan,
            security_scan_exclude_globs=security_scan_exclude_globs,
            config_loaded_from=config_loaded_from,
        )
