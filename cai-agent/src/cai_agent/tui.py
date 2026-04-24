from __future__ import annotations

import difflib
import json
import time
from dataclasses import replace
from pathlib import Path
from datetime import datetime
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.suggester import Suggester
from textual.widgets import Footer, Header, Input, LoadingIndicator, RichLog, Static
from textual.worker import Worker, WorkerState

from cai_agent import __version__
from cai_agent.command_registry import load_command_text
from cai_agent.config import Settings
from cai_agent.graph import build_app, build_system_prompt
from cai_agent.llm import estimate_tokens_from_messages, get_last_usage
from cai_agent.llm_factory import activate_profile_in_memory
from cai_agent.models import fetch_models
from cai_agent.profiles import Profile, build_profile_contract_payload
from cai_agent.skill_registry import load_related_skill_texts
from cai_agent.session import list_session_files, load_session, save_session
from cai_agent.mcp_presets import format_tui_mcp_web_notebook_quickstart
from cai_agent.tui_session_strip import (
    tui_input_placeholder,
    tui_session_continue_one_liner_rich,
    tui_workbench_cheatsheet_rich,
)
from cai_agent.tui_model_panel import ModelPanelScreen
from cai_agent.tui_task_board import TaskBoardScreen
from cai_agent.tui_path_complete import suggest_path_after_command

# 斜杠命令补全：顺序决定前缀冲突时的优先级（短命令在前，同前缀的长命令紧跟其后）。
_SLASH_COMMAND_CANDIDATES: tuple[str, ...] = (
    "/?",
    "/help",
    "/status",
    "/models",
    "/models refresh",
    "/mcp refresh",
    "/mcp call ",
    "/mcp",
    "/mcp-presets",
    "/save",
    "/save ",
    "/sessions",
    "/tasks",
    "/load",
    "/load ",
    "/load latest",
    "/use-model",
    "/use-model ",
    "/reload",
    "/fix-build",
    "/security-scan",
    "/stop",
    "/clear",
)

_USE_MODEL_PREFIX = "/use-model "
_MCP_CALL_PREFIX = "/mcp call "
_LOAD_PREFIX = "/load "
_SAVE_PREFIX = "/save "
_LOAD_LATEST = "/load latest"

# 斜杠命令纠错：与补全候选略有不同（含多词命令），用于未知输入时的友好提示。
_SLASH_TYPO_POOL: tuple[str, ...] = (
    "/?",
    "/help",
    "/status",
    "/models",
    "/models refresh",
    "/mcp",
    "/mcp refresh",
    "/mcp-presets",
    "/save",
    "/load",
    "/load latest",
    "/sessions",
    "/tasks",
    "/use-model",
    "/reload",
    "/fix-build",
    "/security-scan",
    "/stop",
    "/clear",
)


def _slash_typo_hint(value: str) -> str | None:
    """对明显打错的斜杠命令给出一条「你可能想输入」提示。"""
    v = value.strip()
    if not v.startswith("/"):
        return None
    if v in _SLASH_TYPO_POOL:
        return None
    if v.startswith("/mcp call ") or v.startswith("/load ") or v.startswith("/save "):
        return None
    if v.startswith("/use-model ") and len(v.split()) >= 2:
        return None
    token = v.split(maxsplit=1)[0]
    if token in _SLASH_TYPO_POOL:
        return None
    m = difflib.get_close_matches(token, _SLASH_TYPO_POOL, n=1, cutoff=0.72)
    if not m:
        return None
    sug = m[0]
    if sug == token:
        return None
    return f"[dim]你可能想输入:[/] [cyan]{sug}[/]"


def _cai_brand_markup() -> str:
    """顶栏下品牌区：FIGlet standard 风格「CAI」三列 + 「Cai」字标。"""
    cols = (
        (" ██████╗ ", "██╔════╝ ", "██║      ", "██║      ", "╚██████╗ ", " ╚═════╝ "),
        (" █████╗ ", "██╔══██╗", "███████║", "██╔══██║", "██║  ██║", "╚═╝  ╚═╝"),
        (" ██╗ ", " ██║ ", " ██║ ", " ██║ ", " ██║ ", " ╚═╝ "),
    )
    lines = ["".join(cols[c][r] for c in range(3)) for r in range(6)]
    inner = max(len(x) for x in lines) + 8
    bw = inner + 2
    bar = "─" * bw
    out: list[str] = [
        "",
        f"[bold $primary]╭{bar}╮[/]",
    ]
    for ln in lines:
        out.append(f"[bold $primary]│[/][bold white]{ln.center(inner)}[/][bold $primary]│[/]")
    out.append(f"[bold $primary]│[/][bold white italic]{'· Cai ·'.center(inner)}[/][bold $primary]│[/]")
    out.append(f"[bold $primary]╰{bar}╯[/]")
    out.append("")
    return "\n".join(out)


# 说明里勿写「[llm]」等方括号：RichLog 会当作样式标记，界面会显示错乱。
_CONTEXT_WINDOW_SOURCE_LABELS: dict[str, str] = {
    "profile": "来自 TOML：models.profile（当前激活 profile 的 context_window）",
    "llm": "来自 TOML：llm.context_window",
    "env": "来自环境变量 CAI_CONTEXT_WINDOW",
    "default": (
        "内置 8192（没找到任何 cai-agent.toml）。可用以下任一方式让 TUI 读到你的配置："
        " ① 从含 cai-agent.toml 的目录启动；"
        " ② 运行 cai-agent init --global 写一份全局配置到用户目录；"
        " ③ 设置环境变量 CAI_CONFIG 指向已有 TOML；"
        " ④ 启动时用 cai-agent ui --config <path> 或 -w <项目根>。"
    ),
}


