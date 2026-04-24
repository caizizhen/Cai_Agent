"""TUI：只读任务看板（调度 + board 同源 observe 摘要 + 最近 workflow 快照）。"""

from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Static

from cai_agent.board_state import (
    attach_failed_summary,
    attach_status_summary,
    build_board_payload,
    load_last_workflow_snapshot,
)
from cai_agent.config import Settings
from cai_agent.mcp_presets import format_tui_mcp_web_notebook_quickstart
from cai_agent.tui_session_strip import tui_task_board_session_line_rich
from cai_agent.schedule import enrich_schedule_tasks_for_display, list_schedule_tasks


def _short(s: str, n: int) -> str:
    t = (s or "").replace("\n", " ").strip()
    if len(t) <= n:
        return t
    return t[: max(1, n - 1)] + "…"


def render_task_board_markup(settings: Settings) -> str:
    """生成任务看板 Rich markup（与 ``board`` / ``schedule list`` 数据源对齐，供测试与 UI 复用）。"""
    ws = (getattr(settings, "workspace", None) or ".").strip() or "."
    lines: list[str] = [
        "[bold]任务看板（只读）[/]",
        tui_task_board_session_line_rich(),
        f"[dim]工作区:[/] {ws}",
        "",
        "[bold magenta]board 同源（observe · board_v1）[/]",
    ]
    try:
        payload = build_board_payload(
            cwd=ws,
            observe_pattern=".cai-session*.json",
            observe_limit=100,
        )
        payload = attach_failed_summary(payload, limit=5)
        payload = attach_status_summary(payload)
    except Exception as e:
        lines.append(f"[red]聚合 observe 失败:[/] {e!s}")
        payload = None

    if payload is not None:
        obs = payload.get("observe") if isinstance(payload.get("observe"), dict) else {}
        lines.append(
            f"[dim]observe[/] schema={obs.get('schema_version')} "
            f"sessions={obs.get('sessions_count', 0)}",
        )
        ag = obs.get("aggregates") if isinstance(obs.get("aggregates"), dict) else {}
        lines.append(
            f"[dim]aggregates[/] failed={ag.get('failed_count')} "
            f"tokens={ag.get('total_tokens')} "
            f"run_events_total={ag.get('run_events_total', 0)}",
        )
        st_sum = payload.get("status_summary")
        if isinstance(st_sum, dict):
            counts = st_sum.get("counts")
            if isinstance(counts, dict):
                lines.append(
                    "[dim]status_summary[/] "
                    f"pending={counts.get('pending', 0)} "
                    f"running={counts.get('running', 0)} "
                    f"completed={counts.get('completed', 0)} "
                    f"failed={counts.get('failed', 0)} "
                    f"unknown={counts.get('unknown', 0)}",
                )
        fs = payload.get("failed_summary")
        recent = fs.get("recent") if isinstance(fs, dict) else None
        if isinstance(recent, list) and recent:
            lines.append("[dim]recent_failed（与 board 一致，最多 5）:[/]")
            for row in recent[:5]:
                if not isinstance(row, dict):
                    continue
                lines.append(
                    "  · "
                    f"[red]{_short(str(row.get('path') or ''), 48)}[/] "
                    f"task_id={row.get('task_id')} errors={row.get('error_count')}",
                )
        sessions = obs.get("sessions")
        if isinstance(sessions, list) and sessions:
            lines.append("[dim]sessions（前 8 条，无筛选，同 board 默认）:[/]")
            for r in sessions[:8]:
                if not isinstance(r, dict):
                    continue
                tid = str(r.get("task_id") or "?")
                st = str(r.get("task_status") or "")
                ec = int(r.get("error_count") or 0)
                p = _short(str(r.get("path") or ""), 40)
                lines.append(f"  · [cyan]{tid}[/] [{st}] err={ec} [dim]{p}[/]")
            if len(sessions) > 8:
                lines.append(f"  [dim]… 共 {len(sessions)} 条[/]")
        else:
            lines.append("[dim]（无会话文件匹配 .cai-session*.json）[/]")

    lines.extend(["", "[bold cyan].cai-schedule.json[/]（与 schedule list 同源 + enrich）"])
    try:
        raw_rows = list_schedule_tasks(ws)
        rows = enrich_schedule_tasks_for_display(
            [r for r in raw_rows if isinstance(r, dict)],
        )
    except Exception as e:
        lines.append(f"[red]读取调度失败:[/] {e!s}")
        rows = []
    if not rows:
        lines.append("[dim]（无定时任务）[/]")
    else:
        for r in rows[:40]:
            if not isinstance(r, dict):
                continue
            tid = str(r.get("id") or r.get("task_id") or "?")
            st = str(r.get("status") or r.get("last_status") or "")
            goal = _short(str(r.get("goal") or ""), 56)
            dep_blk = "[red]blocked[/]" if r.get("dependency_blocked") else "[dim]ok[/]"
            chain = str(r.get("depends_on_chain") or "").strip()
            chain_s = _short(chain, 52) if chain else "-"
            lines.append(
                f"- [cyan]{tid}[/] [{st}] {dep_blk} [dim]chain=[/]{chain_s}",
            )
            lines.append(f"  {goal}")
            deps = r.get("depends_on") or []
            if isinstance(deps, list) and deps:
                lines.append(
                    f"  [dim]depends_on:[/] {', '.join(str(x) for x in deps if str(x).strip())}",
                )
            dents = r.get("dependents") or []
            if isinstance(dents, list) and dents:
                lines.append(
                    f"  [dim]dependents:[/] {', '.join(str(x) for x in dents[:8])}"
                    + (" …" if len(dents) > 8 else ""),
                )
        if len(rows) > 40:
            lines.append(f"[dim]… 共 {len(rows)} 条，仅显示前 40[/]")

    lines.extend(["", "[bold cyan].cai/last-workflow.json[/]"])
    try:
        snap = load_last_workflow_snapshot(ws)
    except Exception as e:
        lines.append(f"[red]读取 workflow 快照失败:[/] {e!s}")
        snap = None
    if not snap:
        lines.append("[dim]（无最近 workflow 快照；可先运行 cai-agent workflow …）[/]")
    else:
        saved = str(snap.get("saved_at") or "")
        if saved:
            lines.append(f"[dim]saved_at[/] {saved}")
        wf = snap.get("workflow_file")
        if wf:
            lines.append(f"[dim]workflow_file[/] {wf}")
        tsk = snap.get("task")
        if isinstance(tsk, dict):
            lines.append(
                f"[dim]task[/] id={tsk.get('task_id')} status={tsk.get('status')}",
            )
        steps = snap.get("steps")
        if isinstance(steps, list) and steps:
            lines.append("[dim]steps（顺序与 last-workflow 一致）:[/]")
            for s in steps[:20]:
                if not isinstance(s, dict):
                    continue
                ix = s.get("index", "")
                nm = str(s.get("name") or "")
                g = _short(str(s.get("goal") or ""), 52)
                ec = s.get("error_count", 0)
                fin = s.get("finished")
                try:
                    ix_i = int(ix) if ix is not None else 0
                except (TypeError, ValueError):
                    ix_i = 0
                sp = "  " * min(ix_i, 8)
                lines.append(f"{sp}· [yellow]{nm}[/] [dim]idx={ix}[/] err={ec} done={fin}")
                lines.append(f"{sp}  {g}")
            if len(steps) > 20:
                lines.append(f"  [dim]… +{len(steps) - 20} 步[/]")

    lines.append(format_tui_mcp_web_notebook_quickstart())
    return "\n".join(lines)


class TaskBoardScreen(ModalScreen[None]):
    """只读面板：Esc / q 关闭。"""

    BINDINGS = [
        Binding("escape", "close", "关闭", show=True),
        Binding("q", "close", "关闭", show=False),
    ]

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._settings = settings

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("", id="task-board-body", markup=True),
            id="task-board-wrap",
        )
        yield Footer()

    def on_mount(self) -> None:
        body = self.query_one("#task-board-body", Static)
        body.update(render_task_board_markup(self._settings))
        self.sub_title = f"刷新于 {datetime.now().strftime('%H:%M:%S')}"

    def action_close(self) -> None:
        self.dismiss(None)
