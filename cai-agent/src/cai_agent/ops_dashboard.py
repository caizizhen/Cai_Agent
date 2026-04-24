"""运营聚合：会话看板 + 调度 SLA + 成本 rollup（CLI `ops dashboard`）。"""

from __future__ import annotations

import html
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cai_agent.board_state import attach_failed_summary, attach_status_summary, build_board_payload
from cai_agent.gateway_lifecycle import build_gateway_summary_payload
from cai_agent.schedule import compute_schedule_stats_from_audit
from cai_agent.session import aggregate_sessions


def build_ops_dashboard_payload(
    *,
    cwd: str | Path | None = None,
    observe_pattern: str = ".cai-session*.json",
    observe_limit: int = 100,
    schedule_days: int = 30,
    audit_path: str | Path | None = None,
    cost_session_limit: int = 200,
) -> dict[str, Any]:
    """``ops_dashboard_v1``：嵌套完整 ``board_v1`` 供既有消费者复用，并附调度与成本摘要。"""
    base = Path(cwd or ".").expanduser().resolve()
    board = build_board_payload(
        cwd=str(base),
        observe_pattern=observe_pattern,
        observe_limit=observe_limit,
    )
    board = attach_status_summary(board)
    board = attach_failed_summary(board, limit=5)
    obs = board.get("observe") if isinstance(board.get("observe"), dict) else {}
    ag = obs.get("aggregates") if isinstance(obs.get("aggregates"), dict) else {}
    schedule_stats = compute_schedule_stats_from_audit(
        cwd=str(base),
        days=int(schedule_days),
        audit_path=audit_path,
    )
    cost_agg = aggregate_sessions(
        cwd=str(base),
        pattern=observe_pattern,
        limit=max(1, int(cost_session_limit)),
    )
    gateway_summary = build_gateway_summary_payload(base)
    st_tasks = schedule_stats.get("tasks")
    n_sched = len(st_tasks) if isinstance(st_tasks, list) else 0
    return {
        "schema_version": "ops_dashboard_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(base),
        "observe_pattern": observe_pattern,
        "observe_limit": int(observe_limit),
        "schedule_days": int(schedule_days),
        "summary": {
            "sessions_count": int(obs.get("sessions_count", 0) or 0),
            "failure_rate": float(ag.get("failure_rate", 0.0) or 0.0),
            "failed_count": int(ag.get("failed_count", 0) or 0),
            "total_tokens_observe": int(ag.get("total_tokens", 0) or 0),
            "schedule_tasks_in_stats": n_sched,
            "cost_total_tokens": int(cost_agg.get("total_tokens", 0) or 0),
            "cost_failed_count": int(cost_agg.get("failed_count", 0) or 0),
            "gateway_status": gateway_summary.get("status"),
            "gateway_bindings_count": int(gateway_summary.get("bindings_count", 0) or 0),
            "gateway_webhook_running": bool(gateway_summary.get("webhook_running")),
        },
        "board": board,
        "gateway_summary": gateway_summary,
        "schedule_stats": schedule_stats,
        "cost_aggregate": cost_agg,
    }


# ---------------------------------------------------------------------------
# HTML 静态报告导出（§26 补齐：ops dashboard --format html）
# ---------------------------------------------------------------------------

def _h(text: Any) -> str:
    return html.escape(str(text))


