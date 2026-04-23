"""TUI：只读任务看板（调度 + 最近 workflow 快照摘要）。"""

from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Static

from cai_agent.board_state import load_last_workflow_snapshot
from cai_agent.config import Settings
from cai_agent.schedule import list_schedule_tasks


def _short(s: str, n: int) -> str:
    t = (s or "").replace("\n", " ").strip()
    if len(t) <= n:
        return t
    return t[: max(1, n - 1)] + "…"


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
        ws = (getattr(self._settings, "workspace", None) or ".").strip() or "."
        lines: list[str] = [
            "[bold]任务看板（只读）[/]",
            f"[dim]工作区:[/] {ws}",
            "",
            "[bold cyan].cai-schedule.json[/]",
        ]
        try:
            rows = list_schedule_tasks(ws)
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
                st = str(r.get("status") or "")
                goal = _short(str(r.get("goal") or ""), 72)
                lines.append(f"- [cyan]{tid}[/] [{st}] {goal}")
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
                lines.append("[dim]steps（摘要）:[/]")
                for s in steps[:12]:
                    if not isinstance(s, dict):
                        continue
                    nm = str(s.get("name") or "")
                    g = _short(str(s.get("goal") or ""), 56)
                    lines.append(f"  · [yellow]{nm}[/] {g}")
                if len(steps) > 12:
                    lines.append(f"  [dim]… +{len(steps) - 12}[/]")
        body = self.query_one("#task-board-body", Static)
        body.update("\n".join(lines))
        self.sub_title = f"刷新于 {datetime.now().strftime('%H:%M:%S')}"

    def action_close(self) -> None:
        self.dismiss(None)
