from __future__ import annotations

import io
import json
import os
import time
import unittest
from datetime import UTC, datetime
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cai_agent.__main__ import main
from cai_agent.memory import build_memory_health_payload
from cai_agent.session import save_session


class MemoryHealthCliTests(unittest.TestCase):
    def test_health_empty_workspace_json(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["memory", "health", "--json"])
            self.assertEqual(rc, 0)
            p = json.loads(buf.getvalue().strip())
            self.assertEqual(p.get("schema_version"), "1.0")
            self.assertEqual(p.get("grade"), "D")
            self.assertEqual(float(p.get("health_score")), 0.0)
            self.assertEqual(float(p.get("freshness")), 0.0)
            self.assertEqual(float(p.get("coverage")), 0.0)
            self.assertIn("conflict_rate", p)
            self.assertIsInstance(p.get("actions"), list)

    def test_health_fail_on_grade_c_exits_2_when_d(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["memory", "health", "--json", "--fail-on-grade", "C"])
            self.assertEqual(rc, 2)
            p = json.loads(buf.getvalue().strip())
            self.assertEqual(p.get("grade"), "D")

    def test_health_fail_on_grade_c_exits_0_when_a(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            now = int(time.time())
            mem_dir = root / "memory"
            mem_dir.mkdir(parents=True, exist_ok=True)
            entries = mem_dir / "entries.jsonl"
            ts = datetime.now(UTC).isoformat()
            entries.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "id": "e1",
                                "category": "session",
                                "text": "shared goal alpha\n\nanswer one",
                                "confidence": 0.9,
                                "expires_at": None,
                                "created_at": ts,
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "id": "e2",
                                "category": "session",
                                "text": "shared goal beta\n\ntwo",
                                "confidence": 0.9,
                                "expires_at": None,
                                "created_at": ts,
                            },
                            ensure_ascii=False,
                        ),
                    ],
                )
                + "\n",
                encoding="utf-8",
            )
            for i in range(5):
                p = root / f".cai-session-{i}.json"
                save_session(
                    str(p),
                    {
                        "version": 2,
                        "goal": "shared goal alpha extended",
                        "answer": "ok",
                    },
                )
                os_ts = now - (i * 30)
                os.utime(p, (os_ts, os_ts))

            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "memory",
                            "health",
                            "--json",
                            "--days",
                            "30",
                            "--session-limit",
                            "20",
                            "--fail-on-grade",
                            "C",
                        ],
                    )
            self.assertEqual(rc, 0, buf.getvalue())
            p = json.loads(buf.getvalue().strip())
            self.assertIn(p.get("grade"), ("A", "B"))

    def test_build_memory_health_conflict_pairs(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            now_iso = datetime.now(UTC).isoformat()
            rows = [
                {
                    "id": "a",
                    "category": "session",
                    "text": "hello world foo bar baz",
                    "confidence": 0.5,
                    "expires_at": None,
                    "created_at": now_iso,
                },
                {
                    "id": "b",
                    "category": "session",
                    "text": "hello world foo bar slightly",
                    "confidence": 0.5,
                    "expires_at": None,
                    "created_at": now_iso,
                },
            ]
            mem = root / "memory"
            mem.mkdir(parents=True, exist_ok=True)
            (mem / "entries.jsonl").write_text(
                "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                encoding="utf-8",
            )
            p = build_memory_health_payload(root, conflict_threshold=0.5)
            self.assertGreater(float(p.get("conflict_rate") or 0), 0.0)
            pairs = p.get("conflict_pairs")
            self.assertIsInstance(pairs, list)
            self.assertGreaterEqual(len(pairs), 1)


if __name__ == "__main__":
    unittest.main()
