from __future__ import annotations

import io
import json
import os
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cai_agent.__main__ import main
from cai_agent.session import save_session


class MemoryNudgeCliTests(unittest.TestCase):
    def test_memory_nudge_json_reports_high_when_no_entries(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            now = int(time.time())
            for i in range(8):
                p = root / f".cai-session-{i}.json"
                save_session(
                    str(p),
                    {
                        "version": 2,
                        "goal": f"goal-{i}",
                        "answer": f"answer-{i}",
                    },
                )
                os_ts = now - (i * 60)
                p.touch()
                p.chmod(0o644)
                os.utime(p, (os_ts, os_ts))

            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["memory", "nudge", "--json", "--days", "7", "--session-limit", "20"])
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("schema_version"), "1.0")
            self.assertEqual(payload.get("severity"), "high")
            self.assertGreaterEqual(int(payload.get("recent_sessions") or 0), 8)
            self.assertEqual(int(payload.get("memory_entries") or 0), 0)

    def test_memory_nudge_json_reports_low_with_entries(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            save_session(
                str(root / ".cai-session-a.json"),
                {"version": 2, "goal": "g", "answer": "a"},
            )
            mem_dir = root / "memory"
            mem_dir.mkdir(parents=True, exist_ok=True)
            entries = mem_dir / "entries.jsonl"
            entries.write_text(
                json.dumps(
                    {
                        "id": "e1",
                        "category": "session",
                        "text": "hello",
                        "confidence": 0.7,
                        "expires_at": None,
                        "created_at": "2024-01-01T00:00:00+00:00",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            instincts_dir = mem_dir / "instincts"
            instincts_dir.mkdir(parents=True, exist_ok=True)
            (instincts_dir / "instincts-20240101-000000.md").write_text("# i\n", encoding="utf-8")

            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["memory", "nudge", "--json"])
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("severity"), "low")
            self.assertTrue(payload.get("latest_instinct_path"))

