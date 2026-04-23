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


__all__ = [
    "ModelRoutingRule",
    "first_matching_routing_rule",
    "model_routing_enabled",
    "parse_model_routing_section",
    "routing_goal_from_messages",
]