def build_ops_dashboard_html(
    payload: dict[str, Any],
    *,
    html_refresh_seconds: int | None = None,
    live_mode: str | None = None,
    live_url: str | None = None,
    live_interval_seconds: int | None = None,
) -> str:
    """将 ``ops_dashboard_v1`` 载荷渲染为单文件 HTML 仪表盘。

    无外部依赖，内嵌 CSS + 少量内联样式，支持离线打开。
    ``html_refresh_seconds`` > 0 时插入 ``meta http-equiv=refresh``（Phase A 轻量刷新）。
    """
    gen_at = _h(payload.get("generated_at", ""))
    workspace = _h(payload.get("workspace", ""))
    sm = payload.get("summary") or {}
    sessions_count = int(sm.get("sessions_count", 0) or 0)
    failure_rate = float(sm.get("failure_rate", 0.0) or 0.0)
    failed_count = int(sm.get("failed_count", 0) or 0)
    total_tokens = int(sm.get("cost_total_tokens", 0) or 0)
    sched_tasks = int(sm.get("schedule_tasks_in_stats", 0) or 0)

    sched_stats = payload.get("schedule_stats") or {}
    sched_tasks_list = sched_stats.get("tasks") or []
    sched_rows = ""
    if isinstance(sched_tasks_list, list):
        for t in sched_tasks_list[:50]:
            if not isinstance(t, dict):
                continue
            sched_rows += (
                f"<tr><td>{_h(t.get('task_id',''))}</td>"
                f"<td>{_h(t.get('goal_preview',''))}</td>"
                f"<td>{_h(t.get('run_count',0))}</td>"
                f"<td>{_h(t.get('success_count',0))}</td>"
                f"<td>{_h(str(round(float(t.get('success_rate', 0) or 0) * 100)) + '%')}</td>"
                f"<td>{_h(t.get('avg_elapsed_ms','—'))}</td></tr>\n"
            )

    board = payload.get("board") or {}
    obs = board.get("observe") if isinstance(board.get("observe"), dict) else {}
    ag = obs.get("aggregates") if isinstance(obs.get("aggregates"), dict) else {}
    top_tools = ag.get("top_tools") or []
    tool_rows = ""
    if isinstance(top_tools, list):
        for item in top_tools[:10]:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                tool_rows += f"<tr><td>{_h(item[0])}</td><td>{_h(item[1])}</td></tr>\n"
            elif isinstance(item, dict):
                tool_rows += f"<tr><td>{_h(item.get('name',''))}</td><td>{_h(item.get('count',''))}</td></tr>\n"

    fail_rate_pct = f"{failure_rate * 100:.1f}%"
    fail_color = "#d32f2f" if failure_rate > 0.2 else ("#f57c00" if failure_rate > 0.05 else "#388e3c")

    refresh_line = ""
    if html_refresh_seconds is not None:
        sec = int(html_refresh_seconds)
        if sec > 0:
            refresh_line = f'  <meta http-equiv="refresh" content="{_h(sec)}">\n'

    live_script = ""
    live_mode_norm = str(live_mode or "").strip().lower()
    live_url_norm = str(live_url or "").strip()
    live_interval = int(live_interval_seconds or 0)
    if live_mode_norm in ("sse", "poll") and live_url_norm:
        live_url_js = json.dumps(live_url_norm, ensure_ascii=False)
        if live_mode_norm == "sse":
            live_script = f"""
  <script>
    (() => {{
      const streamUrl = {live_url_js};
      if (!window.EventSource) return;
      const es = new EventSource(streamUrl);
      es.onmessage = () => window.location.reload();
      es.onerror = () => es.close();
    }})();
  </script>"""
        elif live_interval > 0:
            live_script = f"""
  <script>
    (() => {{
      const refreshMs = {live_interval * 1000};
      window.setInterval(() => window.location.reload(), refreshMs);
    }})();
  </script>"""

    html_body = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
{refresh_line}  <title>CAI Agent 运营面板</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           background: #f4f6f9; margin: 0; padding: 24px; color: #1a1a2e; }}
    h1 {{ font-size: 1.5rem; margin-bottom: 4px; }}
    .meta {{ font-size: .85rem; color: #666; margin-bottom: 24px; }}
    .cards {{ display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 24px; }}
    .card {{ background: #fff; border-radius: 8px; padding: 20px 24px;
             flex: 1 1 160px; box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
    .card .label {{ font-size: .8rem; color: #888; text-transform: uppercase; letter-spacing: .05em; }}
    .card .value {{ font-size: 2rem; font-weight: 700; margin-top: 4px; }}
    .section {{ background: #fff; border-radius: 8px; padding: 20px 24px;
                margin-bottom: 16px; box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
    .section h2 {{ font-size: 1rem; margin: 0 0 12px; color: #333; border-bottom: 1px solid #eee; padding-bottom: 8px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: .875rem; }}
    th {{ text-align: left; padding: 8px 12px; background: #f8f9fa; color: #555;
          font-weight: 600; border-bottom: 2px solid #e9ecef; }}
    td {{ padding: 8px 12px; border-bottom: 1px solid #f0f0f0; }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: #f9f9fb; }}
    footer {{ font-size: .75rem; color: #aaa; text-align: center; margin-top: 32px; }}
  </style>
</head>
<body>
  <h1>CAI Agent 运营面板</h1>
  <div class="meta">工作区：{workspace} &nbsp;|&nbsp; 生成时间：{gen_at}</div>

  <div class="cards">
    <div class="card">
      <div class="label">会话总数</div>
      <div class="value">{sessions_count}</div>
    </div>
    <div class="card">
      <div class="label">失败率</div>
      <div class="value" style="color:{fail_color}">{fail_rate_pct}</div>
    </div>
    <div class="card">
      <div class="label">失败会话</div>
      <div class="value">{failed_count}</div>
    </div>
    <div class="card">
      <div class="label">Token 总用量</div>
      <div class="value">{total_tokens:,}</div>
    </div>
    <div class="card">
      <div class="label">调度任务数</div>
      <div class="value">{sched_tasks}</div>
    </div>
  </div>

  <div class="section">
    <h2>调度任务 SLA</h2>
    {"<p style='color:#999;font-size:.875rem'>暂无调度数据</p>" if not sched_rows else f'''
    <table>
      <thead><tr><th>Task ID</th><th>目标</th><th>运行次数</th><th>成功次数</th><th>成功率</th><th>平均耗时(ms)</th></tr></thead>
      <tbody>{sched_rows}</tbody>
    </table>'''}
  </div>

  <div class="section">
    <h2>Top 工具调用</h2>
    {"<p style='color:#999;font-size:.875rem'>暂无工具数据</p>" if not tool_rows else f'''
    <table>
      <thead><tr><th>工具名</th><th>调用次数</th></tr></thead>
      <tbody>{tool_rows}</tbody>
    </table>'''}
  </div>

  <footer>由 cai-agent ops dashboard --format html 生成 · {gen_at}</footer>
</body>
</html>"""
    return html_body
