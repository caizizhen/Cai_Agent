from __future__ import annotations

from cai_agent.tui_session_strip import (
    build_context_label,
    build_profile_switched_line,
    tui_input_placeholder,
    tui_session_continue_one_liner_rich,
    tui_task_board_session_line_rich,
    tui_workbench_cheatsheet_rich,
)


def test_workbench_cheatsheet_covers_tasks_context_continue() -> None:
    s = tui_workbench_cheatsheet_rich(leading_nl=False)
    assert "/tasks" in s
    assert "/recap" in s
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
    assert "/recap" in tui_session_continue_one_liner_rich()


def test_context_label_active_only() -> None:
    label = build_context_label(active_profile_id="primary")
    assert label == "primary · 上下文"


def test_context_label_with_subagent_and_planner() -> None:
    label = build_context_label(
        active_profile_id="primary",
        subagent_profile_id="worker",
        planner_profile_id="planner",
    )
    assert label == "primary · 上下文 · route=sub+pl"


def test_context_label_hides_route_when_same_as_active() -> None:
    label = build_context_label(
        active_profile_id="primary",
        subagent_profile_id="primary",
        planner_profile_id="primary",
    )
    assert "route=" not in label


def test_context_label_migration_warning() -> None:
    label = build_context_label(
        active_profile_id="primary",
        migration_state="needs_explicit_profiles",
    )
    assert "⚠ migration" in label


def test_context_label_ready_migration_no_warning() -> None:
    label = build_context_label(
        active_profile_id="primary",
        migration_state="ready",
    )
    assert "migration" not in label


def test_context_label_truncates_to_max_len() -> None:
    very_long = "x" * 100
    label = build_context_label(
        active_profile_id=very_long,
        subagent_profile_id="sub",
        max_len=30,
    )
    assert len(label) <= 30
    assert label.endswith("…")


def test_profile_switched_line() -> None:
    assert build_profile_switched_line("primary") == "profile_switched: primary"
    assert build_profile_switched_line("") == "profile_switched: ?"
