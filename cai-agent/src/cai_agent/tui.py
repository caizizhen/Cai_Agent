from __future__ import annotations

import time
from dataclasses import replace
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Footer, Header, Input, LoadingIndicator, RichLog, Static
from textual.worker import Worker, WorkerState

from cai_agent.config import Settings
from cai_agent.graph import build_app, build_system_prompt
from cai_agent.models import fetch_models


def run_tui(settings: Settings) -> None:
    CaiAgentApp(settings).run()


class ProgressUpdate(Message):
    """从工作线程投递到主循环的阶段信息（thread-safe post_message）。"""

    __slots__ = ("payload",)

    def __init__(self, payload: dict[str, Any]) -> None:
        super().__init__()
        self.payload = payload


class CaiAgentApp(App[None]):
    """类 Claude Code 的终端会话：顶栏、对话区、底部输入。"""

    CSS = """
    Screen { layout: vertical; }
    #chat {
        height: 1fr;
        border: tall $primary;
        margin: 0 1;
        min-height: 8;
        background: $surface;
    }
    #bottom-stack {
        dock: bottom;
        height: auto;
        margin: 0 0 1 0;
    }
    #activity-row {
        height: auto;
        margin: 0 1 0 1;
        padding: 0 0 1 0;
    }
    #loader {
        width: 3;
        margin-right: 1;
        min-height: 1;
    }
    #activity-status {
        width: 1fr;
        height: auto;
        content-align-vertical: middle;
        color: $text-muted;
    }
    #user-input {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "退出", show=True),
    ]

    WORKER_NAME = "cai-agent-invoke"

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._settings = settings
        self._phase_detail = ""
        self._activity_start = 0.0
        self._agent_busy = False
        self._activity_timer: Any = None
        self._agent_worker: Worker | None = None
        self._pending_agent_ctx: dict[str, Any] | None = None

        def _progress_sink(payload: dict[str, Any]) -> None:
            self.post_message(ProgressUpdate(payload))

        self._compiled = build_app(settings, progress=_progress_sink)
        self._messages: list[dict[str, Any]] = [
            {"role": "system", "content": build_system_prompt(settings)},
        ]

    def _rebuild_runtime(self) -> None:
        """模型或系统提示策略变化后重建编排器。"""
        def _progress_sink(payload: dict[str, Any]) -> None:
            self.post_message(ProgressUpdate(payload))

        self._compiled = build_app(self._settings, progress=_progress_sink)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield RichLog(id="chat", highlight=True, markup=True, wrap=True, auto_scroll=True)
        with Vertical(id="bottom-stack"):
            with Horizontal(id="activity-row"):
                yield LoadingIndicator(id="loader")
                yield Static("", id="activity-status")
            yield Input(
                placeholder="输入任务 Enter · /help · /models · /use-model <id> · /clear",
                id="user-input",
            )
        yield Footer()

    def on_mount(self) -> None:
        self.title = "CAI Agent"
        self.sub_title = self._settings.workspace
        self.query_one("#activity-row").display = False
        self._print_welcome()

    def _print_welcome(self) -> None:
        log = self.query_one("#chat", RichLog)
        log.write(
            "[bold]CAI Agent[/] — 本地 LM Studio + LangGraph\n"
            f"工作区: [cyan]{self._settings.workspace}[/]\n"
            f"模型: [cyan]{self._settings.model}[/]  "
            f"API: [dim]{self._settings.base_url}[/]\n"
            "[dim]Ctrl+Q 退出 · 运行中可滚动上方记录[/]\n",
        )

    def _format_phase_line(self, p: dict[str, Any]) -> str:
        phase = p.get("phase")
        if phase == "llm":
            it = p.get("iteration", "")
            st = p.get("step", "")
            return f"[cyan]LLM[/] 第{it}轮 · [dim]{st}[/]"
        if phase == "planned_tool":
            return (
                f"[yellow]待执行工具[/] [bold]{p.get('name', '')}[/] "
                f"[dim]{p.get('summary', '')}[/]"
            )
        if phase == "tool":
            return (
                f"[magenta]执行工具[/] [bold]{p.get('name', '')}[/] "
                f"[dim]{p.get('summary', '')}[/]"
            )
        if phase == "tool_done":
            return f"[green]工具完成[/] [bold]{p.get('name', '')}[/]"
        if phase == "finish":
            return "[green]收尾[/] 汇总最终回答"
        if phase == "limit":
            return "[red]停止[/] 达到最大轮次"
        return ""

    def on_progress_update(self, event: ProgressUpdate) -> None:
        self._phase_detail = self._format_phase_line(event.payload)

    def _stop_activity_timer(self) -> None:
        if self._activity_timer is not None:
            self._activity_timer.stop()
            self._activity_timer = None

    def _log_turn(self, final: dict[str, Any], prev_len: int) -> None:
        log = self.query_one("#chat", RichLog)
        msgs = final.get("messages") or []
        for m in msgs[prev_len + 1 :]:
            role = m.get("role", "")
            content = (m.get("content") or "").strip()
            if not content:
                continue
            if role == "assistant":
                preview = content if len(content) <= 12_000 else content[:12_000] + "\n…[截断]"
                log.write(f"\n[bold green]assistant[/]\n{preview}\n")
            elif role == "user":
                log.write(f"\n[dim]user[/]\n{preview[:4000]}{'…' if len(preview) > 4000 else ''}\n")
        ans = (final.get("answer") or "").strip()
        if ans:
            log.write(f"\n[bold yellow]回答[/]\n{ans}\n")

    def _finish_agent_worker(self, worker: Worker) -> None:
        """Worker 结束后在主线程收尾（不阻塞消息泵）。"""
        self._stop_activity_timer()
        self._phase_detail = ""
        self.query_one("#activity-row").display = False
        self.query_one("#activity-status", Static).update("")
        self.sub_title = self._settings.workspace
        self._agent_busy = False
        self._agent_worker = None

        log = self.query_one("#chat", RichLog)
        ctx = self._pending_agent_ctx
        self._pending_agent_ctx = None
        if ctx is None:
            return

        prev_len = int(ctx["prev_len"])
        msgs = ctx["msgs"]

        if worker.state == WorkerState.SUCCESS:
            final = worker.result
            if not isinstance(final, dict):
                log.write(f"\n[bold red]错误[/]\n异常返回类型: {type(final)!r}\n")
                return
            self._messages = list(final.get("messages", msgs))
            self._log_turn(final, prev_len)
        elif worker.state == WorkerState.ERROR:
            err = worker.error
            log.write(f"\n[bold red]错误[/]\n{err!r}\n")
        else:
            log.write("\n[dim]任务已取消[/]\n")

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        worker = event.worker
        if worker.name != self.WORKER_NAME:
            return
        if not worker.is_finished:
            return
        self._finish_agent_worker(worker)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "user-input":
            return
        inp = self.query_one("#user-input", Input)
        raw = event.value.strip()
        if not raw:
            return
        if self._agent_busy:
            self.notify(
                "上一轮任务仍在运行，请稍候；可先滚动上方对话区查看记录。",
                severity="warning",
                timeout=3.5,
            )
            return
        inp.value = ""

        if raw in ("/help", "/?"):
            self.query_one("#chat", RichLog).write(
                "\n[bold]命令[/]\n"
                "/help — 本帮助\n"
                "/status — 当前模型、工作区与配置来源\n"
                "/models — 拉取当前代理可用模型列表\n"
                "/mcp — 拉取 MCP 工具列表\n"
                "/use-model <id> — 临时切换当前会话模型\n"
                "/reload — 重新从磁盘生成系统提示（项目说明 / Git）\n"
                "/clear — 清空对话并重建系统提示\n"
                "其他以 / 开头会提示未知命令。\n",
            )
            return

        if raw == "/status":
            s = self._settings
            cfg = s.config_loaded_from or "（无 TOML）"
            self.query_one("#chat", RichLog).write(
                f"\n[bold]状态[/]\n"
                f"提供方: [cyan]{s.provider}[/]\n"
                f"工作区: [cyan]{s.workspace}[/]\n"
                f"模型: [cyan]{s.model}[/]\n"
                f"API: [dim]{s.base_url}[/]\n"
                f"温度: {s.temperature}  HTTP超时: {s.llm_timeout_sec}s\n"
                f"配置: [dim]{cfg}[/]\n"
                f"project_context={s.project_context}  git_context={s.git_context}\n"
                f"mcp_enabled={s.mcp_enabled}  mcp_url={s.mcp_base_url or '(none)'}\n",
            )
            return

        if raw == "/reload":
            if self._messages and self._messages[0].get("role") == "system":
                self._messages[0] = {
                    "role": "system",
                    "content": build_system_prompt(self._settings),
                }
            self.query_one("#chat", RichLog).write(
                "\n[green]已重新加载系统提示[/]（CAI.md 等 / Git 摘要按当前开关重读）\n",
            )
            return

        if raw == "/models":
            log = self.query_one("#chat", RichLog)
            try:
                models = fetch_models(self._settings)
            except Exception as e:
                log.write(f"\n[bold red]获取模型失败[/]\n{e!r}\n")
                return
            if not models:
                log.write("\n[yellow]模型列表为空[/]\n")
                return
            preview = "\n".join(f"- {m}" for m in models[:120])
            more = "\n...[已截断]" if len(models) > 120 else ""
            log.write(f"\n[bold]可用模型（{len(models)}）[/]\n{preview}{more}\n")
            return

        if raw == "/mcp":
            from cai_agent.tools import dispatch

            log = self.query_one("#chat", RichLog)
            try:
                text = dispatch(self._settings, "mcp_list_tools", {"force": False})
            except Exception as e:
                log.write(f"\n[bold red]MCP 查询失败[/]\n{e!r}\n")
                return
            if text.startswith("[mcp_list_tools 失败]"):
                log.write(f"\n[bold red]MCP 查询失败[/]\n{text}\n")
            else:
                log.write(f"\n[bold]MCP 工具列表[/]\n{text}\n")
            return

        if raw.startswith("/use-model"):
            parts = raw.split(maxsplit=1)
            if len(parts) != 2 or not parts[1].strip():
                self.query_one("#chat", RichLog).write(
                    "\n[red]用法错误:[/] /use-model <model_id>\n",
                )
                return
            model_id = parts[1].strip()
            self._settings = replace(self._settings, model=model_id)
            self._rebuild_runtime()
            self.sub_title = self._settings.workspace
            if self._messages and self._messages[0].get("role") == "system":
                self._messages[0] = {
                    "role": "system",
                    "content": build_system_prompt(self._settings),
                }
            self.query_one("#chat", RichLog).write(
                f"\n[green]已切换模型[/] [cyan]{model_id}[/]\n",
            )
            return

        if raw == "/clear":
            self._messages = [
                {"role": "system", "content": build_system_prompt(self._settings)},
            ]
            self.query_one("#chat", RichLog).clear()
            self.query_one("#activity-row").display = False
            self.query_one("#activity-status", Static).update("")
            self._phase_detail = ""
            self._print_welcome()
            return

        if raw.startswith("/"):
            self.query_one("#chat", RichLog).write(
                f"[red]未知命令:[/] {raw}（/help 查看可用命令）\n",
            )
            return

        log = self.query_one("#chat", RichLog)
        log.write(f"\n[bold cyan]你[/]\n{raw}\n")
        prev_len = len(self._messages)
        msgs = list(self._messages)
        msgs.append({"role": "user", "content": raw})
        state: dict[str, Any] = {
            "messages": msgs,
            "iteration": 0,
            "pending": None,
            "finished": False,
        }

        activity_row = self.query_one("#activity-row")
        status = self.query_one("#activity-status", Static)
        activity_row.display = True
        self._phase_detail = ""
        self._activity_start = time.monotonic()
        status.update("[yellow]运行中[/] 等待 LangGraph 节点…")

        def _tick_activity() -> None:
            elapsed = int(time.monotonic() - self._activity_start)
            detail = (self._phase_detail or "").strip()
            if detail:
                status.update(f"[yellow]{elapsed}s[/]  {detail}")
            else:
                status.update(
                    f"[yellow]{elapsed}s[/]  "
                    f"[dim]等待模型 / 工具（可滚动上方记录）[/]",
                )

        self._stop_activity_timer()
        self._activity_timer = self.set_interval(0.35, _tick_activity)
        _tick_activity()

        log.focus()

        self._agent_busy = True
        self._pending_agent_ctx = {"prev_len": prev_len, "msgs": msgs}
        self.sub_title = f"{self._settings.workspace}  [dim]运行中…[/]"

        invoke_state = state

        def thread_invoke() -> dict[str, Any]:
            return self._compiled.invoke(invoke_state)

        self._agent_worker = self.run_worker(
            thread_invoke,
            thread=True,
            name=self.WORKER_NAME,
            exclusive=True,
            exit_on_error=False,
        )
