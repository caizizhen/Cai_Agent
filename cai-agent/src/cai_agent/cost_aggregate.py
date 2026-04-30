"""P0-MP：按 profile / provider 聚合成本相关 tokens（metrics + 会话快照）。"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _default_metrics_path(cwd: str | Path) -> Path:
    env = str(os.environ.get("CAI_METRICS_JSONL", "") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return Path(cwd).expanduser().resolve() / ".cai" / "metrics.jsonl"


def _read_jsonl(path: Path, *, max_lines: int = 20_000) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for raw in lines[-max_lines:]:
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def build_cost_by_profile_v1(
    cwd: str | Path,
    *,
    metrics_path: str | Path | None = None,
    session_pattern: str = ".cai-session*.json",
    session_limit: int = 200,
    include_by_tenant: bool = False,
    include_by_calendar_day: bool = False,
) -> dict[str, Any]:
    """``cost_by_profile_v1``：聚合 metrics 行与会话 JSON 中的 tokens / profile 线索。"""
    base = Path(cwd).expanduser().resolve()
    mp = Path(metrics_path).expanduser().resolve() if metrics_path else _default_metrics_path(base)
    metrics_rows = _read_jsonl(mp)
    by_profile: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"id": "", "total_tokens": 0, "cost_estimate_usd": 0.0, "route_hits": 0, "events": 0},
    )
    by_provider: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"provider": "", "total_tokens": 0, "events": 0},
    )
    by_route_rule: dict[str, int] = defaultdict(int)
    by_tenant: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"tenant_id": "", "total_tokens": 0, "events": 0},
    )
    by_calendar_day: dict[str, int] = defaultdict(int)

    for row in metrics_rows:
        mod = str(row.get("module") or "")
        ev = str(row.get("event") or "")
        tok = int(row.get("tokens") or 0)
        pid = str(row.get("active_profile_id") or row.get("profile_id") or "").strip()
        prov = str(row.get("provider") or "").strip()
        if not pid and mod == "llm":
            pid = "_unknown_profile"
        if pid:
            slot = by_profile[pid]
            slot["id"] = pid
            slot["total_tokens"] += tok
            slot["events"] = int(slot.get("events") or 0) + 1
            cu = row.get("cost_usd")
            if isinstance(cu, int | float):
                slot["cost_estimate_usd"] = float(slot.get("cost_estimate_usd") or 0.0) + float(cu)
        if prov:
            ps = by_provider[prov]
            ps["provider"] = prov
            ps["total_tokens"] += tok
            ps["events"] = int(ps.get("events") or 0) + 1
        if include_by_tenant or include_by_calendar_day:
            tenant = str(row.get("tenant_id") or row.get("tenant") or "").strip() or "_default"
            if include_by_tenant:
                bt = by_tenant[tenant]
                bt["tenant_id"] = tenant
                bt["total_tokens"] += tok
                bt["events"] = int(bt.get("events") or 0) + 1
            if include_by_calendar_day:
                ts = str(row.get("ts") or "")
                day = ts[:10] if len(ts) >= 10 else ""
                if len(day) == 10 and day[4] == "-" and day[7] == "-":
                    by_calendar_day[day] += tok
        if "route" in ev.lower() or "profile_route" in json.dumps(row, ensure_ascii=False):
            key = f"{mod}:{ev}"
            by_route_rule[key] += 1

    # 会话文件：累计 total_tokens 与 active_profile_id
    try:
        from cai_agent.session import list_session_files, load_session

        paths = list_session_files(cwd=str(base), pattern=session_pattern, limit=session_limit)
        for p in paths:
            try:
                sess = load_session(str(p))
            except Exception:
                continue
            tt = int(sess.get("total_tokens") or 0)
            ap = str(sess.get("active_profile_id") or sess.get("profile") or "").strip()
            if ap and tt > 0:
                slot = by_profile[ap]
                slot["id"] = ap
                slot["total_tokens"] += tt
                slot["events"] = int(slot.get("events") or 0) + 1
    except Exception:
        pass

    profiles_list = sorted(by_profile.values(), key=lambda x: -int(x.get("total_tokens") or 0))
    providers_list = sorted(by_provider.values(), key=lambda x: -int(x.get("total_tokens") or 0))
    empty = not metrics_rows and not profiles_list and not providers_list

    out: dict[str, Any] = {
        "schema_version": "cost_by_profile_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(base),
        "metrics_file": str(mp),
        "empty": bool(empty),
        "profiles": profiles_list,
        "by_provider": providers_list,
        "by_route_rule": dict(sorted(by_route_rule.items(), key=lambda kv: -kv[1])[:40]),
    }
    if include_by_tenant:
        out["by_tenant"] = sorted(
            by_tenant.values(),
            key=lambda x: -int(x.get("total_tokens") or 0),
        )
    if include_by_calendar_day:
        out["by_calendar_day"] = dict(sorted(by_calendar_day.items()))
    return out


def build_compact_policy_explain_v1(
    *,
    cost_budget_max_tokens: int,
    context_compact_after_iterations: int,
    context_compact_min_messages: int,
    context_compact_on_tool_error: bool,
    context_compact_after_tool_calls: int,
    context_compact_mode: str = "heuristic",
    context_compact_trigger_ratio: float = 0.85,
    context_compact_keep_tail_messages: int = 8,
    context_compact_summary_max_chars: int = 6000,
) -> dict[str, Any]:
    """与 ``graph`` 中注入 compact / 成本提示的阈值对齐，供 ``cost report`` 机读与人读。"""
    budget = max(0, int(cost_budget_max_tokens))
    ratio = 0.85
    lines_zh: list[str] = [
        f"context_compact_after_iterations={int(context_compact_after_iterations)}，"
        f"context_compact_min_messages={int(context_compact_min_messages)}："
        "达到轮次且非 system 消息数足够时，可能注入「对话已较长」类提示。",
        f"context_compact_after_tool_calls={int(context_compact_after_tool_calls)}："
        "工具调用达到阈值时可触发里程碑压缩提示。",
        f"context_compact_on_tool_error={'开' if context_compact_on_tool_error else '关'}："
        "工具错误时是否追加压缩类提示。",
    ]
    lines_en: list[str] = [
        f"context_compact_mode={str(context_compact_mode or 'heuristic')}.",
        f"When iteration >= {int(context_compact_after_iterations)} and "
        f"non-system messages >= {int(context_compact_min_messages)}, "
        "the runtime may inject a length / finish hint (see graph compact path).",
        f"After {int(context_compact_after_tool_calls)} tool calls, milestone compact hints may apply.",
        f"When estimated prompt tokens >= context_window * {float(context_compact_trigger_ratio):.2f}, "
        "older messages may be replaced with context_summary_v1.",
        f"context_compact_on_tool_error={bool(context_compact_on_tool_error)}.",
    ]
    if budget > 0:
        lines_zh.append(
            f"[cost] budget_max_tokens={budget}：当轮次累计 tokens > {int(budget * ratio)} "
            f"（≈{ratio:.0%} 预算）且已触发 compact 分支时，可能追加「成本提示」消息。",
        )
        lines_en.append(
            f"[cost] budget_max_tokens={budget}: when compact branch runs and "
            f"cumulative tokens > {int(budget * ratio)} (~{ratio:.0%}), a cost hint may be injected.",
        )
    else:
        lines_zh.append("[cost] budget_max_tokens=0：未启用基于预算的成本提示（仍可触发迭代类 compact）。")
        lines_en.append("[cost] budget_max_tokens=0: budget-based cost hints disabled.")
    return {
        "schema_version": "compact_policy_explain_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "cost_budget_max_tokens": budget,
        "cost_hint_ratio": ratio if budget > 0 else None,
        "context_compact_after_iterations": int(context_compact_after_iterations),
        "context_compact_min_messages": int(context_compact_min_messages),
        "context_compact_on_tool_error": bool(context_compact_on_tool_error),
        "context_compact_after_tool_calls": int(context_compact_after_tool_calls),
        "context_compact_mode": str(context_compact_mode or "heuristic"),
        "context_compact_trigger_ratio": float(context_compact_trigger_ratio),
        "context_compact_keep_tail_messages": int(context_compact_keep_tail_messages),
        "context_compact_summary_max_chars": int(context_compact_summary_max_chars),
        "lines_zh": lines_zh,
        "lines_en": lines_en,
    }


def build_cost_budget_explain_v1(
    *,
    state: str,
    total_tokens: int,
    max_tokens: int,
) -> dict[str, Any]:
    """嵌于 ``cost_budget_v1`` 的 ``explain``，便于 CLI/CI 人读。"""
    if max_tokens <= 0:
        zh = f"未配置有效预算（[cost].budget_max_tokens={max_tokens}）；当前聚合 total_tokens={total_tokens}。"
        en = f"No effective token budget (max_tokens={max_tokens}); aggregated total_tokens={total_tokens}."
    elif state == "fail":
        zh = f"已超过预算：total_tokens={total_tokens} > max_tokens={max_tokens}（exit 2）。"
        en = f"Over budget: total_tokens={total_tokens} > max_tokens={max_tokens} (exit 2)."
    elif state == "warn":
        zh = f"接近预算（>80%）：total_tokens={total_tokens} / max_tokens={max_tokens}，请关注。"
        en = f"Near budget (>80%): total_tokens={total_tokens} / max_tokens={max_tokens}."
    else:
        zh = f"在预算内：total_tokens={total_tokens} / max_tokens={max_tokens}。"
        en = f"Within budget: total_tokens={total_tokens} / max_tokens={max_tokens}."
    return {
        "schema_version": "cost_budget_explain_v1",
        "state": state,
        "summary_zh": zh,
        "summary_en": en,
    }
