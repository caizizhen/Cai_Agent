"""运营聚合：会话看板 + 调度 SLA + 成本 rollup（CLI `ops dashboard`）。"""

from __future__ import annotations

import html
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cai_agent.board_state import attach_failed_summary, attach_status_summary, build_board_payload
from cai_agent.gateway_lifecycle import build_gateway_summary_payload
from cai_agent.gateway_maps import summarize_gateway_maps
from cai_agent.config import Settings
from cai_agent.profiles import write_models_to_toml
from cai_agent.schedule import compute_schedule_stats_from_audit
from cai_agent.schedule import list_schedule_tasks
from cai_agent.session import aggregate_sessions


def _ops_action_audit_path(workspace: Path) -> Path:
    p = workspace / ".cai" / "ops-dashboard-actions.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _append_ops_action_audit(
    workspace: Path,
    *,
    action: str,
    mode: str,
    ok: bool,
    summary: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _params = dict(params or {})
    actor = str(
        _params.get("actor")
        or _params.get("operator")
        or os.environ.get("CAI_OPERATOR")
        or os.environ.get("USERNAME")
        or os.environ.get("USER")
        or "unknown",
    ).strip() or "unknown"
    row = {
        "schema_version": "ops_dashboard_action_audit_v1",
        "event_id": str(uuid.uuid4()),
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(workspace),
        "actor": actor,
        "action": str(action),
        "mode": str(mode),
        "ok": bool(ok),
        "result": "success" if bool(ok) else "failed",
        "summary": dict(summary or {}),
        "params": _params,
    }
    ap = _ops_action_audit_path(workspace)
    with ap.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def _read_ops_action_audit(
    workspace: Path,
    *,
    limit: int = 50,
    action: str | None = None,
    mode: str | None = None,
    ok: bool | None = None,
) -> list[dict[str, Any]]:
    ap = _ops_action_audit_path(workspace)
    if not ap.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for raw in ap.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    a = str(action or "").strip()
    m = str(mode or "").strip().lower()
    filt: list[dict[str, Any]] = []
    for r in rows:
        if a and str(r.get("action") or "") != a:
            continue
        if m and str(r.get("mode") or "").lower() != m:
            continue
        if ok is not None and bool(r.get("ok")) != bool(ok):
            continue
        filt.append(r)
    return filt[-max(1, int(limit)) :]


def _apply_schedule_reorder(workspace: Path, task_ids: list[str]) -> dict[str, Any]:
    sched = workspace / ".cai-schedule.json"
    if not sched.is_file():
        return {"ok": False, "error": "schedule_file_not_found"}
    try:
        doc = json.loads(sched.read_text(encoding="utf-8"))
    except Exception:
        return {"ok": False, "error": "schedule_file_invalid_json"}
    tasks = doc.get("tasks") if isinstance(doc.get("tasks"), list) else []
    by_id = {
        str(t.get("id") or "").strip(): t for t in tasks if isinstance(t, dict) and str(t.get("id") or "").strip()
    }
    if len(by_id) != len(task_ids):
        return {"ok": False, "error": "schedule_id_mismatch"}
    reordered = [by_id[tid] for tid in task_ids if tid in by_id]
    if len(reordered) != len(tasks):
        return {"ok": False, "error": "schedule_reorder_incomplete"}
    doc["tasks"] = reordered
    sched.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "written_path": str(sched)}


def _apply_gateway_binding_patch(
    *,
    map_path: Path,
    binding_id: str,
    key_name: str,
    patch: dict[str, Any],
) -> dict[str, Any]:
    if not map_path.is_file():
        return {"ok": False, "error": "map_file_not_found", "map_path": str(map_path)}
    try:
        doc = json.loads(map_path.read_text(encoding="utf-8"))
    except Exception:
        return {"ok": False, "error": "map_file_invalid_json", "map_path": str(map_path)}
    if not isinstance(doc, dict):
        return {"ok": False, "error": "map_file_invalid_shape", "map_path": str(map_path)}
    bindings = doc.get("bindings") if isinstance(doc.get("bindings"), dict) else {}
    target = bindings.get(binding_id)
    if not isinstance(target, dict):
        return {"ok": False, "error": "binding_not_found", "map_path": str(map_path)}
    for k, v in patch.items():
        target[k] = v
    bindings[binding_id] = target
    doc["bindings"] = bindings
    map_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "map_path": str(map_path),
        key_name: binding_id,
        "binding": target,
    }


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


