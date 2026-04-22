from __future__ import annotations

import json
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cai_agent.__main__ import main
from cai_agent.schedule import (
    add_schedule_task,
    enrich_schedule_tasks_for_display,
    list_schedule_tasks,
    schedule_dependency_graph_has_cycle,
)


class ScheduleDependsS403Tests(unittest.TestCase):
    def test_cycle_detection_two_node(self) -> None:
        rows = [
            {"id": "a", "depends_on": ["b"]},
            {"id": "b", "depends_on": ["a"]},
        ]
        self.assertTrue(schedule_dependency_graph_has_cycle(rows))

    def test_cycle_detection_self_loop(self) -> None:
        rows = [{"id": "x", "depends_on": ["x"]}]
        self.assertTrue(schedule_dependency_graph_has_cycle(rows))

    def test_add_rejects_when_new_edge_completes_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            a = add_schedule_task(goal="ga", every_minutes=1, cwd=str(root))
            aid = str(a.get("id") or "")
            b = add_schedule_task(goal="gb", every_minutes=1, depends_on=[aid], cwd=str(root))
            bid = str(b.get("id") or "")
            p = root / ".cai-schedule.json"
            doc = json.loads(p.read_text(encoding="utf-8"))
            for t in doc.get("tasks") or []:
                if isinstance(t, dict) and str(t.get("id")) == aid:
                    t["depends_on"] = [bid]
                    break
            p.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                add_schedule_task(goal="gc", every_minutes=1, cwd=str(root))
            self.assertIn("环", str(ctx.exception))

    def test_enrich_list_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            a = add_schedule_task(goal="upstream", every_minutes=1, cwd=str(root))
            aid = str(a.get("id") or "")
            b = add_schedule_task(goal="down", every_minutes=1, depends_on=[aid], cwd=str(root))
            bid = str(b.get("id") or "")
            raw = list_schedule_tasks(str(root))
            enriched = enrich_schedule_tasks_for_display(raw)
            self.assertEqual(len(enriched), 2)
            down = next(x for x in enriched if str(x.get("goal")) == "down")
            self.assertTrue(down.get("dependency_blocked"))
            self.assertIn("(", str(down.get("depends_on_chain") or ""))
            up = next(x for x in enriched if str(x.get("goal")) == "upstream")
            self.assertEqual(up.get("dependents"), [bid])

    def test_cli_add_cycle_json_error(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                rc1 = main(
                    [
                        "schedule",
                        "add",
                        "--goal",
                        "t1",
                        "--every-minutes",
                        "1",
                        "--json",
                    ],
                )
                self.assertEqual(rc1, 0)
                j1 = json.loads((root / ".cai-schedule.json").read_text(encoding="utf-8"))
                tid = str(j1["tasks"][0]["id"])
                rc2 = main(
                    [
                        "schedule",
                        "add",
                        "--goal",
                        "t2",
                        "--every-minutes",
                        "1",
                        "--depends-on",
                        tid,
                        "--json",
                    ],
                )
                self.assertEqual(rc2, 0)
                j2 = json.loads((root / ".cai-schedule.json").read_text(encoding="utf-8"))
                tid2 = str(j2["tasks"][1]["id"])
                doc = json.loads((root / ".cai-schedule.json").read_text(encoding="utf-8"))
                for t in doc.get("tasks") or []:
                    if isinstance(t, dict) and str(t.get("id")) == tid:
                        t["depends_on"] = [tid2]
                        break
                (root / ".cai-schedule.json").write_text(
                    json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc3 = main(
                        [
                            "schedule",
                            "add",
                            "--goal",
                            "t3",
                            "--every-minutes",
                            "1",
                            "--json",
                        ],
                    )
            self.assertEqual(rc3, 2)
            err = json.loads(buf.getvalue().strip())
            self.assertEqual(err.get("schema_version"), "schedule_add_invalid_v1")
            self.assertEqual(err.get("error"), "schedule_add_invalid")


if __name__ == "__main__":
    unittest.main()
