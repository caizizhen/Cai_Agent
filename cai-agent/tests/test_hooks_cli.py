from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cai_agent.__main__ import main


class HooksCliTests(unittest.TestCase):
    def test_hooks_list_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = root / "cai-agent.toml"
            cfg.write_text(
                "[llm]\nbase_url = \"http://x/v1\"\nmodel = \"m\"\napi_key = \"k\"\n",
                encoding="utf-8",
            )
            hooks_dir = root / "hooks"
            hooks_dir.mkdir(parents=True, exist_ok=True)
            (hooks_dir / "hooks.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "hooks": [
                            {
                                "id": "h1",
                                "event": "observe_start",
                                "enabled": True,
                                "command": [sys.executable, "-c", "print(1)"],
                            },
                            {
                                "id": "h2",
                                "event": "workflow_start",
                                "enabled": False,
                                "command": [sys.executable, "-c", "print(2)"],
                            },
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["hooks", "--config", str(cfg), "list", "--json"])
            self.assertEqual(rc, 0)
            doc = json.loads(buf.getvalue().strip())
            self.assertEqual(doc.get("schema_version"), "hooks_catalog_v1")
            self.assertIn("hooks_file", doc)
            rows = doc.get("hooks")
            self.assertIsInstance(rows, list)
            self.assertEqual(len(rows), 2)

    def test_hooks_list_json_missing_hooks_returns_2(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = root / "cai-agent.toml"
            cfg.write_text(
                "[llm]\nbase_url = \"http://x/v1\"\nmodel = \"m\"\napi_key = \"k\"\n",
                encoding="utf-8",
            )
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["hooks", "--config", str(cfg), "list", "--json"])
            self.assertEqual(rc, 2)
            doc = json.loads(buf.getvalue().strip())
            self.assertEqual(doc.get("error"), "hooks_json_not_found")

    def test_hooks_run_event_dry_run_and_execute(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = root / "cai-agent.toml"
            cfg.write_text(
                "[llm]\nbase_url = \"http://x/v1\"\nmodel = \"m\"\napi_key = \"k\"\n",
                encoding="utf-8",
            )
            hooks_dir = root / ".cai" / "hooks"
            hooks_dir.mkdir(parents=True, exist_ok=True)
            (hooks_dir / "hooks.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "hooks": [
                            {
                                "id": "echo-hook",
                                "event": "observe_start",
                                "enabled": True,
                                "command": [sys.executable, "-c", "print(99)"],
                            },
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            buf1 = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf1):
                    rc1 = main(
                        [
                            "hooks",
                            "--config",
                            str(cfg),
                            "run-event",
                            "observe_start",
                            "--dry-run",
                            "--json",
                        ],
                    )
            self.assertEqual(rc1, 0)
            d1 = json.loads(buf1.getvalue().strip())
            self.assertEqual(d1.get("schema_version"), "hooks_run_event_result_v1")
            self.assertTrue(d1.get("dry_run"))
            res1 = d1.get("results")
            self.assertIsInstance(res1, list)
            self.assertEqual(len(res1), 1)
            self.assertEqual(res1[0].get("status"), "planned")

            buf2 = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf2):
                    rc2 = main(
                        [
                            "hooks",
                            "--config",
                            str(cfg),
                            "run-event",
                            "observe_start",
                            "--payload",
                            "{\"x\":1}",
                            "--json",
                        ],
                    )
            self.assertEqual(rc2, 0)
            d2 = json.loads(buf2.getvalue().strip())
            res2 = d2.get("results")
            self.assertIsInstance(res2, list)
            self.assertEqual(res2[0].get("status"), "ok")


if __name__ == "__main__":
    unittest.main()
