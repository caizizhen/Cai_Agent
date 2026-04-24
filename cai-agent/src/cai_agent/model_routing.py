"""Declarative ``[models.routing]`` rules (TOML) — parse + first-hit match.

See ``docs/MODEL_ROUTING_RULES.zh-CN.md``. Rules are evaluated in file order;
the first rule whose ``roles`` contains the current role and whose optional
goal / cost conditions all match wins. Invalid regex in TOML is skipped at
parse time with no entry (lenient).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ModelsProfileRoute:
    """``[[models.route]]`` — Hermes H1-MP-03 / Canvas F1 细粒度路由。"""

    use_profile: str
    match_task_kind: str | None
    match_tokens_gt: int | None
    match_phase: str | None = None


@dataclass(frozen=True)
class ModelRoutingRule:
    """One ``[[models.routing.rules]]`` row after validation."""

    roles: tuple[str, ...]
    goal_regex: str | None
    goal_substring: str | None
    profile_id: str
    _compiled: re.Pattern[str] | None
    # When set: match iff ``max(0, cost_budget_max_tokens - total_tokens_used) < N``.
    cost_budget_remaining_tokens_below: int | None = None


def _parse_cost_below(raw: object) -> int | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return max(0, int(raw))
    if isinstance(raw, float) and not isinstance(raw, bool):
        return max(0, int(raw))
    if isinstance(raw, str) and raw.strip().isdigit():
        return max(0, int(raw.strip()))
    return None


def parse_models_profile_routes(file_data: dict[str, Any]) -> tuple[ModelsProfileRoute, ...]:
    """Parse ``[[models.route]]`` tables (``models.route`` list in TOML)."""
    models = file_data.get("models")
    if not isinstance(models, dict):
        return ()
    raw_list = models.get("route")
    if not isinstance(raw_list, list):
        return ()
    out: list[ModelsProfileRoute] = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        pid = str(item.get("use_profile") or item.get("profile") or "").strip()
        if not pid:
            continue
        mtk = item.get("match_task_kind")
        task_kind = str(mtk).strip() if isinstance(mtk, str) and mtk.strip() else None
        mtg = item.get("match_tokens_gt")
        tokens_gt: int | None = None
        if isinstance(mtg, bool):
            tokens_gt = None
        elif isinstance(mtg, int | float):
            tokens_gt = max(0, int(mtg))
        elif isinstance(mtg, str) and mtg.strip().isdigit():
            tokens_gt = int(mtg.strip())
        mphase = item.get("match_phase")
        phase_s = str(mphase).strip() if isinstance(mphase, str) and mphase.strip() else None
        if task_kind is None and tokens_gt is None and phase_s is None:
            continue
        out.append(
            ModelsProfileRoute(
                use_profile=pid,
                match_task_kind=task_kind,
                match_tokens_gt=tokens_gt,
                match_phase=phase_s,
            ),
        )
    return tuple(out)


def first_matching_profile_route(
    routes: tuple[ModelsProfileRoute, ...],
    *,
    goal: str,
    last_prompt_tokens: int,
    conversation_phase: str | None = None,
) -> ModelsProfileRoute | None:
    g = (goal or "").strip().lower()
    pt = max(0, int(last_prompt_tokens))
    cp = (conversation_phase or "").strip().lower()
    for r in routes:
        if r.match_phase:
            if not cp:
                continue
            allowed = {x.strip().lower() for x in str(r.match_phase).split("|") if x.strip()}
            if cp not in allowed:
                continue
        if r.match_task_kind:
            if str(r.match_task_kind).lower() not in g:
                continue
        if r.match_tokens_gt is not None:
            if not (pt > int(r.match_tokens_gt)):
                continue
        return r
    return None


def build_models_route_wizard_v1(
    *,
    use_profile: str,
    match_phase: str | None = None,
    match_task_kind: str | None = None,
    match_tokens_gt: int | None = None,
) -> dict[str, Any]:
    """生成可追加到 TOML 的 ``[[models.route]]`` 片段（``models_route_wizard_v1``）。"""
    pid = str(use_profile or "").strip()
    lines = ['[[models.route]]', f'use_profile = "{pid}"']
    if match_phase:
        lines.append(f'match_phase = "{str(match_phase).strip()}"')
    if match_task_kind:
        lines.append(f'match_task_kind = "{str(match_task_kind).strip()}"')
    if match_tokens_gt is not None and int(match_tokens_gt) >= 0:
        lines.append(f"match_tokens_gt = {int(match_tokens_gt)}")
    blob = "\n".join(lines) + "\n"
    return {
        "schema_version": "models_route_wizard_v1",
        "toml_append": blob,
        "preview": {
            "use_profile": pid,
            "match_phase": match_phase,
            "match_task_kind": match_task_kind,
            "match_tokens_gt": match_tokens_gt,
        },
    }


def parse_model_routing_section(file_data: dict[str, Any]) -> tuple[ModelRoutingRule, ...]:
    """Parse ``[models.routing]`` / ``[[models.routing.rules]]`` from loaded TOML."""
    models = file_data.get("models")
    if not isinstance(models, dict):
        return ()
    routing = models.get("routing")
    if not isinstance(routing, dict):
        return ()
    rules_raw = routing.get("rules")
    if not isinstance(rules_raw, list):
        return ()
    out: list[ModelRoutingRule] = []
    for item in rules_raw:
        if not isinstance(item, dict):
            continue
        profile = str(item.get("profile") or "").strip()
        if not profile:
            continue
        roles_raw = item.get("roles")
        if isinstance(roles_raw, str) and roles_raw.strip():
            roles = (roles_raw.strip().lower(),)
        elif isinstance(roles_raw, list):
            roles = tuple(str(x).strip().lower() for x in roles_raw if str(x).strip())
        else:
            roles = ()
        if not roles:
            roles = ("active", "subagent", "planner")
        gr = item.get("goal_regex")
        gs = item.get("goal_substring")
        goal_regex = str(gr).strip() if isinstance(gr, str) and gr.strip() else None
        goal_substring = str(gs).strip() if isinstance(gs, str) and gs.strip() else None
        cost_below = _parse_cost_below(item.get("cost_budget_remaining_tokens_below"))
        if not goal_regex and not goal_substring and cost_below is None:
            continue
        compiled: re.Pattern[str] | None = None
        if goal_regex:
            try:
                compiled = re.compile(goal_regex)
            except re.error:
                continue
        out.append(
            ModelRoutingRule(
                roles=roles,
                goal_regex=goal_regex,
                goal_substring=goal_substring,
                profile_id=profile,
                _compiled=compiled,
                cost_budget_remaining_tokens_below=cost_below,
            ),
        )
    return tuple(out)


def model_routing_enabled(file_data: dict[str, Any]) -> bool:
    models = file_data.get("models")
    if not isinstance(models, dict):
        return True
    routing = models.get("routing")
    if not isinstance(routing, dict):
        return True
    raw = routing.get("enabled")
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.strip().lower() not in ("0", "false", "no", "off")
    return True


def _goal_matches(rule: ModelRoutingRule, goal: str) -> bool:
    has_goal = bool(rule._compiled) or bool(rule.goal_substring)
    if not has_goal:
        return True
    g = goal or ""
    if rule._compiled is not None:
        return bool(rule._compiled.search(g))
    if rule.goal_substring:
        return rule.goal_substring in g
    return False


def _cost_matches(
    rule: ModelRoutingRule,
    *,
    cost_budget_max_tokens: int,
    total_tokens_used: int,
) -> bool:
    if rule.cost_budget_remaining_tokens_below is None:
        return True
    if cost_budget_max_tokens <= 0:
        return False
    remaining = max(0, int(cost_budget_max_tokens) - int(total_tokens_used))
    return remaining < int(rule.cost_budget_remaining_tokens_below)


def first_matching_routing_rule(
    rules: tuple[ModelRoutingRule, ...],
    *,
    role: str,
    goal: str,
    cost_budget_max_tokens: int = 0,
    total_tokens_used: int = 0,
) -> ModelRoutingRule | None:
    """Return the first rule that matches ``role``, goal, and cost snapshot."""
    rl = (role or "active").strip().lower() or "active"
    for rule in rules:
        if rule.roles and rl not in rule.roles:
            continue
        if not _goal_matches(rule, goal):
            continue
        if not _cost_matches(
            rule,
            cost_budget_max_tokens=cost_budget_max_tokens,
            total_tokens_used=total_tokens_used,
        ):
            continue
        return rule
    return None


def routing_goal_from_messages(messages: list[dict[str, Any]]) -> str | None:
    """First non-empty ``user`` message ``content`` string, else ``None``."""
    for m in messages:
        if m.get("role") != "user":
            continue
        c = m.get("content")
        if isinstance(c, str) and c.strip():
            return c
    return None


def build_routing_explain_v1(
    *,
    model_routing_enabled: bool,
    matched: ModelRoutingRule | None,
    base_profile_id: str,
    effective_profile_id: str,
    role: str,
    rules_count: int,
    cost_budget_max_tokens: int,
    total_tokens_used: int,
    cost_budget_remaining: int | None,
) -> dict[str, Any]:
    """人读/机读解释块（嵌于 ``models_routing_test_v1`` 的 ``explain`` 字段）。"""
    rem_txt = (
        f"剩余预算≈{cost_budget_remaining} tokens（max={cost_budget_max_tokens}, used={total_tokens_used}）"
        if cost_budget_remaining is not None
        else f"未启用成本预算条件（max_tokens={cost_budget_max_tokens}）"
    )
    rem_en = (
        f"remaining budget ≈{cost_budget_remaining} tokens (max={cost_budget_max_tokens}, used={total_tokens_used})"
        if cost_budget_remaining is not None
        else f"no cost-budget window (max_tokens={cost_budget_max_tokens})"
    )
    if not model_routing_enabled:
        zh = (
            f"[models.routing] 已关闭（enabled=false）。role={role}，使用 active profile「{effective_profile_id}」。"
            f"{rem_txt}。"
        )
        en = (
            f"[models.routing] disabled. role={role}, using active profile '{effective_profile_id}'. "
            f"{rem_en}."
        )
        decision = "routing_disabled"
    elif matched is not None:
        conds: list[str] = []
        if matched.goal_regex:
            conds.append(f"goal_regex={matched.goal_regex!r}")
        if matched.goal_substring:
            conds.append(f"goal_substring={matched.goal_substring!r}")
        if matched.cost_budget_remaining_tokens_below is not None:
            conds.append(
                f"cost_remaining_below={matched.cost_budget_remaining_tokens_below}",
            )
        cond_s = "，".join(conds) if conds else "（无条件，仅 role）"
        zh = (
            f"命中第 1 条匹配的 [models.routing.rules]：profile={matched.profile_id}，roles={list(matched.roles)}，"
            f"{cond_s}。最终 effective={effective_profile_id}。{rem_txt}。"
        )
        en = (
            f"First matching [models.routing.rules]: profile={matched.profile_id}, roles={list(matched.roles)}, "
            f"conditions: {cond_s}. effective={effective_profile_id}. {rem_en}."
        )
        decision = "matched_rule"
    else:
        zh = (
            f"未命中任何规则（共 {rules_count} 条，role={role}）。回退到 active profile「{base_profile_id}」。"
            f"{rem_txt}。"
        )
        en = (
            f"No rule matched ({rules_count} rules, role={role}). Fallback to active profile '{base_profile_id}'. "
            f"{rem_en}."
        )
        decision = "fallback_active"
    return {
        "schema_version": "routing_explain_v1",
        "decision": decision,
        "summary_zh": zh,
        "summary_en": en,
    }


__all__ = [
    "ModelRoutingRule",
    "build_routing_explain_v1",
    "first_matching_routing_rule",
    "model_routing_enabled",
    "parse_model_routing_section",
    "routing_goal_from_messages",
]
