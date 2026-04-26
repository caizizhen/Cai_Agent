from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path


def _load_script():
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts" / "finalize_task.py"
    spec = importlib.util.spec_from_file_location("finalize_task_script", script)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_update_next_actions_moves_done_row() -> None:
    mod = _load_script()
    root = Path(__file__).resolve().parents[2]
    tmp_path = root / ".tmp-tests-finalize-script"
    if tmp_path.exists():
        shutil.rmtree(tmp_path, ignore_errors=True)
    next_actions = tmp_path / "docs" / "NEXT_ACTIONS.zh-CN.md"
    archive = tmp_path / "docs" / "COMPLETED_TASKS_ARCHIVE.zh-CN.md"
    test_todos = tmp_path / "docs" / "TEST_TODOS.zh-CN.md"
    qa_runs = tmp_path / "docs" / "qa" / "runs"
    next_actions.parent.mkdir(parents=True)
    next_actions.write_text(
        """# NEXT_ACTIONS.zh-CN.md

> 最后同步：2026-04-01。状态来源：x。

## 现在做

| 顺位 | ID | 状态 | 目标 | 主要入口 | 最小验证 |
|---|---|---|---|---|---|
| 1 | `TASK-1` | Ready | old | file.py | pytest |
| 2 | `TASK-2` | Ready | keep | file.py | pytest |

## 刚完成

| ID | 完成日期 | 结果 | 验证/证据 |
|---|---|---|---|
""",
        encoding="utf-8",
    )
    archive.write_text("# Archive\n", encoding="utf-8")
    test_todos.write_text("# Tests\n", encoding="utf-8")
    old_next, old_archive, old_test, old_qa = mod.NEXT_ACTIONS, mod.ARCHIVE, mod.TEST_TODOS, mod.QA_RUNS
    try:
        mod.NEXT_ACTIONS = next_actions
        mod.ARCHIVE = archive
        mod.TEST_TODOS = test_todos
        mod.QA_RUNS = qa_runs
        mod.update_next_actions(
            task_ids=["TASK-1"],
            summary="done summary",
            verification=["pytest ok"],
            date="2026-04-26",
            next_row=None,
        )
        mod.append_archive(task_ids=["TASK-1"], summary="done summary", verification=["pytest ok"], date="2026-04-26")
        qa_path = mod.write_qa_run(
            task_ids=["TASK-1"],
            summary="done summary",
            verification=["pytest ok"],
            date="2026-04-26",
        )
        mod.append_test_todos(
            task_ids=["TASK-1"],
            verification=["pytest ok"],
            qa_path=qa_path,
            date="2026-04-26",
        )

        updated = next_actions.read_text(encoding="utf-8")
        assert "| 1 | `TASK-1` | Ready | old | file.py | pytest |" not in updated
        assert "| 2 | `TASK-2` | Ready | keep | file.py | pytest |" in updated
        assert "| `TASK-1` | 2026-04-26 | done summary | pytest ok |" in updated
        assert "`TASK-1`" in archive.read_text(encoding="utf-8")
        assert "`TASK-1`" in test_todos.read_text(encoding="utf-8")
        assert qa_path.is_file()
    finally:
        mod.NEXT_ACTIONS = old_next
        mod.ARCHIVE = old_archive
        mod.TEST_TODOS = old_test
        mod.QA_RUNS = old_qa
        shutil.rmtree(tmp_path, ignore_errors=True)
