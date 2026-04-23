"""Provider 调度工厂（M11 骨架）。

三个入口：

1. :func:`resolve_provider` —— 把 ``settings.active_profile_provider``（优先）
   或 ``settings.provider`` 规范化为 canonical key（``anthropic / openai /
   openai_compatible`` 等）。``claude*`` 系列别名归并为 ``anthropic``；未知
   值回退 ``openai_compatible``。
2. :func:`chat_completion` —— 纯派发：按 :func:`resolve_provider` 的返回值，
   交给 ``_openai_adapter.chat_completion`` 或 ``_anthropic_adapter.chat_completion``。
3. :func:`chat_completion_by_role` —— 组合：按 ``active / subagent / planner``
   选 profile（可选 ``[models.routing]`` 用首条 ``user`` 消息覆盖），再用
   :func:`dataclasses.replace` 把 settings 投影到该 profile，最后派发适配器。
   graph.py / workflow.py 使用此入口。

测试通过重绑定 ``_openai_adapter.chat_completion`` / ``_anthropic_adapter.chat_completion``
来 stub 底层 HTTP，避免实网调用。
"""
from __future__ import annotations

import contextvars
from dataclasses import replace
from typing import Any, Callable

from cai_agent import llm as _openai_adapter
from cai_agent import llm_anthropic as _anthropic_adapter
from cai_agent.llm import get_last_usage, get_usage_counters
from cai_agent.model_routing import (
    first_matching_profile_route,
    first_matching_routing_rule,
    routing_goal_from_messages,
)
from cai_agent.profiles import Profile, project_base_url


ChatFn = Callable[[Any, list[dict[str, Any]]], str]

_profile_route_decision: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "profile_route_decision",
    default=None,
)


def peek_last_profile_route_decision() -> dict[str, Any] | None:
    """最近一次 :func:`resolve_effective_profile_for_llm` 的 ``[[models.route]]`` 命中（若有）。"""
    return _profile_route_decision.get()


def _set_profile_route_decision(doc: dict[str, Any] | None) -> None:
    _profile_route_decision.set(doc)


def resolve_provider(settings: Any) -> str:
    """把 settings.provider（或 active_profile_provider）映射为 canonical 值。

    - 优先读 ``active_profile_provider``（主循环已选中某 profile 后用它通告 provider）；
    - 空值 / 未知值 → ``openai_compatible``；
    - ``anthropic`` / ``claude`` / ``claude-*`` → ``anthropic``；
    - ``openai / openai_compatible / azure_openai / copilot / ollama / lmstudio / vllm`` 透传。
    """
    val = (
        getattr(settings, "active_profile_provider", None)
        or getattr(settings, "provider", None)
    )
    s = str(val or "").strip().lower()
    if not s:
        return "openai_compatible"
    if s == "anthropic" or s == "claude" or s.startswith("claude-"):
        return "anthropic"
    if s in {
        "openai",
        "openai_compatible",
        "azure_openai",
        "copilot",
        "ollama",
        "lmstudio",
        "vllm",
    }:
        return s
    return "openai_compatible"


def _adapter_for(provider_canonical: str) -> ChatFn:
    if provider_canonical == "anthropic":
        return _anthropic_adapter.chat_completion
    return _openai_adapter.chat_completion


def chat_completion(settings: Any, messages: list[dict[str, Any]]) -> str:
    """按 ``resolve_provider(settings)`` 直接派发到底层适配器，不做 profile 投影。"""
    return _adapter_for(resolve_provider(settings))(settings, messages)


# ---------------------------------------------------------------------------
# Role-based 路由（Sprint 2 会接入 graph.py / workflow.py）
# ---------------------------------------------------------------------------

def resolve_role_profile(settings: Any, role: str) -> Profile:
    """按 ``active / subagent / planner`` 返回 profile；未配置时回退 active。"""
    profiles = list(getattr(settings, "profiles", ()) or ())
    if not profiles:
        raise RuntimeError("settings.profiles 为空，无法定位 profile")

    role_l = (role or "active").strip().lower()
    active_id = getattr(settings, "active_profile_id", None)
    if role_l == "subagent":
        target_id = getattr(settings, "subagent_profile_id", None) or active_id
    elif role_l == "planner":
        target_id = getattr(settings, "planner_profile_id", None) or active_id
    else:
        target_id = active_id

    for p in profiles:
        if getattr(p, "id", None) == target_id:
            return p
    return profiles[0]


