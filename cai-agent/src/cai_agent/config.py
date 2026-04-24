from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cai_agent.model_routing import (
    ModelRoutingRule,
    ModelsProfileRoute,
    model_routing_enabled as _model_routing_enabled_from_toml,
    parse_model_routing_section,
    parse_models_profile_routes,
)
from cai_agent.profiles import (
    KNOWN_PROVIDERS,
    Profile,
    ProfilesError,
    normalize_openai_chat_base_url,
    parse_models_section,
    pick_active,
    project_base_url,
    synthesize_default_profile,
)


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.lower() in ("1", "true", "yes", "on")


def _normalize_base_url(base: str) -> str:
    return normalize_openai_chat_base_url(base)


def _user_config_candidates() -> list[Path]:
    """返回用户级全局配置候选路径（按优先级从高到低）。

    类似 git 的 ``~/.gitconfig``：从 cwd / workspace 找不到项目级 TOML 时，
    用这里列出的**用户目录**路径作为兜底，解决「从任意目录启动 ui，想读
    固定那份个人配置」的诉求。

    Windows / macOS / Linux 覆盖：

    - ``%APPDATA%\\cai-agent\\cai-agent.toml``（Windows 专属，最先查）
    - ``~/.config/cai-agent/cai-agent.toml``（XDG 风格；受 ``XDG_CONFIG_HOME``）
    - ``~/.cai-agent.toml``（点文件，最兼容）
    - ``~/cai-agent.toml``（非隐藏，方便 Windows 用户 Explorer 里直接看）
    """
    out: list[Path] = []

    appdata = os.getenv("APPDATA")
    if isinstance(appdata, str) and appdata.strip():
        try:
            out.append(Path(appdata).expanduser().resolve() / "cai-agent" / "cai-agent.toml")
        except OSError:
            pass

    xdg = os.getenv("XDG_CONFIG_HOME")
    if isinstance(xdg, str) and xdg.strip():
        try:
            out.append(Path(xdg).expanduser().resolve() / "cai-agent" / "cai-agent.toml")
        except OSError:
            pass
    else:
        try:
            out.append(Path.home().resolve() / ".config" / "cai-agent" / "cai-agent.toml")
        except (OSError, RuntimeError):
            pass

    try:
        home = Path.home().resolve()
        out.append(home / ".cai-agent.toml")
        out.append(home / "cai-agent.toml")
    except (OSError, RuntimeError):
        pass

    # 去重但保序
    seen: set[str] = set()
    uniq: list[Path] = []
    for p in out:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