def build_ops_dashboard_interactions_payload(
    *,
    cwd: str | Path | None = None,
    action: str,
    mode: str = "preview",
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Dashboard interaction contract for preview/apply/audit flows."""
    base = Path(cwd or ".").expanduser().resolve()
    act = str(action or "").strip()
    op_mode = str(mode or "preview").strip().lower() or "preview"
    p = dict(params or {})
    supported = ("schedule_reorder_preview", "gateway_bind_edit_preview", "profile_switch_preview")
    result: dict[str, Any] = {
        "schema_version": "ops_dashboard_interactions_v1",
        "workspace": str(base),
        "action": act,
        "mode": op_mode,
        "dry_run": op_mode != "apply",
        "applied": False,
        "supported_actions": list(supported),
        "supported_modes": ["preview", "apply", "audit"],
    }
    if op_mode not in ("preview", "apply", "audit"):
        return {
            **result,
            "ok": False,
            "error": "unsupported_mode",
        }
    if op_mode == "audit":
        ok_raw = str(p.get("ok") or "").strip().lower()
        ok_filter: bool | None = None
        if ok_raw in ("1", "true", "yes", "on"):
            ok_filter = True
        elif ok_raw in ("0", "false", "no", "off"):
            ok_filter = False
        rows = _read_ops_action_audit(
            base,
            limit=int(p.get("limit") or 50),
            action=str(p.get("filter_action") or "").strip() or None,
            mode=str(p.get("filter_mode") or "").strip() or None,
            ok=ok_filter,
        )
        return {
            **result,
            "ok": True,
            "audit_schema_version": "ops_dashboard_action_audit_v1",
            "filter": {
                "action": str(p.get("filter_action") or "").strip() or None,
                "mode": str(p.get("filter_mode") or "").strip() or None,
                "ok": ok_filter,
            },
            "records_count": len(rows),
            "records": rows,
        }
    if act not in supported:
        return {
            **result,
            "ok": False,
            "error": "unsupported_action",
        }

    if act == "profile_switch_preview":
        cfg_in_workspace = base / "cai-agent.toml"
        cfg = str(cfg_in_workspace) if cfg_in_workspace.is_file() else None
        settings = Settings.from_env(config_path=cfg, workspace_hint=str(base))
        target_profile_id = str(p.get("target_profile_id") or "").strip()
        available_ids = [pp.id for pp in settings.profiles]
        if not target_profile_id:
            return {**result, "ok": False, "error": "missing_target_profile_id", "available_profile_ids": available_ids}
        if target_profile_id not in available_ids:
            return {
                **result,
                "ok": False,
                "error": "target_profile_not_found",
                "available_profile_ids": available_ids,
            }
        preview_profile = next((pp for pp in settings.profiles if pp.id == target_profile_id), None)
        if preview_profile is None:
            return {
                **result,
                "ok": False,
                "error": "target_profile_not_found",
                "available_profile_ids": available_ids,
            }
        out = {
            **result,
            "ok": True,
            "active_profile_id": settings.active_profile_id,
            "target_profile_id": target_profile_id,
            "target_profile_provider": preview_profile.provider,
            "target_profile_model": preview_profile.model,
            "summary": {
                "position_changed": settings.active_profile_id != target_profile_id,
            },
        }
        if op_mode == "apply":
            cfg = Path(str(settings.config_loaded_from or "")).expanduser() if settings.config_loaded_from else None
            if cfg is None:
                out["ok"] = False
                out["error"] = "config_file_not_found"
                out["applied"] = False
            else:
                write_models_to_toml(
                    cfg,
                    settings.profiles,
                    active=target_profile_id,
                    subagent=settings.subagent_profile_id,
                    planner=settings.planner_profile_id,
                )
                out["applied"] = True
                out["apply_result"] = {"ok": True, "config_path": str(cfg)}
        audit_ps = _append_ops_action_audit(
            base,
            action=act,
            mode=op_mode,
            ok=bool(out.get("ok")),
            summary=out.get("summary") if isinstance(out.get("summary"), dict) else {},
            params={"target_profile_id": target_profile_id},
        )
        out["audit_event"] = audit_ps
        return out

    if act == "schedule_reorder_preview":
        tasks = list_schedule_tasks(str(base))
        task_ids = [str(t.get("id") or "").strip() for t in tasks if isinstance(t, dict)]
        task_ids = [x for x in task_ids if x]
        task_id = str(p.get("task_id") or "").strip()
        before_task_id = str(p.get("before_task_id") or "").strip()
        if not task_id:
            return {**result, "ok": False, "error": "missing_task_id", "current_order": task_ids}
        if task_id not in task_ids:
            return {**result, "ok": False, "error": "task_not_found", "current_order": task_ids}
        if before_task_id and before_task_id not in task_ids:
            return {**result, "ok": False, "error": "before_task_not_found", "current_order": task_ids}
        next_order = [x for x in task_ids if x != task_id]
        if before_task_id:
            idx = next_order.index(before_task_id)
            next_order.insert(idx, task_id)
        else:
            next_order.append(task_id)
        preview = {
            **result,
            "ok": True,
            "current_order": task_ids,
            "preview_order": next_order,
            "summary": {
                "task_id": task_id,
                "before_task_id": before_task_id or None,
                "position_changed": task_ids != next_order,
            },
        }
        if op_mode == "apply" and task_ids != next_order:
            wr = _apply_schedule_reorder(base, next_order)
            preview["applied"] = bool(wr.get("ok"))
            preview["apply_result"] = wr
        audit = _append_ops_action_audit(
            base,
            action=act,
            mode=op_mode,
            ok=bool(preview.get("ok")),
            summary=preview.get("summary") if isinstance(preview.get("summary"), dict) else {},
            params={"task_id": task_id, "before_task_id": before_task_id or None},
        )
        preview["audit_event"] = audit
        return preview

    platform = str(p.get("platform") or "").strip().lower()
    binding_id = str(p.get("binding_id") or "").strip()
    if platform not in ("telegram", "discord", "slack", "teams"):
        return {**result, "ok": False, "error": "unsupported_platform"}
    if not binding_id:
        return {**result, "ok": False, "error": "missing_binding_id"}
    maps = summarize_gateway_maps([base])
    workspace_rows = maps.get("workspaces") if isinstance(maps.get("workspaces"), list) else []
    ws = workspace_rows[0] if workspace_rows and isinstance(workspace_rows[0], dict) else {}
    plat = ws.get(platform) if isinstance(ws.get(platform), dict) else {}
    rows = plat.get("bindings") if isinstance(plat.get("bindings"), list) else []
    key_name = "conversation_id" if platform == "teams" else "channel_id" if platform in ("discord", "slack") else "binding_key"
    current = next((r for r in rows if isinstance(r, dict) and str(r.get(key_name) or "") == binding_id), None)
    patch: dict[str, Any] = {}
    for key in ("session_file", "label"):
        if key in p and str(p.get(key) or "").strip():
            patch[key] = str(p.get(key)).strip()
    response = {
        **result,
        "ok": True,
        "platform": platform,
        "binding_id": binding_id,
        "binding_found": current is not None,
        "map_path": plat.get("map_path"),
        "current_binding": current,
        "preview_binding": {**(current or {key_name: binding_id}), **patch},
        "summary": {
            "changed_fields": sorted(patch.keys()),
            "requires_apply_endpoint": True,
        },
    }
    if op_mode == "apply" and current is not None and patch:
        mp = Path(str(plat.get("map_path") or "")).expanduser()
        wr2 = _apply_gateway_binding_patch(
            map_path=mp,
            binding_id=binding_id,
            key_name=key_name,
            patch=patch,
        )
        response["applied"] = bool(wr2.get("ok"))
        response["apply_result"] = wr2
    audit2 = _append_ops_action_audit(
        base,
        action=act,
        mode=op_mode,
        ok=bool(response.get("ok")),
        summary=response.get("summary") if isinstance(response.get("summary"), dict) else {},
        params={"platform": platform, "binding_id": binding_id, **patch},
    )
    response["audit_event"] = audit2
    return response


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