class SlashCompletionContext:
    """由 ``CaiAgentApp`` 维护，供 ``SlashCommandSuggester`` 读 profile / MCP / 会话文件名。"""

    __slots__ = ("profile_ids", "mcp_tool_names", "session_paths", "path_roots")

    def __init__(self) -> None:
        self.profile_ids: tuple[str, ...] = ()
        self.mcp_tool_names: tuple[str, ...] = ()
        # 工作区内 .cai-session*.json 基名，mtime 降序（与 list_session_files 一致）
        self.session_paths: tuple[str, ...] = ()
        # 路径补全根目录（workspace + cwd 去重，resolve 后）
        self.path_roots: tuple[Path, ...] = ()


def _parse_mcp_tool_lines(list_text: str) -> list[str]:
    """从 ``mcp_list_tools`` 文本输出中解析工具名（tab 分隔或纯行）。"""
    names: list[str] = []
    for raw in list_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("[") or line.startswith("(无"):
            continue
        if "失败" in line or "异常返回" in line:
            continue
        if "\t" in line:
            name = line.split("\t", 1)[0].strip()
        else:
            name = line
        if name and not name.startswith("["):
            names.append(name)
    return sorted(set(names))


class SlashCommandSuggester(Suggester):
    """输入以 ``/`` 开头时，按静态候选 + 动态 profile / MCP / 会话路径给出灰色续写。"""

    def __init__(
        self,
        candidates: tuple[str, ...] = _SLASH_COMMAND_CANDIDATES,
        *,
        context: SlashCompletionContext | None = None,
    ) -> None:
        # 含 profile / MCP 列表时会变，有 context 时关闭缓存避免陈旧补全。
        super().__init__(use_cache=context is None, case_sensitive=True)
        self._candidates = candidates
        self._ctx = context

    def _dynamic_use_model(self, value: str) -> str | None:
        if self._ctx is None or not value.startswith(_USE_MODEL_PREFIX):
            return None
        for pid in sorted(self._ctx.profile_ids):
            cand = f"{_USE_MODEL_PREFIX}{pid}"
            if cand.startswith(value) and len(cand) > len(value):
                return cand
        return None

    def _dynamic_mcp_call(self, value: str) -> str | None:
        if self._ctx is None or not self._ctx.mcp_tool_names:
            return None
        if not value.startswith(_MCP_CALL_PREFIX):
            return None
        rest = value[len(_MCP_CALL_PREFIX) :]
        if "{" in rest:
            return None
        rest_ls = rest.lstrip()
        toks = rest_ls.split()
        if len(toks) >= 2 and not toks[1].startswith("{"):
            return None
        partial = toks[0] if toks else ""
        for tool in sorted(self._ctx.mcp_tool_names):
            if partial and not tool.startswith(partial):
                continue
            cand = f"{_MCP_CALL_PREFIX}{tool} {{}}"
            if cand.startswith(value) and len(cand) > len(value):
                return cand
        return None

    def _dynamic_load(self, value: str) -> str | None:
        if self._ctx is None or not value.startswith(_LOAD_PREFIX):
            return None
        rest = value[len(_LOAD_PREFIX) :]
        has_path_sep = "/" in rest or "\\" in rest
        if not has_path_sep:
            if _LOAD_LATEST.startswith(value) and len(_LOAD_LATEST) > len(value):
                return _LOAD_LATEST
            for name in self._ctx.session_paths:
                cand = f"{_LOAD_PREFIX}{name}"
                if cand.startswith(value) and len(cand) > len(value):
                    return cand
        if self._ctx.path_roots:
            hit = suggest_path_after_command(
                cmd_prefix=_LOAD_PREFIX,
                line_value=value,
                roots=self._ctx.path_roots,
                filter_json_files_only=True,
            )
            if hit is not None:
                return hit
        return None

    def _dynamic_save(self, value: str) -> str | None:
        if self._ctx is None or not value.startswith(_SAVE_PREFIX):
            return None
        rest = value[len(_SAVE_PREFIX) :]
        has_path_sep = "/" in rest or "\\" in rest
        if not has_path_sep:
            for name in self._ctx.session_paths:
                cand = f"{_SAVE_PREFIX}{name}"
                if cand.startswith(value) and len(cand) > len(value):
                    return cand
        if self._ctx.path_roots:
            hit = suggest_path_after_command(
                cmd_prefix=_SAVE_PREFIX,
                line_value=value,
                roots=self._ctx.path_roots,
                filter_json_files_only=False,
            )
            if hit is not None:
                return hit
        return None

    async def get_suggestion(self, value: str) -> str | None:
        if not value.startswith("/"):
            return None
        # ``/mcp `` 与 ``/mcp refresh`` 同前缀；用户键入空格后更可能想 ``call``。
        if value == "/mcp ":
            return "/mcp call "
        if value == "/models ":
            return "/models refresh"
        for fn in (
            self._dynamic_use_model,
            self._dynamic_mcp_call,
            self._dynamic_load,
            self._dynamic_save,
        ):
            hit = fn(value)
            if hit is not None:
                return hit
        for cand in self._candidates:
            if cand.startswith(value) and len(cand) > len(value):
                return cand
        return None


