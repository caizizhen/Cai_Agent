"""TUI：任务看板、上下文条、会话继续的统一提示文案（CC-03a）。"""

from __future__ import annotations


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
        "[dim] · [/][cyan]/load latest[/][dim] · [/][cyan]/sessions[/]\n"
    )
    return ("\n" if leading_nl else "") + body


def tui_session_continue_one_liner_rich() -> str:
    """加载会话后一行提示，与欢迎页 / 工作台口径一致。"""
    return (
        "[dim]继续：直接输入下一条 · [/][cyan]/save[/][dim] · [/][cyan]/tasks[/]"
        "[dim] · CLI:[/] [cyan]cai-agent continue[/]\n"
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
