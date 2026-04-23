"""Hermes S7-02：``observe report`` 运营摘要（JSON / Markdown）。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from cai_agent.session import build_observe_payload


def build_observe_ops_report_v1(
    *,
    cwd: str,
    pattern: str,
    limit: int,
    days: int,
) -> dict[str, Any]:
    """基于 ``build_observe_payload`` 的时间窗口视图；顶层 ``schema_version`` 为 ``1.0``（S7-02 AC）。"""
    d = max(int(days), 1)
    since_ts = int(datetime.now(UTC).timestamp()) - d * 86400
    obs = build_observe_payload(
        cwd=cwd,
        pattern=pattern,
        limit=limit,
        since_ts=since_ts,
        scan_cap=min(max(limit * 20, 200), 2000),
    )
    ag = obs.get("aggregates") if isinstance(obs.get("aggregates"), dict) else {}
    n = int(obs.get("sessions_count") or 0)
    fr = float(ag.get("failure_rate") or 0.0)
    success_rate = (1.0 - fr) if n else 1.0
    tt = int(ag.get("total_tokens") or 0)
    tool_err = int(ag.get("tool_errors_total") or 0)
    run_ev = int(ag.get("run_events_total") or 0)
    tool_rate = (float(tool_err) / float(n)) if n else 0.0
    top = ag.get("tool_errors_top") if isinstance(ag.get("tool_errors_top"), list) else []
    return {
        "schema_version": "1.0",
        "report_kind": "observe_ops_report_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "window_days": d,
        "pattern": pattern,
        "limit": limit,
        "session_count": n,
        "success_rate": success_rate,
        "failure_rate": fr,
        "token_total": tt,
        "token_avg": (float(tt) / n) if n else 0.0,
        "tool_error_rate": tool_rate,
        "tool_errors_total": tool_err,
        "run_events_total": run_ev,
        "top_failing_tools": top,
        "observe": obs,
    }


def render_observe_ops_markdown(doc: dict[str, Any]) -> str:
    lines = [
        "# Observe 运营摘要",
        "",
        f"- 生成时间：`{doc.get('generated_at')}`",
        f"- 窗口：最近 **{doc.get('window_days')}** 天",
        f"- 会话数：**{doc.get('session_count')}**",
        f"- 成功率：**{float(doc.get('success_rate') or 0):.4f}**（失败率 {float(doc.get('failure_rate') or 0):.4f}）",
        f"- Token 合计：**{doc.get('token_total')}**，均值：**{float(doc.get('token_avg') or 0):.2f}**",
        f"- 工具错误率：**{float(doc.get('tool_error_rate') or 0):.4f}**（`tool_errors_total`={doc.get('tool_errors_total')} / `session_count`={doc.get('session_count')}；另见嵌套 `observe.aggregates.run_events_total`={doc.get('run_events_total')}）",
        "",
        "## Top 失败工具",
        "",
    ]
    top = doc.get("top_failing_tools") or []
    if isinstance(top, list) and top:
        for row in top:
            if not isinstance(row, dict):
                continue
            lines.append(f"- `{row.get('tool')}`：{row.get('errors')} 次")
    else:
        lines.append("- （无）")
    lines.append("")
    lines.append("## 原始 observe 摘要")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(doc.get("observe") or {}, ensure_ascii=False, indent=2)[:8000])
    lines.append("```")
    lines.append("")
    return "\n".join(lines)
