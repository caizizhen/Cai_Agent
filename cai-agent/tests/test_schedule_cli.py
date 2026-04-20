from __future__ import annotations

import io
import json
import os
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cai_agent.__main__ import main


class ScheduleCliTests(unittest.TestCase):
    def test_add_list_rm_cycle(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            buf_add = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf_add):
                    rc_add = main(
                        [
                            "schedule",
                            "add",
                            "--goal",
                            "daily audit",
                            "--every-minutes",
                            "5",
                            "--disabled",
                            "--json",
                        ],
                    )
            self.assertEqual(rc_add, 0)
            created = json.loads(buf_add.getvalue().strip())
            self.assertEqual(created.get("goal"), "daily audit")
            self.assertEqual(created.get("enabled"), False)

            buf_list = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf_list):
                    rc_list = main(["schedule", "list", "--json"])
            self.assertEqual(rc_list, 0)
            arr = json.loads(buf_list.getvalue().strip())
            self.assertEqual(len(arr), 1)
            sid = arr[0]["id"]

            buf_rm = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf_rm):
                    rc_rm = main(["schedule", "rm", sid, "--json"])
            self.assertEqual(rc_rm, 0)
            payload = json.loads(buf_rm.getvalue().strip())
            self.assertEqual(payload.get("removed"), True)

    def test_run_due_dry_run_and_mark(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            # Due every minute.
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                main(
                    [
                        "schedule",
                        "add",
                            "--goal",
                            "echo hello",
                            "--every-minutes",
                            "1",
                            "--json",
                        ],
                    )

            buf_dry = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf_dry):
                    rc_dry = main(["schedule", "run-due", "--json"])
            self.assertEqual(rc_dry, 0)
            dry = json.loads(buf_dry.getvalue().strip())
            self.assertEqual(dry.get("mode"), "dry-run")
            self.assertTrue((dry.get("due_jobs") or []))
            self.assertEqual((dry.get("executed") or []), [])

            # Execute mode currently only marks schedule records.
            buf_exec = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf_exec):
                    rc_exec = main(["schedule", "run-due", "--json", "--execute"])
            self.assertEqual(rc_exec, 0)
            ex = json.loads(buf_exec.getvalue().strip())
            self.assertEqual(ex.get("mode"), "execute")
            self.assertTrue((ex.get("executed") or []))