def resolve_effective_profile_for_llm(
    settings: Any,
    role: str,
    messages: list[dict[str, Any]],
    *,
    routing_total_tokens_used_override: int | None = None,
    route_conversation_phase: str | None = None,
) -> Profile:
    """Role profile + ``[[models.route]]`` + ``[models.routing]`` 叠加（按序命中）。"""
    _set_profile_route_decision(None)
    profiles = tuple(getattr(settings, "profiles", ()) or ())
    if not profiles:
        raise RuntimeError("settings.profiles 为空，无法定位 profile")

    def _by_id(pid: str) -> Profile | None:
        for p in profiles:
            if getattr(p, "id", None) == pid:
                return p
        return None

    cur = resolve_role_profile(settings, role)
    goal = routing_goal_from_messages(messages) or ""
    proutes = tuple(getattr(settings, "models_profile_routes", ()) or ())
    if proutes:
        last_pt = int(get_last_usage().get("prompt_tokens") or 0)
        r_hit = first_matching_profile_route(
            proutes,
            goal=goal,
            last_prompt_tokens=last_pt,
            conversation_phase=route_conversation_phase,
        )
        if r_hit is not None:
            picked = _by_id(r_hit.use_profile)
            if picked is not None:
                cur = picked
                _set_profile_route_decision(
                    {
                        "schema_version": "models_route_v1",
                        "matched": True,
                        "use_profile": r_hit.use_profile,
                        "match_task_kind": r_hit.match_task_kind,
                        "match_tokens_gt": r_hit.match_tokens_gt,
                        "match_phase": getattr(r_hit, "match_phase", None),
                        "conversation_phase": route_conversation_phase,
                        "last_prompt_tokens": last_pt,
                    },
                )
    if not bool(getattr(settings, "model_routing_enabled", True)):
        return cur
    rules = getattr(settings, "model_routing_rules", None) or ()
    if not rules:
        return cur
    if routing_total_tokens_used_override is not None:
        used = max(0, int(routing_total_tokens_used_override))
    else:
        snap = get_usage_counters()
        used = int(snap.get("total_tokens") or 0)
    budget = int(getattr(settings, "cost_budget_max_tokens", 0) or 0)
    hit = first_matching_routing_rule(
        rules,
        role=role,
        goal=goal,
        cost_budget_max_tokens=budget,
        total_tokens_used=used,
    )
    if not hit:
        return cur
    picked2 = _by_id(hit.profile_id)
    return picked2 if picked2 is not None else cur


def _project_settings_for_profile(
    settings: Any,
    profile: Profile,
    *,
    force_profile_model: bool = False,
) -> Any:
    """把 settings 字段投影到指定 profile（返回新对象，原对象不改）。

    注意 ``model`` 字段的特殊语义：``Settings.model`` 在加载期已由 active profile
    投影过一次；若当前值与 active profile 的 ``model`` 不一致，则说明上层（CLI
    ``--model`` / workflow step ``model``）用 :func:`dataclasses.replace` 做了
    一次运行期 override，不应被再次的 role projection 静默覆盖。

    ``force_profile_model=True`` 时始终使用 ``profile.model``（TUI ``/use-model``
    按 profile id 切换、模型面板 Enter 等场景）。
    """
    base_url = project_base_url(profile)
    resolved = profile.resolve_api_key()
    api_key = resolved or getattr(settings, "api_key", "") or ""

    effective_model = profile.model
    if not force_profile_model:
        active_id = getattr(settings, "active_profile_id", None)
        cur_model = getattr(settings, "model", None)
        if cur_model and active_id:
            for ap in getattr(settings, "profiles", ()) or ():
                if getattr(ap, "id", None) == active_id:
                    if cur_model != getattr(ap, "model", None):
                        effective_model = cur_model
                    break

    is_anthropic = profile.provider == "anthropic"
    updates: dict[str, Any] = {
        "provider": profile.provider,
        "base_url": base_url,
        "model": effective_model,
        "api_key": api_key,
        "temperature": max(0.0, min(2.0, float(profile.temperature))),
        "llm_timeout_sec": max(5.0, min(3600.0, float(profile.timeout_sec))),
    }
    if hasattr(settings, "active_profile_id"):
        updates["active_profile_id"] = profile.id
    if hasattr(settings, "active_api_key_env"):
        updates["active_api_key_env"] = profile.api_key_env
    if hasattr(settings, "anthropic_version"):
        updates["anthropic_version"] = (
            profile.anthropic_version or "2023-06-01"
            if is_anthropic
            else getattr(settings, "anthropic_version", "2023-06-01")
        )
    if hasattr(settings, "anthropic_max_tokens"):
        updates["anthropic_max_tokens"] = int(
            profile.max_tokens
            if is_anthropic and profile.max_tokens
            else getattr(settings, "anthropic_max_tokens", 4096),
        )
    if hasattr(settings, "context_window"):
        updates["context_window"] = int(
            profile.context_window
            if profile.context_window
            else getattr(settings, "context_window", 8192) or 8192,
        )
    if hasattr(settings, "context_window_source"):
        updates["context_window_source"] = (
            "profile"
            if profile.context_window
            else getattr(settings, "context_window_source", "default")
        )
    return replace(settings, **updates)


def activate_profile_in_memory(settings: Any, profile: Profile) -> Any:
    """将运行期 LLM 相关字段切到 ``profile``（不写 TOML）。

    与 :func:`chat_completion_by_role` 内的投影规则一致，但强制采用该
    profile 的 ``model``，避免把其它 profile 的运行期 model override 带过来。
    """
    return _project_settings_for_profile(settings, profile, force_profile_model=True)


def chat_completion_by_role(
    settings: Any,
    messages: list[dict[str, Any]],
    *,
    role: str = "active",
    route_conversation_phase: str | None = None,
) -> str:
    """按 role 选 profile → 投影 settings → 派发到对应适配器。"""
    profile = resolve_effective_profile_for_llm(
        settings,
        role,
        messages,
        route_conversation_phase=route_conversation_phase,
    )
    projected = _project_settings_for_profile(settings, profile)
    return _adapter_for(resolve_provider(projected))(projected, messages)


__all__ = [
    "ChatFn",
    "activate_profile_in_memory",
    "chat_completion",
    "chat_completion_by_role",
    "peek_last_profile_route_decision",
    "resolve_effective_profile_for_llm",
    "resolve_provider",
    "resolve_role_profile",
]
