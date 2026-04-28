"""TUI：任务看板、上下文条、会话继续的统一提示文案（CC-03a / CC-03c）。"""

from __future__ import annotations

_CONTEXT_LABEL_MAX = 80


def _truncate(label: str, *, limit: int = _CONTEXT_LABEL_MAX) -> str:
    s = str(label or "").strip()
    if len(s) <= limit:
        return s
    return s[: limit - 1].rstrip() + "…"


def build_context_label(
    *,
    active_profile_id: str | None,
    subagent_profile_id: str | None = None,
    planner_profile_id: str | None = None,
    migration_state: str | None = None,
    max_len: int = _CONTEXT_LABEL_MAX,
) -> str:
    """TUI ``#context-label`` 的纯文本生成（CC-03b/c）。

    规则：
    - 基础为 ``"<active> · 上下文"``，``active`` 超过 18 字符时按旧逻辑省略号截断。
    - 若存在与 ``active`` 不同的 ``subagent``/``planner``，在同一行追加缩写
      ``· route=sub`` / ``· route=pl`` / ``· route=sub+pl``（仅出现一种组合）。
    - ``migration_state`` 非 ``ready`` 时追加 ``· ⚠ migration``，帮助用户感知配置不完整。
    - 整个标签长度不超过 ``max_len``（默认 **80**），超出时用 ``…`` 截断。
    """
    aid = (active_profile_id or "?").strip() or "?"
    if len(aid) > 18:
        aid = aid[:17] + "…"
    parts: list[str] = [f"{aid} · 上下文"]

    sub = (subagent_profile_id or "").strip() or None
    pln = (planner_profile_id or "").strip() or None
    flags: list[str] = []
    if sub and sub != active_profile_id:
        flags.append("sub")
    if pln and pln != active_profile_id:
        flags.append("pl")
    if flags:
        parts.append(f"· route={'+'.join(flags)}")

    mig = (migration_state or "").strip().lower()
    if mig and mig != "ready":
        parts.append("· ⚠ migration")

    return _truncate(" ".join(parts), limit=max_len)


def build_profile_switched_line(profile_id: str) -> str:
    """CLI/TUI 共用的 ``profile_switched: <id>`` 一行文案（CC-03c / CC-03b RFC §2）。"""
    pid = str(profile_id or "").strip() or "?"
    return f"profile_switched: {pid}"


def tui_workbench_cheatsheet_rich(*, leading_nl: bool = True) -> str:
    """欢迎页与 /help 共用：任务看板、上下文条、继续会话口径一致。"""
    body = (
        "[bold]工作台[/]\n"
        "[dim]任务与调度：[/][cyan]/tasks[/][dim] 或 [/][cyan]Ctrl+B[/]"
        "[dim]（只读摘要，与 [/][cyan]board[/][dim] / [/][cyan]schedule list[/][dim] 同源）[/]\n"
        "[dim]下方进度条：当前对话 token 占用 vs 上下文窗口（前缀 ~ 表示估算，"
        "收到模型 usage 后为实测）[/]\n"
        "[dim]继续会话：[/]在此直接输入下一条即可；跨终端 CLI 用 "
        "[cyan]cai-agent continue …[/][dim]；快照：[/][cyan]/save[/][dim] · [/][cyan]/load[/]"
        "[dim] · [/][cyan]/load latest[/][dim] · [/][cyan]/sessions[/][dim] · [/][cyan]/recap[/]\n"
    )
    return ("\n" if leading_nl else "") + body


def tui_session_continue_one_liner_rich() -> str:
    """加载会话后一行提示，与欢迎页 / 工作台口径一致。"""
    return (
        "[dim]继续：直接输入下一条 · [/][cyan]/save[/][dim] · [/][cyan]/tasks[/]"
        "[dim] · [/][cyan]/recap[/][dim] · CLI:[/] [cyan]cai-agent continue[/]\n"
    )


def tui_task_board_session_line_rich() -> str:
    """任务看板顶部一行，与会话条口径对齐。"""
    return (
        "[dim]会话继续：本屏直接输入；[/][cyan]/load[/][dim]·[/][cyan]/sessions[/]"
        "[dim]；CLI[/] [cyan]cai-agent continue[/]"
    )


def tui_input_placeholder() -> str:
    return (
        "输入以继续会话，或 /命令 · Tab/→ 补全 · /help · Ctrl+M 模型 · Ctrl+B 任务"
    )