class SlashAwareInput(Input):
    """在默认 ``Input`` 上增加 Tab：有补全时接受，否则交给焦点环。"""

    BINDINGS = [
        *Input.BINDINGS,
        Binding("tab", "try_tab_complete", "接受补全或切焦点", show=False),
    ]

    def action_try_tab_complete(self) -> None:
        if self.cursor_at_end and self._suggestion:
            self.action_cursor_right()
        elif self.app is not None:
            self.app.action_focus_next()


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
    #cai-brand {
        height: auto;
        margin: 0 1 0 1;
        padding: 0 0 1 0;
        text-align: center;
        background: $boost;
        border: heavy $primary;
        color: $text;
    }
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
    #context-row {
        height: 1;
        margin: 0 1 0 1;
        padding: 0;
    }
    #context-label {
        width: auto;
        height: 1;
        content-align-vertical: middle;
        color: $text-muted;
        padding: 0 1 0 0;
    }
    #context-bar-text {
        width: 1fr;
        height: 1;
        content-align-vertical: middle;
    }
    #user-input {
        margin: 0 1;
    }
    """

    # Textual 原生支持鼠标拖选文本 + Ctrl+C 触发 screen.copy_text；但本应用把
    # Ctrl+C 绑为「停止任务」（终端惯例），所以在这里显式开启 ALLOW_SELECT，
    # 并把复制/全选改绑到 Ctrl+Shift+C / Ctrl+Shift+A，避免与 stop_run 冲突。
    ALLOW_SELECT = True

    BINDINGS = [
        Binding("ctrl+q", "quit", "退出", show=True),
        Binding("ctrl+c", "stop_run", "停止任务", show=True),
        Binding("ctrl+m", "open_model_panel", "聊天模型", show=True),
        Binding("ctrl+b", "open_task_board", "任务看板", show=True),
        Binding(
            "ctrl+shift+c",
            "copy_selected_text",
            "复制",
            show=True,
            tooltip="复制鼠标拖选的文本（聊天区）",
        ),
        Binding(
            "ctrl+shift+a",
            "select_all_chat",
            "全选",
            show=False,
            tooltip="选中整段聊天记录，方便 Ctrl+Shift+C 复制",
        ),
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
        self._stop_requested = False
        self._last_stop_request_at = 0.0
        # Context usage snapshot for the progress bar.
        # ``tokens`` 为实际 / 估算的 prompt_tokens；``is_estimate`` 表示数值来自
        # 字符估算（尚未有真实 API 响应），在界面上显示 "~N" 前缀。
        self._ctx_tokens = 0
        self._ctx_is_estimate = True
        self._slash_ctx = SlashCompletionContext()
        self._slash_suggester = SlashCommandSuggester(context=self._slash_ctx)

        def _progress_sink(payload: dict[str, Any]) -> None:
            self.post_message(ProgressUpdate(payload))

        self._compiled = build_app(
            settings,
            progress=_progress_sink,
            should_stop=lambda: self._stop_requested,
        )
        self._messages: list[dict[str, Any]] = [
            {"role": "system", "content": build_system_prompt(settings)},
        ]
        self._sync_slash_completion_sources()

    def _sync_slash_completion_sources(self) -> None:
        """刷新斜杠补全用的 profile id 与 MCP 工具名（走 mcp_list_tools 缓存，不强制联网）。"""
        profs = getattr(self._settings, "profiles", ()) or ()
        pids = tuple(sorted(p.id for p in profs if getattr(p, "id", None)))
        self._slash_ctx.profile_ids = pids
        tools: list[str] = []
        if getattr(self._settings, "mcp_enabled", False):
            try:
                from cai_agent.tools import dispatch

                txt = dispatch(self._settings, "mcp_list_tools", {"force": False})
                if not txt.startswith("[mcp_list_tools"):
                    tools = _parse_mcp_tool_lines(txt)
            except Exception:
                tools = []
        self._slash_ctx.mcp_tool_names = tuple(tools)
        cwd = (getattr(self._settings, "workspace", None) or ".").strip() or "."
        merged: list[tuple[float, str]] = []
        seen: set[str] = set()
        path_roots_list: list[Path] = []
        try:
            for r in (cwd, "."):
                rp = Path(r).expanduser().resolve()
                key = str(rp)
                if key in seen:
                    continue
                seen.add(key)
                path_roots_list.append(rp)
            self._slash_ctx.path_roots = tuple(path_roots_list)
            for rp in path_roots_list:
                for p in list_session_files(cwd=str(rp), pattern=".cai-session*.json", limit=50):
                    merged.append((p.stat().st_mtime, p.name))
            merged.sort(key=lambda x: x[0], reverse=True)
            out_names: list[str] = []
            dup: set[str] = set()
            for _mt, name in merged:
                if name in dup:
                    continue
                dup.add(name)
                out_names.append(name)
            self._slash_ctx.session_paths = tuple(out_names[:50])
        except Exception:
            self._slash_ctx.session_paths = ()
            self._slash_ctx.path_roots = ()

    def _rebuild_runtime(self) -> None:
        """模型或系统提示策略变化后重建编排器。"""
        def _progress_sink(payload: dict[str, Any]) -> None:
            self.post_message(ProgressUpdate(payload))

        self._compiled = build_app(
            self._settings,
            progress=_progress_sink,
            should_stop=lambda: self._stop_requested,
        )
        self._sync_slash_completion_sources()

    def action_open_task_board(self) -> None:
        self.push_screen(TaskBoardScreen(self._settings))

    def action_open_model_panel(self) -> None:
        if self._agent_busy:
            self.notify(
                "上一轮任务仍在运行，请稍候再打开聊天模型面板。",
                severity="warning",
                timeout=3.5,
            )
            return
        self.push_screen(
            ModelPanelScreen(
                self._settings,
                reload_settings=lambda: Settings.from_env(
                    config_path=self._settings.config_loaded_from,
                    workspace_hint=self._settings.workspace,
                ),
            ),
            self._on_model_panel_closed,
        )

    def _on_model_panel_closed(self, result: str | None) -> None:
        """关闭面板后从磁盘重载配置（拾取面板内 add/edit/rm），Enter 选中则切到该 profile。"""
        log = self.query_one("#chat", RichLog)
        prev_active = self._settings.active_profile_id
        try:
            new_s = Settings.from_env(
                config_path=self._settings.config_loaded_from,
                workspace_hint=self._settings.workspace,
            )
        except Exception:
            new_s = None
        if new_s is not None:
            target = (
                result.strip()
                if isinstance(result, str) and result.strip()
                else prev_active
            )
            prof = next((p for p in new_s.profiles if p.id == target), None)
            if prof is None:
                prof = next(
                    (p for p in new_s.profiles if p.id == new_s.active_profile_id),
                    None,
                )
            if prof is None and new_s.profiles:
                prof = new_s.profiles[0]
            if prof is None:
                return
            self._settings = new_s
            self._apply_profile_switch(prof)
            if isinstance(result, str) and result.strip():
                log.write(
                    f"\n[green]已切换 profile[/] [cyan]{prof.id}[/] "
                    f"（{prof.provider} / {prof.model}）\n",
                )
            return
        if isinstance(result, str) and result.strip():
            prof = next((p for p in self._settings.profiles if p.id == result.strip()), None)
            if prof is not None:
                self._apply_profile_switch(prof)
                log.write(
                    f"\n[green]已切换 profile[/] [cyan]{prof.id}[/] "
                    f"（{prof.provider} / {prof.model}）\n",
                )

    def _apply_profile_switch(self, prof: Profile) -> None:
        """内存中切换到指定 profile（不写 TOML），并重建 graph / 系统提示。"""
        old_provider = self._settings.provider
        self._settings = activate_profile_in_memory(self._settings, prof)
        self._rebuild_runtime()
        self.sub_title = self._settings.workspace
        if self._messages and self._messages[0].get("role") == "system":
            self._messages[0] = {
                "role": "system",
                "content": build_system_prompt(self._settings),
            }
        self._ctx_tokens = 0
        self._ctx_is_estimate = True
        self._refresh_context_bar()
        self._sync_slash_completion_sources()
        if old_provider != self._settings.provider:
            self.query_one("#chat", RichLog).write(
                "\n[yellow]提示[/]：provider 已变更，若上下文异常建议执行 /compact 或 /clear。\n",
            )

    def _apply_session_profile_metadata(self, data: dict[str, Any], log: RichLog) -> None:
        """若会话 JSON 含 ``active_profile_id`` / 路由字段且与当前 profiles 一致，则恢复运行时设置。"""
        profs = tuple(self._settings.profiles or ())

        def _known(pid: str) -> bool:
            return any(p.id == pid for p in profs)

        switched_active = False
        aid = data.get("active_profile_id")
        if not (isinstance(aid, str) and aid.strip()):
            prof_alias = data.get("profile")
            if isinstance(prof_alias, str) and prof_alias.strip():
                aid = prof_alias.strip()
        if isinstance(aid, str) and aid.strip():
            s = aid.strip()
            prof = next((p for p in profs if p.id == s), None)
            if prof is not None:
                self._settings = activate_profile_in_memory(self._settings, prof)
                switched_active = True
            else:
                log.write(
                    f"[dim]会话中的 active_profile_id={s!r} 不在当前配置中，已忽略。[/]\n",
                )

        new_sub = self._settings.subagent_profile_id
        new_pln = self._settings.planner_profile_id
        touched_route = False

        if "subagent_profile_id" in data:
            touched_route = True
            raw = data.get("subagent_profile_id")
            if raw is None or (isinstance(raw, str) and not str(raw).strip()):
                new_sub = None
            elif isinstance(raw, str):
                sid = raw.strip()
                if _known(sid):
                    new_sub = sid
                else:
                    log.write(
                        f"[dim]会话中的 subagent_profile_id={sid!r} 无效，已忽略。[/]\n",
                    )

        if "planner_profile_id" in data:
            touched_route = True
            raw = data.get("planner_profile_id")
            if raw is None or (isinstance(raw, str) and not str(raw).strip()):
                new_pln = None
            elif isinstance(raw, str):
                pid = raw.strip()
                if _known(pid):
                    new_pln = pid
                else:
                    log.write(
                        f"[dim]会话中的 planner_profile_id={pid!r} 无效，已忽略。[/]\n",
                    )

        if touched_route:
            self._settings = replace(
                self._settings,
                subagent_profile_id=new_sub,
                planner_profile_id=new_pln,
            )

        if switched_active or touched_route:
            self._rebuild_runtime()
            if self._messages and self._messages[0].get("role") == "system":
                self._messages[0] = {
                    "role": "system",
                    "content": build_system_prompt(self._settings),
                }
            self._sync_slash_completion_sources()

    @staticmethod
    def _session_summary(messages: list[dict[str, Any]]) -> tuple[int, int, str]:
        turns = 0
        tool_calls = 0
        last_answer = ""
        for m in messages:
            role = m.get("role")
            content = m.get("content")
            if role == "assistant" and isinstance(content, str):
                turns += 1
                if content.strip():
                    last_answer = content.strip()
            if role == "user" and isinstance(content, str):
                try:
                    obj = json.loads(content)
                except Exception:
                    continue
                if isinstance(obj, dict) and isinstance(obj.get("tool"), str):
                    tool_calls += 1
        preview = last_answer[:120] + ("…" if len(last_answer) > 120 else "")
        return turns, tool_calls, preview

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(_cai_brand_markup(), id="cai-brand")
        yield RichLog(id="chat", highlight=True, markup=True, wrap=True, auto_scroll=True)
        with Vertical(id="bottom-stack"):
            with Horizontal(id="context-row"):
                yield Static("", id="context-label")
                yield Static("", id="context-bar-text")
            with Horizontal(id="activity-row"):
                yield LoadingIndicator(id="loader")
                yield Static("", id="activity-status")
            yield SlashAwareInput(
                placeholder=tui_input_placeholder(),
                id="user-input",
                suggester=self._slash_suggester,
            )
        yield Footer()

    def on_mount(self) -> None:
        self.title = "CAI Agent"
        self.sub_title = self._settings.workspace
        self.query_one("#activity-row").display = False
        self._sync_slash_completion_sources()
        self._refresh_context_bar()
        self._print_welcome()

    # ------------------------------------------------------------------
    # Context usage bar
    # ------------------------------------------------------------------
    @staticmethod
    def _render_bar(pct: float, *, width: int = 20) -> str:
        pct = max(0.0, min(1.0, pct))
        filled = int(round(pct * width))
        if filled <= 0 and pct > 0:
            filled = 1  # 非零时至少画一格，视觉上能区分 0 与极小占用
        return "█" * filled + "░" * (width - filled)

    def _refresh_context_bar(self) -> None:
        """Recompute the context progress bar from the latest token count."""
        window = max(1, int(getattr(self._settings, "context_window", 8192) or 8192))
        tokens = max(0, int(self._ctx_tokens or 0))
        if tokens <= 0:
            # 没有任何真实数据也没有估算，用当前 messages 估算一次（含 system prompt）
            tokens = estimate_tokens_from_messages(self._messages)
            self._ctx_is_estimate = True
        pct = tokens / window
        bar = self._render_bar(pct)
        color = "$success"
        if pct >= 0.9:
            color = "$error"
        elif pct >= 0.7:
            color = "$warning"
        prefix = "~" if self._ctx_is_estimate else ""
        text = (
            f"[{color}]{bar}[/] "
            f"[dim]{prefix}{tokens:,} / {window:,} ({pct * 100:.1f}%)"
            f"{' · 估算' if self._ctx_is_estimate else ''}[/]"
        )
        try:
            pid = (self._settings.active_profile_id or "?").strip()
            if len(pid) > 18:
                pid = pid[:17] + "…"
            self.query_one("#context-label", Static).update(f"{pid} · 上下文")
            self.query_one("#context-bar-text", Static).update(text)
        except Exception:
            # Widget 在极早期（compose 之前）可能尚未挂载，忽略即可。
            pass

    def _print_welcome(self) -> None:
        log = self.query_one("#chat", RichLog)
        cw = int(getattr(self._settings, "context_window", 8192) or 8192)
        src = str(getattr(self._settings, "context_window_source", "default"))
        src_label = _CONTEXT_WINDOW_SOURCE_LABELS.get(src, src)
        cfg_path = getattr(self._settings, "config_loaded_from", None) or "未找到 TOML（用内置默认）"
        mock_line = ""
        if self._settings.mock:
            mock_line = "[yellow]Mock LLM 已开启（不真实请求模型）[/]\n"
        log.write(
            f"[bold]CAI Agent {__version__}[/] — LangGraph 会话\n"
            f"工作区: [cyan]{self._settings.workspace}[/]\n"
            f"当前 profile: [cyan]{self._settings.active_profile_id}[/]\n"
            f"模型: [cyan]{self._settings.model}[/]  "
            f"API: [dim]{self._settings.base_url}[/]\n"
            f"配置: [dim]{cfg_path}[/]\n"
            f"上下文窗口: [cyan]{cw:,}[/] tokens  [dim]({src_label})[/]\n"
            f"{mock_line}"
            "[dim]Ctrl+M 聊天模型 · Ctrl+C 停止 · Ctrl+Q 退出[/]\n"
            "[dim]复制：鼠标拖选聊天区 → Ctrl+Shift+C 复制；Ctrl+Shift+A 全选。"
            "Windows Terminal 里也可按住 Shift 用鼠标拖选走系统原生选择。[/]\n"
            + tui_workbench_cheatsheet_rich(leading_nl=True),
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
        if phase == "stopped":
            return "[red]停止[/] 用户手动中断"
        return ""

    def action_copy_selected_text(self) -> None:
        """复制当前屏幕上的文本选区到剪贴板。

        优先级：屏幕级 ``get_selected_text``（含 Input / 聊天区混合）→
        若没有选区则给用户一个提示。
        """
        try:
            selection = self.screen.get_selected_text()
        except Exception:
            selection = None
        if not selection:
            self.notify(
                "没有选中文本。用鼠标拖选聊天区内容，或按 Ctrl+Shift+A 全选，再 Ctrl+Shift+C 复制。",
                severity="information",
                timeout=3.5,
            )
            return
        try:
            self.copy_to_clipboard(selection)
        except Exception as e:
            self.notify(f"复制失败：{e!r}", severity="error", timeout=3.5)
            return
        n = len(selection)
        self.notify(f"已复制 {n:,} 个字符到剪贴板", severity="information", timeout=2.0)

    def action_select_all_chat(self) -> None:
        """全选聊天区（RichLog）所有可见文本，便于一键整段拷走。"""
        try:
            log = self.query_one("#chat", RichLog)
        except Exception:
            return
        try:
            log.text_select_all()
        except Exception as e:
            self.notify(f"全选失败：{e!r}", severity="error", timeout=3.5)
            return
        self.notify(
            "已全选聊天区，按 Ctrl+Shift+C 复制；Esc 或点击其它区域取消选区。",
            severity="information",
            timeout=2.5,
        )

    def action_stop_run(self) -> None:
        if not self._agent_busy:
            self.notify("当前没有正在运行的任务。", severity="information", timeout=2.5)
            return
        now = time.monotonic()
        # Two-stage stop:
        # first request asks for graceful stop; second request within 2s exits app.
        if self._stop_requested and (now - self._last_stop_request_at) <= 2.0:
            self.query_one("#chat", RichLog).write("\n[bold red]强制中断[/] 正在退出…\n")
            self.exit()
            return
        self._stop_requested = True
        self._last_stop_request_at = now
        self.query_one("#chat", RichLog).write("\n[dim]已请求停止：等待当前步骤结束…[/]\n")
        self.notify("已请求停止，再按一次 Ctrl+C 可强制退出", severity="warning", timeout=3.2)

    def on_progress_update(self, event: ProgressUpdate) -> None:
        payload = event.payload or {}
        if payload.get("phase") == "usage":
            pt = int(payload.get("prompt_tokens") or 0)
            # 服务器返回的 prompt_tokens 才是"当前上下文的真实占用"。
            # completion_tokens 属于"本轮新产生的回复"，不计入下一轮进条，
            # 因为它会以 assistant content 的形式进到 messages，下一轮的
            # prompt_tokens 会自然包含它。
            if pt > 0:
                self._ctx_tokens = pt
                self._ctx_is_estimate = False
                self._refresh_context_bar()
            return
        self._phase_detail = self._format_phase_line(payload)

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
            # 再 best-effort 同步一次 usage。通常 graph.llm_node 已经通过
            # "usage" 阶段把真实值投递过来；这里做个兜底，防止 worker 异常
            # 退出时 UI 停留在旧值。
            snap = get_last_usage()
            pt = int(snap.get("prompt_tokens") or 0)
            if pt > 0:
                self._ctx_tokens = pt
                self._ctx_is_estimate = False
            self._refresh_context_bar()
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
        if self._agent_busy and raw not in ("/help", "/?", "/tasks", "/mcp-presets", "/stop"):
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
                "[dim]输入 / 时显示灰色补全；光标在末尾时按 Tab 或 →（右方向键）接受。[/]\n"
                "[dim]/use-model 、 /mcp call 、 /load 、 /save：profile / MCP / 会话基名；路径里含 / 或 \\ 时用路径补全（限 workspace 与 cwd，不可跳出根目录）。[/]\n"
                "/help — 本帮助\n"
                "/status — 当前模型、工作区与配置来源\n"
                "/models — 打开聊天 LLM profile 面板（Ctrl+M；Enter 切换、a/e/d/t 子动作写回 TOML 见面板说明）\n"
                "/models refresh — 拉取当前代理 GET /v1/models 列表到聊天区\n"
                "/mcp — 拉取 MCP 工具列表（缓存）\n"
                "/mcp refresh — 强制刷新 MCP 工具列表\n"
                "/mcp call <name> <json_args> — 调用 MCP 工具\n"
                "/mcp-presets — WebSearch·Notebook MCP 文档与自检命令（与任务看板底部同段）\n"
                "/fix-build — 载入并执行 fix-build 命令模板\n"
                "/security-scan — 载入并执行 security-scan 命令模板\n"
                "/save <path> — 保存当前会话为 JSON（不传 path 则自动命名；/save 后可补全已有会话文件）\n"
                "/load <path|latest> — 从 JSON 加载会话（若文件含 active_profile_id 等字段且与当前配置一致则恢复运行时 profile）\n"
                "/sessions — 列出最近会话文件\n"
                "/tasks — 只读任务看板：调度任务 + 最近 workflow 快照（Ctrl+B）\n"
                "/use-model <profile_id|model_id> — 临时切换模型（补全优先 profile id）\n"
                "/reload — 重新从磁盘生成系统提示（项目说明 / Git）\n"
                "/stop — 停止当前运行中的任务\n"
                "/clear — 清空对话并重建系统提示\n"
                "其他以 / 开头会提示未知命令。\n"
                + tui_workbench_cheatsheet_rich(leading_nl=True)
                + "\n[bold]快捷键[/]\n"
                "[dim]Ctrl+M 聊天模型 · Ctrl+B 任务看板 · Ctrl+C 停止 · Ctrl+Q 退出[/]\n"
                "[dim]复制：鼠标拖选聊天区 → Ctrl+Shift+C；Ctrl+Shift+A 全选当前聊天区。[/]\n"
                "[dim]Windows Terminal：按住 Shift + 鼠标拖选可走系统原生选择并 Ctrl+C 复制。[/]\n"
                + format_tui_mcp_web_notebook_quickstart()
                + "\n",
            )
            return

        if raw == "/status":
            s = self._settings
            cfg = s.config_loaded_from or "（无 TOML）"
            cw = int(getattr(s, "context_window", 8192) or 8192)
            src = str(getattr(s, "context_window_source", "default"))
            sub = getattr(s, "subagent_profile_id", None)
            pln = getattr(s, "planner_profile_id", None)
            contract = build_profile_contract_payload(
                s.profiles,
                profiles_explicit=bool(getattr(s, "profiles_explicit", False)),
                active_profile_id=s.active_profile_id,
                subagent_profile_id=sub,
                planner_profile_id=pln,
            )
            route_lines = (
                f"profile: [cyan]{s.active_profile_id}[/]\n"
                f"profile(active): [cyan]{s.active_profile_id}[/]\n"
                f"subagent: [cyan]{sub or '（未设置，沿用 active）'}[/]\n"
                f"planner: [cyan]{pln or '（未设置，沿用 active）'}[/]\n"
                f"profile_contract: [cyan]{contract.get('source_kind')}[/] "
                f"(migration={contract.get('migration_state')})\n"
            )
            self.query_one("#chat", RichLog).write(
                f"\n[bold]状态[/]\n"
                f"{route_lines}"
                f"提供方: [cyan]{s.provider}[/]\n"
                f"工作区: [cyan]{s.workspace}[/]\n"
                f"模型: [cyan]{s.model}[/]\n"
                f"API: [dim]{s.base_url}[/]\n"
                f"温度: {s.temperature}  HTTP超时: {s.llm_timeout_sec}s\n"
                f"上下文窗口: [cyan]{cw:,}[/] tokens\n"
                f"  source=[cyan]{src}[/] — [dim]{_CONTEXT_WINDOW_SOURCE_LABELS.get(src, src)}[/]\n"
                f"配置: [dim]{cfg}[/]\n"
                f"project_context={s.project_context}  git_context={s.git_context}\n"
                f"mcp_enabled={s.mcp_enabled}  mcp_url={s.mcp_base_url or '(none)'}\n"
                + format_tui_mcp_web_notebook_quickstart()
                + "\n",
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
            self._sync_slash_completion_sources()
            return

        if raw in ("/fix-build", "/security-scan"):
            cmd_name = raw.lstrip("/")
            cmd_text = load_command_text(self._settings, cmd_name)
            log = self.query_one("#chat", RichLog)
            if not cmd_text:
                log.write(f"\n[red]命令模板不存在:[/] /{cmd_name}\n")
                return
            skill_texts = load_related_skill_texts(
                self._settings,
                cmd_name,
                goal_hint=f"/{cmd_name}",
            )
            skill_block = ""
            if skill_texts:
                skill_block = (
                    "\n\n下面是自动匹配到的相关技能，请在执行中参考：\n\n"
                    + "\n\n---\n\n".join(skill_texts)
                )
            rendered_goal = (
                f"你当前正在执行命令 /{cmd_name}。\n"
                "请严格参考下方命令模板完成任务：\n\n"
                f"{cmd_text}{skill_block}"
            )
            # 走统一执行路径：将模板渲染后的目标塞回输入处理，避免复制粘贴运行逻辑。
            raw = rendered_goal

        if raw == "/models refresh":
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

        if raw == "/models":
            self.action_open_model_panel()
            return

        if raw == "/mcp-presets":
            self.query_one("#chat", RichLog).write(format_tui_mcp_web_notebook_quickstart() + "\n")
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
                self._sync_slash_completion_sources()
            return

        if raw == "/mcp refresh":
            from cai_agent.tools import dispatch

            log = self.query_one("#chat", RichLog)
            try:
                text = dispatch(self._settings, "mcp_list_tools", {"force": True})
            except Exception as e:
                log.write(f"\n[bold red]MCP 刷新失败[/]\n{e!r}\n")
                return
            if text.startswith("[mcp_list_tools 失败]"):
                log.write(f"\n[bold red]MCP 刷新失败[/]\n{text}\n")
            else:
                log.write(f"\n[bold]MCP 工具列表（强制刷新）[/]\n{text}\n")
                self._sync_slash_completion_sources()
            return

        if raw.startswith("/mcp call "):
            from cai_agent.tools import dispatch

            log = self.query_one("#chat", RichLog)
            rest = raw[len("/mcp call ") :].strip()
            if not rest:
                log.write("\n[red]用法错误:[/] /mcp call <name> <json_args>\n")
                return
            parts = rest.split(maxsplit=1)
            name = parts[0].strip()
            args_text = parts[1].strip() if len(parts) > 1 else "{}"
            try:
                call_args = json.loads(args_text)
                if not isinstance(call_args, dict):
                    log.write("\n[red]参数错误:[/] json_args 必须是 JSON 对象\n")
                    return
            except Exception as e:
                log.write(f"\n[red]JSON 解析失败:[/] {e}\n")
                return
            try:
                text = dispatch(
                    self._settings,
                    "mcp_call_tool",
                    {"name": name, "args": call_args},
                )
            except Exception as e:
                log.write(f"\n[bold red]MCP 调用失败[/]\n{e!r}\n")
                return
            log.write(f"\n[bold]MCP 调用结果[/] tool={name}\n{text}\n")
            return

        if raw.startswith("/use-model"):
            parts = raw.split(maxsplit=1)
            if len(parts) != 2 or not parts[1].strip():
                self.query_one("#chat", RichLog).write(
                    "\n[red]用法错误:[/] /use-model <profile_id|model_id>\n",
                )
                return
            arg = parts[1].strip()
            log = self.query_one("#chat", RichLog)
            prof = next((p for p in self._settings.profiles if p.id == arg), None)
            if prof is not None:
                self._apply_profile_switch(prof)
                log.write(
                    f"\n[green]已切换 profile[/] [cyan]{prof.id}[/] "
                    f"（{prof.provider} / {prof.model}）\n",
                )
            else:
                self._settings = replace(self._settings, model=arg)
                self._rebuild_runtime()
                self.sub_title = self._settings.workspace
                if self._messages and self._messages[0].get("role") == "system":
                    self._messages[0] = {
                        "role": "system",
                        "content": build_system_prompt(self._settings),
                    }
                log.write(f"\n[green]已切换模型[/] [cyan]{arg}[/]（同 profile 下仅改 model）\n")
                self._ctx_tokens = 0
                self._ctx_is_estimate = True
                self._refresh_context_bar()
                self._sync_slash_completion_sources()
            return

        if raw == "/save" or raw.startswith("/save "):
            p = raw[len("/save ") :].strip() if raw.startswith("/save ") else ""
            if not p:
                ts = datetime.now().strftime("%Y%m%d-%H%M%S")
                p = f".cai-session-{ts}.json"
            payload = {
                "version": 2,
                "workspace": self._settings.workspace,
                "config": self._settings.config_loaded_from,
                "provider": self._settings.provider,
                "model": self._settings.model,
                "profile": self._settings.active_profile_id,
                "active_profile_id": self._settings.active_profile_id,
                "subagent_profile_id": self._settings.subagent_profile_id,
                "planner_profile_id": self._settings.planner_profile_id,
                "mcp_enabled": self._settings.mcp_enabled,
                "messages": self._messages,
                "answer": "",
            }
            try:
                save_session(p, payload)
            except Exception as e:
                self.query_one("#chat", RichLog).write(f"\n[bold red]保存失败[/]\n{e!r}\n")
                return
            self.query_one("#chat", RichLog).write(f"\n[green]已保存会话[/] {p}\n")
            self._sync_slash_completion_sources()
            return

        if raw.startswith("/load "):
            p = raw[len("/load ") :].strip()
            if not p:
                self.query_one("#chat", RichLog).write("\n[red]用法错误:[/] /load <path>\n")
                return
            if p == "latest":
                recent = list_session_files(cwd=".", pattern=".cai-session*.json", limit=1)
                if not recent:
                    self.query_one("#chat", RichLog).write("\n[yellow]未找到会话文件[/]\n")
                    return
                p = str(recent[0])
            try:
                data = load_session(p)
            except Exception as e:
                self.query_one("#chat", RichLog).write(f"\n[bold red]加载失败[/]\n{e!r}\n")
                return
            msgs = data.get("messages")
            if not isinstance(msgs, list) or not msgs:
                self.query_one("#chat", RichLog).write(
                    "\n[bold red]会话格式错误[/] messages 必须是非空数组\n",
                )
                return
            self._messages = list(msgs)
            chat_log = self.query_one("#chat", RichLog)
            chat_log.clear()
            self._ctx_tokens = 0
            self._ctx_is_estimate = True
            self._refresh_context_bar()
            self._apply_session_profile_metadata(data, chat_log)
            self._print_welcome()
            turns, tool_calls, preview = self._session_summary(self._messages)
            self.query_one("#chat", RichLog).write(
                f"\n[green]已加载会话[/] {p}\n[dim]当前消息数: {len(self._messages)}[/]\n",
            )
            self.query_one("#chat", RichLog).write(
                f"[dim]摘要: assistant轮次={turns}  工具调用={tool_calls}[/]\n",
            )
            if preview:
                self.query_one("#chat", RichLog).write(
                    f"[dim]最后回答预览: {preview}[/]\n",
                )
            self.query_one("#chat", RichLog).write(tui_session_continue_one_liner_rich())
            self._sync_slash_completion_sources()
            return

        if raw == "/sessions":
            files = list_session_files(cwd=".", pattern=".cai-session*.json", limit=20)
            if not files:
                self.query_one("#chat", RichLog).write("\n[yellow]未找到会话文件[/]\n")
                return
            lines = []
            for i, f in enumerate(files, start=1):
                st = f.stat()
                mtime = datetime.fromtimestamp(st.st_mtime).strftime("%m-%d %H:%M")
                lines.append(f"{i:>2}. {f.name}  {mtime}  {st.st_size:,} B")
            self.query_one("#chat", RichLog).write(
                "\n[bold]最近会话文件[/]\n"
                + "\n".join(lines)
                + "\n"
                + tui_workbench_cheatsheet_rich(leading_nl=True),
            )
            return

        if raw == "/tasks":
            self.action_open_task_board()
            return

        if raw == "/clear":
            self._messages = [
                {"role": "system", "content": build_system_prompt(self._settings)},
            ]
            self.query_one("#chat", RichLog).clear()
            self.query_one("#activity-row").display = False
            self.query_one("#activity-status", Static).update("")
            self._phase_detail = ""
            self._ctx_tokens = 0
            self._ctx_is_estimate = True
            self._refresh_context_bar()
            self._print_welcome()
            return

        if raw == "/stop":
            self.action_stop_run()
            return

        if raw == "/usage":
            from cai_agent.llm import get_last_usage, get_usage_counters

            c = get_usage_counters()
            lu = get_last_usage()
            self.query_one("#chat", RichLog).write(
                f"\n[bold]/usage[/]\n累计: {c!r}\n最近一轮: {lu!r}\n",
            )
            return

        if raw == "/compress":
            self.notify(
                "已提示：请在下一轮直接让模型「总结当前对话关键结论」；"
                "完整自动压缩将结合 graph compact 策略演进。",
                severity="information",
                timeout=4.0,
            )
            return

        if raw == "/retry":
            self.notify(
                "在 TUI 内可直接再次发送同一任务描述以继续；跨终端请用 CLI "
                "`cai-agent continue …`。快照请用 /save、/load。",
                severity="information",
                timeout=4.5,
            )
            return

        if raw == "/undo":
            self.notify(
                "撤销尚未全自动接入；可用 /clear 清空本轮或手动编辑会话 JSON。",
                severity="warning",
                timeout=4.5,
            )
            return

        if raw == "/personality":
            import os

            p = (os.environ.get("CAI_PERSONALITY") or "").strip()
            default_personality_hint = '(未设置 CAI_PERSONALITY；export CAI_PERSONALITY="…" 后 /reload)'
            self.query_one("#chat", RichLog).write(
                f"\n[bold]/personality[/]\n"
                f"{p or default_personality_hint}\n",
            )
            return

        if raw.startswith("/"):
            log_u = self.query_one("#chat", RichLog)
            log_u.write(f"[red]未知命令:[/] {raw}（[dim]/help[/] 查看全部命令）\n")
            hint = _slash_typo_hint(raw)
            if hint:
                log_u.write(hint + "\n")
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

        # 按 Enter 后立即用 CJK 加权估算器重算一次进度条，带上新 user 消息。
        # 等 usage 阶段回来会用服务端真实 prompt_tokens 覆盖；但如果响应较慢，
        # 这一步至少让用户看到 "输入变长 → 进度条同步变化"，不会给人"僵死"感。
        pre_est = estimate_tokens_from_messages(msgs)
        if pre_est > 0:
            self._ctx_tokens = pre_est
            self._ctx_is_estimate = True
            self._refresh_context_bar()

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
        self._stop_requested = False
        self._last_stop_request_at = 0.0
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
