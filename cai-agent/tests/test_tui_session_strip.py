from __future__ import annotations

from cai_agent.tui_session_strip import (
    tui_input_placeholder,
    tui_session_continue_one_liner_rich,
    tui_task_board_session_line_rich,
    tui_workbench_cheatsheet_rich,
)


def test_workbench_cheatsheet_covers_tasks_context_continue() -> None:
    s = tui_workbench_cheatsheet_rich(leading_nl=False)
    assert "/tasks" in s
    assert "Ctrl+B" in s
    assert "cai-agent continue" in s
    assert "进度条" in s or "token" in s


def test_placeholder_mentions_continue_and_tasks() -> None:
    p = tui_input_placeholder()
    assert "继续" in p or "会话" in p
    assert "Ctrl+B" in p


def test_task_board_line() -> None:
    assert "continue" in tui_task_board_session_line_rich()


def test_one_liner_after_load() -> None:
    assert "/save" in tui_session_continue_one_liner_rich()
