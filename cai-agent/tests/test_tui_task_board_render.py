from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from cai_agent.tui_task_board import render_task_board_markup


class TuiTaskBoardRenderTests(unittest.TestCase):
    def test_empty_workspace_contains_board_aligned_sections(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            s = MagicMock()
            s.workspace = td
            out = render_task_board_markup(s)
            self.assertIn("board 同源", out)
            self.assertIn("observe", out)
            self.assertIn(".cai-schedule", out)
            self.assertIn("last-workflow", out)

    def test_schedule_enrich_shows_dependency_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sched = {
                "schema_version": "1.0",
                "tasks": [
                    {
                        "id": "parent",
                        "goal": "parent goal",
                        "every_minutes": 5,
                        "enabled": True,
                        "last_status": "completed",
                    },
                    {
                        "id": "child",
                        "goal": "child goal",
                        "every_minutes": 10,
                        "enabled": True,
                        "depends_on": ["parent"],
                        "last_status": "pending",
                    },
                ],
            }
            (root / ".cai-schedule.json").write_text(
                json.dumps(sched, ensure_ascii=False),
                encoding="utf-8",
            )
            s = MagicMock()
            s.workspace = str(root)
            out = render_task_board_markup(s)
            self.assertIn("parent", out)
            self.assertIn("child", out)
            self.assertIn("dependents:", out)
            self.assertIn("depends_on:", out)
            self.assertIn("chain=", out)