def _resolve_config_file(
    explicit: str | None,
    *,
    workspace_hint: str | None = None,
) -> Path | None:
    """返回要加载的 TOML 路径；显式路径缺失时抛错；未配置则自动查找。

    查找顺序：``CAI_CONFIG`` → 当前目录 ``cai-agent.toml`` / ``.cai-agent.toml`` →
    沿父目录向上最多 12 级（便于「配置在仓库根、在子目录里跑 ``ui``」）→
    若仍未找到：再沿 ``CAI_WORKSPACE`` 环境变量目录及其父目录查找 →
    沿 ``workspace_hint``（通常为 CLI ``--workspace``）同样查找 →
    最后尝试用户级全局配置（见 :func:`_user_config_candidates`）。

    解决从任意目录启动（尤其跨盘符）时读不到项目根 ``cai-agent.toml``、
    导致 ``context_window`` 等回落到内置默认 8192 的问题。
    """
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if not p.is_file():
            msg = (
                f"配置文件不存在: {p}\n"
                "提示: 检查路径与文件名；或在项目根执行 `cai-agent init`；"
                "也可设置环境变量 CAI_CONFIG 指向有效 TOML。"
            )
            raise FileNotFoundError(msg)
        return p
    env_path = os.getenv("CAI_CONFIG")
    if env_path:
        p = Path(env_path).expanduser().resolve()
        if not p.is_file():
            msg = (
                f"CAI_CONFIG 指向的文件不存在: {p}\n"
                "提示: 修正 CAI_CONFIG 路径，或取消该变量以使用当前目录及上级目录中的 cai-agent.toml。"
            )
            raise FileNotFoundError(msg)
        return p

    def _pick_in(dir_path: Path) -> Path | None:
        for name in ("cai-agent.toml", ".cai-agent.toml"):
            cand = (dir_path / name).resolve()
            if cand.is_file():
                return cand
        return None

    def _walk_from(anchor: Path) -> Path | None:
        hit = _pick_in(anchor)
        if hit is not None:
            return hit
        for parent in list(anchor.parents)[:12]:
            hit = _pick_in(parent)
            if hit is not None:
                return hit
        return None

    here = Path.cwd().resolve()
    hit = _walk_from(here)
    if hit is not None:
        return hit

    seen_roots: set[str] = {str(here)}

    def _try_extra_root(raw: str | None) -> Path | None:
        if not isinstance(raw, str) or not raw.strip():
            return None
        try:
            root = Path(raw).expanduser().resolve()
        except OSError:
            return None
        if not root.is_dir():
            return None
        key = str(root)
        if key in seen_roots:
            return None
        seen_roots.add(key)
        return _walk_from(root)

    hit = _try_extra_root(os.getenv("CAI_WORKSPACE"))
    if hit is not None:
        return hit
    hit = _try_extra_root(workspace_hint)
    if hit is not None:
        return hit

    for cand in _user_config_candidates():
        try:
            if cand.is_file():
                return cand
        except OSError:
            continue
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
    # 单次 chat_completion 的 HTTP 尝试总次数（含首次）；[llm].max_http_retries，CAI_LLM_MAX_RETRIES 优先。
    llm_max_http_retries: int
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
    quality_gate_test_policy: str
    quality_gate_lint_policy: str
    quality_gate_typecheck: bool
    quality_gate_typecheck_policy: str
    quality_gate_typecheck_paths: tuple[str, ...]
    quality_gate_extra_commands: tuple[tuple[str, ...], ...]
    context_compact_after_iterations: int
    context_compact_min_messages: int
    context_compact_on_tool_error: bool
    context_compact_after_tool_calls: int
    security_scan_exclude_globs: tuple[str, ...]
    security_scan_rule_overrides: tuple[tuple[str, bool], ...]
    permission_write_file: str
    permission_run_command: str
    permission_fetch_url: str
    run_command_approval_mode: str
    run_command_high_risk_patterns: tuple[str, ...]
    fetch_url_enabled: bool
    fetch_url_unrestricted: bool
    fetch_url_allowed_hosts: tuple[str, ...]
    fetch_url_max_bytes: int
    fetch_url_timeout_sec: float
    fetch_url_max_redirects: int
    fetch_url_allow_private_resolved_ips: bool
    cost_budget_max_tokens: int
    hooks_profile: str
    hooks_disabled_ids: tuple[str, ...]
    hooks_timeout_sec: float
    # 模型 Profile（M1/M2）：所有已定义 profile；`active/subagent/planner` 是 id 字符串。
    # 当 TOML 未显式声明 [[models.profile]] 时，会从 [llm] 合成 id="default" 的单条 profile。
    profiles: tuple[Profile, ...]
    # True 表示 profiles 来自 TOML 的 [[models.profile]]；False 表示从 [llm] 合成。
    # 写回 TOML 时仅持久化真实 profile，避免落盘一个合成的 "default" 条目。
    profiles_explicit: bool
    active_profile_id: str
    subagent_profile_id: str | None
    planner_profile_id: str | None
    # [models.routing]：按 goal 与 role 覆盖 profile（见 model_routing.py）。
    model_routing_enabled: bool
    model_routing_rules: tuple[ModelRoutingRule, ...]
    # [[models.route]]：按任务子串 / prompt token 阈值切换 profile（H1-MP-03）。
    models_profile_routes: tuple[ModelsProfileRoute, ...]
    active_api_key_env: str | None
    anthropic_version: str
    anthropic_max_tokens: int
    # 当前 active profile 的上下文窗口（tokens）。UI 用来计算进度条百分比。
    # 优先级：active_profile.context_window > [llm].context_window > 内置默认 8192。
    context_window: int
    # 解析来源标签，仅用于 UI 诊断："profile" | "llm" | "env" | "default"
    context_window_source: str
    # 若由 TOML 解析则为该文件绝对路径，否则为 None
    config_loaded_from: str | None
    # [runtime]：命令执行后端（H1-RT）；工具层可读取并派发 run_command。
    runtime_backend: str
    runtime_docker_container: str
    runtime_docker_image: str
    runtime_docker_workdir: str
    runtime_docker_volume_mounts: tuple[str, ...]
    runtime_docker_exec_options: tuple[str, ...]
    runtime_docker_cpus: str | None
    runtime_docker_memory: str | None
    runtime_ssh_host: str
    runtime_ssh_user: str
    runtime_ssh_key_path: str | None
    runtime_ssh_strict_host_key: bool
    runtime_ssh_known_hosts_path: str | None
    runtime_ssh_connect_timeout_sec: float
    runtime_ssh_audit_log_path: str | None
    runtime_ssh_audit_label: str | None
    runtime_ssh_audit_include_command: bool
    runtime_modal_app_name: str
    runtime_modal_hibernate_idle_seconds: int | None
    runtime_singularity_sif_path: str
    runtime_singularity_bind_paths: tuple[str, ...]
    runtime_daytona_workspace: str
    # [memory.policy]：记忆治理与 recall 负样本审计（P0-MEM）
    memory_policy_max_entries_per_day: int
    memory_policy_default_ttl_days: int | None
    memory_policy_recall_negative_audit: bool
    # [skills.auto_extract]：任务后自动提炼（P0-SKEXT）
    skills_auto_extract_enabled: bool
    skills_auto_extract_mode: str
    skills_auto_extract_min_goal_chars: int
    skills_auto_improve_min_usage_count: int
    skills_auto_improve_min_days_since_last_improve: int

    @classmethod
    def from_env(
        cls,
        *,
        config_path: str | None = None,
        workspace_hint: str | None = None,
    ) -> Settings:
        """加载顺序：默认值 → TOML 文件 → 环境变量（环境变量优先）。"""
        return cls.from_sources(
            config_path=config_path,
            workspace_hint=workspace_hint,
        )

    @classmethod
    def from_sources(
        cls,
        *,
        config_path: str | None = None,
        workspace_hint: str | None = None,
    ) -> Settings:
        file_data: dict[str, Any] = {}
        resolved = _resolve_config_file(
            config_path,
            workspace_hint=workspace_hint,
        )
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

        rmr = llm.get("max_http_retries")
        if isinstance(rmr, bool):
            llm_max_http_retries_toml = 50
        elif isinstance(rmr, int) and not isinstance(rmr, bool):
            llm_max_http_retries_toml = int(rmr)
        elif isinstance(rmr, float) and rmr > 0:
            llm_max_http_retries_toml = int(rmr)
        elif isinstance(rmr, str) and rmr.strip().isdigit():
            llm_max_http_retries_toml = int(rmr.strip(), 10)
        else:
            llm_max_http_retries_toml = 50
        llm_max_http_retries_toml = max(1, min(100, llm_max_http_retries_toml))

        raw_llm_retries_env = os.getenv("CAI_LLM_MAX_RETRIES")
        if raw_llm_retries_env is not None and str(raw_llm_retries_env).strip():
            try:
                llm_max_http_retries = int(str(raw_llm_retries_env).strip(), 10)
            except ValueError:
                llm_max_http_retries = llm_max_http_retries_toml
        else:
            llm_max_http_retries = llm_max_http_retries_toml
        llm_max_http_retries = max(1, min(100, llm_max_http_retries))

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

        quality_gate_compile = bool(qg.get("compile", False))
        quality_gate_test = bool(qg.get("test", False))
        quality_gate_lint = bool(qg.get("lint", False))
        quality_gate_security_scan = bool(qg.get("security_scan", False))
        test_pol = str(qg.get("test_policy", "skip")).strip().lower()
        if test_pol not in ("skip", "fail_if_missing"):
            test_pol = "skip"
        quality_gate_test_policy = test_pol
        lint_pol = str(qg.get("lint_policy", "skip")).strip().lower()
        if lint_pol not in ("skip", "fail_if_missing"):
            lint_pol = "skip"
        quality_gate_lint_policy = lint_pol

        quality_gate_typecheck = bool(qg.get("typecheck", False))
        tcp = str(qg.get("typecheck_policy", "skip")).strip().lower()
        if tcp not in ("skip", "fail_if_missing"):
            tcp = "skip"
        quality_gate_typecheck_policy = tcp
        tpaths = qg.get("typecheck_paths")
        tplist: list[str] = []
        if isinstance(tpaths, list):
            tplist = [str(x).strip() for x in tpaths if str(x).strip()]
        elif isinstance(tpaths, str) and tpaths.strip():
            tplist = [tpaths.strip()]
        quality_gate_typecheck_paths = tuple(tplist)

        extra_cmds: list[tuple[str, ...]] = []
        raw_extra = qg.get("extra")
        if isinstance(raw_extra, list):
            for it in raw_extra:
                if not isinstance(it, dict):
                    continue
                av = it.get("argv")
                if isinstance(av, list) and av and all(isinstance(x, str) for x in av):
                    tup = tuple(str(x) for x in av)
                    if tup:
                        extra_cmds.append(tup)
        quality_gate_extra_commands = tuple(extra_cmds)

        ctx = _section(file_data, "context")
        cic = ctx.get("compact_after_iterations", 0)
        if isinstance(cic, bool):
            context_compact_after_iterations = int(cic)
        elif isinstance(cic, int) and not isinstance(cic, bool):
            context_compact_after_iterations = max(0, int(cic))
        else:
            context_compact_after_iterations = 0
        cmm = ctx.get("compact_min_messages", 8)
        if isinstance(cmm, bool):
            context_compact_min_messages = int(cmm)
        elif isinstance(cmm, int) and not isinstance(cmm, bool):
            context_compact_min_messages = max(0, int(cmm))
        else:
            context_compact_min_messages = 8

        if os.getenv("CAI_CONTEXT_COMPACT_ON_TOOL_ERROR") is not None:
            context_compact_on_tool_error = _env_bool("CAI_CONTEXT_COMPACT_ON_TOOL_ERROR", True)
        else:
            raw_cote = ctx.get("compact_on_tool_error")
            if isinstance(raw_cote, bool):
                context_compact_on_tool_error = raw_cote
            else:
                context_compact_on_tool_error = True

        if os.getenv("CAI_CONTEXT_COMPACT_AFTER_TOOL_CALLS") is not None:
            context_compact_after_tool_calls = max(
                0,
                int(os.environ["CAI_CONTEXT_COMPACT_AFTER_TOOL_CALLS"]),
            )
        else:
            raw_catc = ctx.get("compact_after_tool_calls")
            if isinstance(raw_catc, int) and not isinstance(raw_catc, bool):
                context_compact_after_tool_calls = max(0, int(raw_catc))
            elif isinstance(raw_catc, float) and not isinstance(raw_catc, bool):
                context_compact_after_tool_calls = max(0, int(raw_catc))
            else:
                context_compact_after_tool_calls = 0

        sec_ex = sec.get("exclude_globs")
        if isinstance(sec_ex, list):
            security_scan_exclude_globs = tuple(str(x).strip() for x in sec_ex if str(x).strip())
        else:
            security_scan_exclude_globs = ()

        ro = sec.get("rule_overrides")
        pairs: list[tuple[str, bool]] = []
        if isinstance(ro, dict):
            for k, v in ro.items():
                key = str(k).strip()
                if not key:
                    continue
                if isinstance(v, bool):
                    pairs.append((key, v))
                elif isinstance(v, int):
                    pairs.append((key, bool(v)))
        security_scan_rule_overrides = tuple(sorted(pairs))

        perm = _section(file_data, "permissions")
        def _perm_mode(raw: object, default: str) -> str:
            s = str(raw or default).strip().lower()
            if s not in ("allow", "ask", "deny"):
                return default
            return s

        permission_write_file = _perm_mode(perm.get("write_file"), "allow")
        permission_run_command = _perm_mode(perm.get("run_command"), "allow")
        permission_fetch_url = _perm_mode(perm.get("fetch_url"), "allow")
        raw_rc_mode = str(perm.get("run_command_approval_mode", "block_high_risk")).strip().lower()
        if raw_rc_mode not in ("block_high_risk", "allow_all"):
            raw_rc_mode = "block_high_risk"
        run_command_approval_mode = raw_rc_mode
        raw_patterns = perm.get("run_command_high_risk_patterns")
        if isinstance(raw_patterns, list):
            run_command_high_risk_patterns = tuple(
                str(x).strip().lower() for x in raw_patterns if str(x).strip()
            )
        else:
            run_command_high_risk_patterns = ()

        fu = _section(file_data, "fetch_url")
        if os.getenv("CAI_FETCH_URL_ENABLED") is not None:
            fetch_url_enabled = _env_bool("CAI_FETCH_URL_ENABLED", False)
        else:
            raw_fu_en = fu.get("enabled")
            if isinstance(raw_fu_en, bool):
                fetch_url_enabled = raw_fu_en
            else:
                fetch_url_enabled = True

        if os.getenv("CAI_FETCH_URL_UNRESTRICTED") is not None:
            fetch_url_unrestricted = _env_bool("CAI_FETCH_URL_UNRESTRICTED", False)
        else:
            raw_fu_ur = fu.get("unrestricted")
            if isinstance(raw_fu_ur, bool):
                fetch_url_unrestricted = raw_fu_ur
            else:
                fetch_url_unrestricted = True

        raw_hosts_env = os.getenv("CAI_FETCH_URL_ALLOW_HOSTS")
        if raw_hosts_env is not None and raw_hosts_env.strip():
            fetch_url_allowed_hosts = tuple(
                x.strip().lower()
                for x in raw_hosts_env.split(",")
                if x.strip()
            )
        else:
            ah = fu.get("allow_hosts")
            if isinstance(ah, list):
                fetch_url_allowed_hosts = tuple(
                    str(x).strip().lower() for x in ah if str(x).strip()
                )
            else:
                fetch_url_allowed_hosts = ()

        if os.getenv("CAI_FETCH_URL_MAX_BYTES") is not None:
            fetch_url_max_bytes = max(1024, int(os.environ["CAI_FETCH_URL_MAX_BYTES"]))
        else:
            raw_mb = fu.get("max_bytes")
            if isinstance(raw_mb, int) and not isinstance(raw_mb, bool):
                fetch_url_max_bytes = max(1024, int(raw_mb))
            elif isinstance(raw_mb, float):
                fetch_url_max_bytes = max(1024, int(raw_mb))
            else:
                fetch_url_max_bytes = 500_000
        fetch_url_max_bytes = min(fetch_url_max_bytes, 5_000_000)

        if os.getenv("CAI_FETCH_URL_TIMEOUT_SEC") is not None:
            fetch_url_timeout_sec = float(os.environ["CAI_FETCH_URL_TIMEOUT_SEC"])
        else:
            raw_ft = fu.get("timeout_sec")
            if isinstance(raw_ft, int | float) and not isinstance(raw_ft, bool):
                fetch_url_timeout_sec = float(raw_ft)
            else:
                fetch_url_timeout_sec = 30.0
        fetch_url_timeout_sec = max(3.0, min(120.0, fetch_url_timeout_sec))

        if os.getenv("CAI_FETCH_URL_MAX_REDIRECTS") is not None:
            fetch_url_max_redirects = int(os.environ["CAI_FETCH_URL_MAX_REDIRECTS"])
        else:
            raw_mr = fu.get("max_redirects")
            if isinstance(raw_mr, int) and not isinstance(raw_mr, bool):
                fetch_url_max_redirects = int(raw_mr)
            elif isinstance(raw_mr, float) and not isinstance(raw_mr, bool):
                fetch_url_max_redirects = int(raw_mr)
            else:
                fetch_url_max_redirects = 20
        fetch_url_max_redirects = max(1, min(50, int(fetch_url_max_redirects)))

        if os.getenv("CAI_FETCH_URL_ALLOW_PRIVATE_RESOLVED_IPS") is not None:
            fetch_url_allow_private_resolved_ips = _env_bool(
                "CAI_FETCH_URL_ALLOW_PRIVATE_RESOLVED_IPS", False
            )
        else:
            raw_apri = fu.get("allow_private_resolved_ips")
            if isinstance(raw_apri, bool):
                fetch_url_allow_private_resolved_ips = raw_apri
            else:
                fetch_url_allow_private_resolved_ips = False

        cost_sec = _section(file_data, "cost")
        raw_max = cost_sec.get("budget_max_tokens")
        if isinstance(raw_max, int) and not isinstance(raw_max, bool):
            cost_budget_max_tokens = max(0, int(raw_max))
        elif isinstance(raw_max, float):
            cost_budget_max_tokens = max(0, int(raw_max))
        else:
            cost_budget_max_tokens = 50_000

        hooks_sec = _section(file_data, "hooks")
        raw_prof = os.getenv("CAI_HOOKS_PROFILE")
        if raw_prof is not None and raw_prof.strip():
            hooks_profile = str(raw_prof).strip().lower()
        else:
            hooks_profile = str(hooks_sec.get("profile", "standard")).strip().lower()
        if hooks_profile not in ("minimal", "standard", "strict"):
            hooks_profile = "standard"
        disabled_ids: list[str] = []
        raw_dis_env = os.getenv("CAI_HOOKS_DISABLED")
        if raw_dis_env is not None and raw_dis_env.strip():
            disabled_ids = [
                x.strip() for x in raw_dis_env.split(",") if x.strip()
            ]
        else:
            dis = hooks_sec.get("disabled")
            if isinstance(dis, list):
                disabled_ids = [str(x).strip() for x in dis if str(x).strip()]
        raw_ht = hooks_sec.get("timeout_sec")
        if os.getenv("CAI_HOOKS_TIMEOUT_SEC") is not None:
            hooks_timeout_sec = float(os.environ["CAI_HOOKS_TIMEOUT_SEC"])
        elif isinstance(raw_ht, int | float) and not isinstance(raw_ht, bool):
            hooks_timeout_sec = float(raw_ht)
        else:
            hooks_timeout_sec = float(command_timeout_sec)
        hooks_timeout_sec = max(1.0, min(600.0, hooks_timeout_sec))

        runtime_sec = _section(file_data, "runtime")
        runtime_docker = _section(runtime_sec, "docker")
        runtime_ssh = _section(runtime_sec, "ssh")
        runtime_modal = _section(runtime_sec, "modal")
        runtime_singularity = _section(runtime_sec, "singularity")
        runtime_daytona = _section(runtime_sec, "daytona")
        runtime_backend = str(runtime_sec.get("backend") or "local").strip().lower() or "local"
        if os.getenv("CAI_RUNTIME_BACKEND") is not None and str(os.getenv("CAI_RUNTIME_BACKEND") or "").strip():
            runtime_backend = str(os.environ["CAI_RUNTIME_BACKEND"]).strip().lower() or "local"
        runtime_docker_container = str(
            runtime_docker.get("container_name") or runtime_docker.get("container") or "",
        ).strip()
        runtime_docker_image = str(runtime_docker.get("image") or "").strip()
        runtime_docker_workdir = str(runtime_docker.get("workdir") or "/workspace").strip() or "/workspace"
        raw_dvm = runtime_docker.get("volume_mounts")
        if isinstance(raw_dvm, list):
            runtime_docker_volume_mounts = tuple(
                str(x).strip() for x in raw_dvm if isinstance(x, str | int | float) and str(x).strip()
            )
        else:
            runtime_docker_volume_mounts = ()
        raw_deo = runtime_docker.get("exec_options")
        if isinstance(raw_deo, list):
            runtime_docker_exec_options = tuple(
                str(x).strip() for x in raw_deo if isinstance(x, str | int | float) and str(x).strip()
            )
        else:
            runtime_docker_exec_options = ()
        _cpus = runtime_docker.get("cpus")
        runtime_docker_cpus = str(_cpus).strip() if _cpus is not None and str(_cpus).strip() else None
        _mem = runtime_docker.get("memory")
        runtime_docker_memory = str(_mem).strip() if _mem is not None and str(_mem).strip() else None
        runtime_ssh_host = str(runtime_ssh.get("host") or "").strip()
        runtime_ssh_user = str(runtime_ssh.get("user") or "").strip()
        _kp = runtime_ssh.get("key_path")
        runtime_ssh_key_path = (
            str(_kp).strip() if isinstance(_kp, str) and str(_kp).strip() else None
        )
        raw_shk = runtime_ssh.get("strict_host_key_checking")
        if isinstance(raw_shk, bool):
            runtime_ssh_strict_host_key = raw_shk
        else:
            runtime_ssh_strict_host_key = True
        _khp = runtime_ssh.get("known_hosts_path")
        runtime_ssh_known_hosts_path = (
            str(_khp).strip() if isinstance(_khp, str) and str(_khp).strip() else None
        )
        raw_ct = runtime_ssh.get("connect_timeout_sec")
        if isinstance(raw_ct, int | float) and not isinstance(raw_ct, bool):
            runtime_ssh_connect_timeout_sec = float(max(1.0, min(120.0, float(raw_ct))))
        else:
            runtime_ssh_connect_timeout_sec = 15.0
        _audit_path = runtime_ssh.get("audit_log_path")
        runtime_ssh_audit_log_path = (
            str(_audit_path).strip() if isinstance(_audit_path, str) and str(_audit_path).strip() else None
        )
        _audit_label = runtime_ssh.get("audit_label")
        runtime_ssh_audit_label = (
            str(_audit_label).strip() if isinstance(_audit_label, str) and str(_audit_label).strip() else None
        )
        runtime_ssh_audit_include_command = bool(runtime_ssh.get("audit_include_command", False) is True)
        runtime_modal_app_name = str(runtime_modal.get("app_name") or "").strip()
        raw_hib = runtime_modal.get("hibernate_idle_seconds")
        if isinstance(raw_hib, int) and not isinstance(raw_hib, bool) and raw_hib > 0:
            runtime_modal_hibernate_idle_seconds = int(raw_hib)
        elif isinstance(raw_hib, float) and raw_hib > 0:
            runtime_modal_hibernate_idle_seconds = int(raw_hib)
        else:
            runtime_modal_hibernate_idle_seconds = None
        runtime_singularity_sif_path = str(
            runtime_singularity.get("sif_path") or runtime_singularity.get("image") or "",
        ).strip()
        raw_binds = runtime_singularity.get("bind_paths")
        if isinstance(raw_binds, list):
            runtime_singularity_bind_paths = tuple(
                str(x).strip() for x in raw_binds if isinstance(x, str) and str(x).strip()
            )
        else:
            runtime_singularity_bind_paths = ()
        runtime_daytona_workspace = str(
            runtime_daytona.get("workspace") or runtime_daytona.get("workspace_id") or "",
        ).strip()

        memory_sec = _section(file_data, "memory")
        policy_sec = _section(memory_sec, "policy")
        raw_mepd = policy_sec.get("max_entries_per_day")
        if isinstance(raw_mepd, int) and not isinstance(raw_mepd, bool) and raw_mepd > 0:
            memory_policy_max_entries_per_day = min(1_000_000, int(raw_mepd))
        else:
            memory_policy_max_entries_per_day = 10_000
        raw_ttl = policy_sec.get("default_ttl_days")
        if isinstance(raw_ttl, int) and not isinstance(raw_ttl, bool) and raw_ttl > 0:
            memory_policy_default_ttl_days = int(raw_ttl)
        elif isinstance(raw_ttl, float) and raw_ttl > 0:
            memory_policy_default_ttl_days = int(raw_ttl)
        else:
            memory_policy_default_ttl_days = None
        raw_rna = policy_sec.get("recall_negative_audit")
        if isinstance(raw_rna, bool):
            memory_policy_recall_negative_audit = raw_rna
        else:
            memory_policy_recall_negative_audit = True

        skills_sec = _section(file_data, "skills")
        ae_sec = _section(skills_sec, "auto_extract")
        if os.getenv("CAI_SKILLS_AUTO_EXTRACT_ENABLED") is not None:
            skills_auto_extract_enabled = _env_bool("CAI_SKILLS_AUTO_EXTRACT_ENABLED", False)
        else:
            raw_en = ae_sec.get("enabled")
            if isinstance(raw_en, bool):
                skills_auto_extract_enabled = raw_en
            else:
                skills_auto_extract_enabled = False
        mode_env = os.getenv("CAI_SKILLS_AUTO_EXTRACT_MODE")
        if mode_env is not None and str(mode_env).strip():
            skills_auto_extract_mode = str(mode_env).strip().lower()
        else:
            raw_mode = ae_sec.get("mode")
            skills_auto_extract_mode = str(raw_mode or "template").strip().lower()
        if skills_auto_extract_mode not in ("template", "llm", "auto"):
            skills_auto_extract_mode = "template"
        if os.getenv("CAI_SKILLS_AUTO_EXTRACT_MIN_GOAL_CHARS") is not None:
            skills_auto_extract_min_goal_chars = max(
                1,
                int(os.environ["CAI_SKILLS_AUTO_EXTRACT_MIN_GOAL_CHARS"]),
            )
        else:
            raw_mgc = ae_sec.get("min_goal_chars")
            if isinstance(raw_mgc, int) and not isinstance(raw_mgc, bool):
                skills_auto_extract_min_goal_chars = max(1, int(raw_mgc))
            elif isinstance(raw_mgc, float):
                skills_auto_extract_min_goal_chars = max(1, int(raw_mgc))
            else:
                skills_auto_extract_min_goal_chars = 8

        aim_sec = _section(skills_sec, "auto_improve")
        raw_muc = aim_sec.get("min_usage_count")
        if isinstance(raw_muc, int) and not isinstance(raw_muc, bool):
            skills_auto_improve_min_usage_count = max(1, int(raw_muc))
        else:
            skills_auto_improve_min_usage_count = 1
        raw_mdays = aim_sec.get("min_days_since_last_improve")
        if isinstance(raw_mdays, int) and not isinstance(raw_mdays, bool):
            skills_auto_improve_min_days_since_last_improve = max(0, int(raw_mdays))
        else:
            skills_auto_improve_min_days_since_last_improve = 0

        config_loaded_from = str(resolved) if resolved is not None else None

        # ---- Model Profiles（M1/M2） -------------------------------------------------
        # 语义：显式 [[models.profile]] 优先；否则从 [llm] 合成一个 id="default" 的隐式 profile。
        # 激活顺序：CAI_ACTIVE_MODEL env > [models].active > 列表首个。
        profiles_parsed, active_id, subagent_id, planner_id = parse_models_section(file_data)
        profiles_explicit = bool(profiles_parsed)
        if profiles_parsed:
            all_profiles: tuple[Profile, ...] = profiles_parsed
        else:
            synth = synthesize_default_profile(
                provider=provider,
                base_url=base_url,
                model=model,
                api_key=api_key,
                temperature=temperature,
                timeout_sec=llm_timeout_sec,
            )
            all_profiles = (synth,)
            active_id = active_id or "default"

        env_active = os.getenv("CAI_ACTIVE_MODEL")
        env_active = env_active.strip() if isinstance(env_active, str) and env_active.strip() else None
        active_profile = pick_active(all_profiles, active_id, env_override=env_active)
        active_profile_id = active_profile.id

        # 有显式 profile 时：active profile 为权威，覆盖旧字段。
        if profiles_parsed:
            provider = active_profile.provider
            base_url = project_base_url(active_profile)
            model = active_profile.model
            temperature = max(0.0, min(2.0, float(active_profile.temperature)))
            llm_timeout_sec = max(5.0, min(3600.0, float(active_profile.timeout_sec)))
            resolved_key = active_profile.resolve_api_key()
            if active_profile.api_key_env:
                # env 模式：未设置时保留空字符串，由 doctor / 运行期给出可读错误；
                # 绝不回落到 [llm] 以免用户误以为已认证。
                api_key = resolved_key
            else:
                api_key = resolved_key or api_key or ""

        active_api_key_env = active_profile.api_key_env

        anthropic_version = (
            active_profile.anthropic_version
            if active_profile.provider == "anthropic" and active_profile.anthropic_version
            else "2023-06-01"
        )
        anthropic_max_tokens = int(active_profile.max_tokens or 4096)

        llm_context_window_raw = llm.get("context_window")
        llm_context_window: int | None = None
        if isinstance(llm_context_window_raw, bool):
            llm_context_window = None
        elif isinstance(llm_context_window_raw, int) and llm_context_window_raw > 0:
            llm_context_window = int(llm_context_window_raw)
        elif isinstance(llm_context_window_raw, float) and llm_context_window_raw > 0:
            llm_context_window = int(llm_context_window_raw)
        elif isinstance(llm_context_window_raw, str):
            raw_s = llm_context_window_raw.strip()
            if raw_s.isdigit() and int(raw_s) > 0:
                llm_context_window = int(raw_s)
        llm_context_window_from_toml = llm_context_window is not None
        env_ctx = os.getenv("CAI_CONTEXT_WINDOW")
        env_ctx_applied = False
        if isinstance(env_ctx, str) and env_ctx.strip().isdigit():
            llm_context_window = int(env_ctx.strip())
            env_ctx_applied = True
        profile_ctx = (
            active_profile.context_window
            if active_profile and active_profile.context_window
            else 0
        )
        if profile_ctx:
            context_window = int(profile_ctx)
            context_window_source = "profile"
        elif env_ctx_applied:
            context_window = int(llm_context_window or 8192)
            context_window_source = "env"
        elif llm_context_window_from_toml:
            context_window = int(llm_context_window or 8192)
            context_window_source = "llm"
        else:
            context_window = 8192
            context_window_source = "default"
        context_window = max(256, min(10_000_000, context_window))

        # 校正 subagent/planner：若 profile 不存在于集合，降级为 None 并允许启动。
        def _validate_route(pid: str | None) -> str | None:
            if not pid:
                return None
            if any(p.id == pid for p in all_profiles):
                return pid
            return None
        subagent_profile_id = _validate_route(subagent_id)
        planner_profile_id = _validate_route(planner_id)

        model_routing_rules = parse_model_routing_section(file_data)
        routing_on = _model_routing_enabled_from_toml(file_data)
        models_profile_routes = parse_models_profile_routes(file_data)

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
            llm_max_http_retries=llm_max_http_retries,
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
            quality_gate_test_policy=quality_gate_test_policy,
            quality_gate_lint_policy=quality_gate_lint_policy,
            quality_gate_typecheck=quality_gate_typecheck,
            quality_gate_typecheck_policy=quality_gate_typecheck_policy,
            quality_gate_typecheck_paths=quality_gate_typecheck_paths,
            quality_gate_extra_commands=quality_gate_extra_commands,
            context_compact_after_iterations=context_compact_after_iterations,
            context_compact_min_messages=context_compact_min_messages,
            context_compact_on_tool_error=context_compact_on_tool_error,
            context_compact_after_tool_calls=context_compact_after_tool_calls,
            security_scan_exclude_globs=security_scan_exclude_globs,
            security_scan_rule_overrides=security_scan_rule_overrides,
            permission_write_file=permission_write_file,
            permission_run_command=permission_run_command,
            permission_fetch_url=permission_fetch_url,
            run_command_approval_mode=run_command_approval_mode,
            run_command_high_risk_patterns=run_command_high_risk_patterns,
            fetch_url_enabled=fetch_url_enabled,
            fetch_url_unrestricted=fetch_url_unrestricted,
            fetch_url_allowed_hosts=fetch_url_allowed_hosts,
            fetch_url_max_bytes=fetch_url_max_bytes,
            fetch_url_timeout_sec=fetch_url_timeout_sec,
            fetch_url_max_redirects=fetch_url_max_redirects,
            fetch_url_allow_private_resolved_ips=fetch_url_allow_private_resolved_ips,
            cost_budget_max_tokens=cost_budget_max_tokens,
            hooks_profile=hooks_profile,
            hooks_disabled_ids=tuple(disabled_ids),
            hooks_timeout_sec=hooks_timeout_sec,
            profiles=all_profiles,
            profiles_explicit=profiles_explicit,
            active_profile_id=active_profile_id,
            subagent_profile_id=subagent_profile_id,
            planner_profile_id=planner_profile_id,
            model_routing_enabled=routing_on,
            model_routing_rules=model_routing_rules,
            models_profile_routes=models_profile_routes,
            active_api_key_env=active_api_key_env,
            anthropic_version=anthropic_version,
            anthropic_max_tokens=anthropic_max_tokens,
            context_window=context_window,
            context_window_source=context_window_source,
            config_loaded_from=config_loaded_from,
            runtime_backend=runtime_backend,
            runtime_docker_container=runtime_docker_container,
            runtime_docker_image=runtime_docker_image,
            runtime_docker_workdir=runtime_docker_workdir,
            runtime_docker_volume_mounts=runtime_docker_volume_mounts,
            runtime_docker_exec_options=runtime_docker_exec_options,
            runtime_docker_cpus=runtime_docker_cpus,
            runtime_docker_memory=runtime_docker_memory,
            runtime_ssh_host=runtime_ssh_host,
            runtime_ssh_user=runtime_ssh_user,
            runtime_ssh_key_path=runtime_ssh_key_path,
            runtime_ssh_strict_host_key=runtime_ssh_strict_host_key,
            runtime_ssh_known_hosts_path=runtime_ssh_known_hosts_path,
            runtime_ssh_connect_timeout_sec=runtime_ssh_connect_timeout_sec,
            runtime_ssh_audit_log_path=runtime_ssh_audit_log_path,
            runtime_ssh_audit_label=runtime_ssh_audit_label,
            runtime_ssh_audit_include_command=runtime_ssh_audit_include_command,
            runtime_modal_app_name=runtime_modal_app_name,
            runtime_modal_hibernate_idle_seconds=runtime_modal_hibernate_idle_seconds,
            runtime_singularity_sif_path=runtime_singularity_sif_path,
            runtime_singularity_bind_paths=runtime_singularity_bind_paths,
            runtime_daytona_workspace=runtime_daytona_workspace,
            memory_policy_max_entries_per_day=memory_policy_max_entries_per_day,
            memory_policy_default_ttl_days=memory_policy_default_ttl_days,
            memory_policy_recall_negative_audit=memory_policy_recall_negative_audit,
            skills_auto_extract_enabled=skills_auto_extract_enabled,
            skills_auto_extract_mode=skills_auto_extract_mode,
            skills_auto_extract_min_goal_chars=skills_auto_extract_min_goal_chars,
            skills_auto_improve_min_usage_count=skills_auto_improve_min_usage_count,
            skills_auto_improve_min_days_since_last_improve=skills_auto_improve_min_days_since_last_improve,
        )
