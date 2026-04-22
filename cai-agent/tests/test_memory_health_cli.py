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

    def test_memory_state_json_empty_workspace(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["memory", "state", "--json"])
            self.assertEqual(rc, 0)
            p = json.loads(buf.getvalue().strip())
            self.assertEqual(p.get("schema_version"), "memory_state_eval_v1")
            self.assertIsInstance(p.get("counts"), dict)
            self.assertEqual(int(p.get("total_entries") or 0), 0)

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
            self.assertEqual(p.get("conflict_similarity_metric"), "word_jaccard")
            self.assertGreaterEqual(int(p.get("conflict_pair_count") or 0), 1)

    def test_coverage_denominator_excludes_short_goals(self) -> None:
        """S2-04：coverage = 有命中的会话 / 可评估会话（goal>=8），与 --days 窗口一致。"""
        with TemporaryDirectory() as td:
            root = Path(td)
            now = int(time.time())
            mem = root / "memory"
            mem.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(UTC).isoformat()
            # Two memory rows keyed to two long goals
            g1 = "alpha project milestone one"
            g2 = "beta project milestone two"
            lines = [
                json.dumps(
                    {
                        "id": "m1",
                        "category": "session",
                        "text": f"{g1}\n\nbody",
                        "confidence": 0.8,
                        "expires_at": None,
                        "created_at": ts,
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "id": "m2",
                        "category": "session",
                        "text": f"{g2}\n\nbody",
                        "confidence": 0.8,
                        "expires_at": None,
                        "created_at": ts,
                    },
                    ensure_ascii=False,
                ),
            ]
            (mem / "entries.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
            sessions = [
                (".cai-session-a.json", g1, "a1"),
                (".cai-session-b.json", g2, "b1"),
                (".cai-session-c.json", "short", "c1"),
                (".cai-session-d.json", "tiny", "d1"),
                (".cai-session-e.json", "orphan goal text here", "e1"),
            ]
            for fname, goal, _ in sessions:
                p = root / fname
                save_session(str(p), {"version": 2, "goal": goal, "answer": "x"})
                os.utime(p, (now, now))
            p = build_memory_health_payload(root, days=30, session_limit=20)
            counts = p.get("counts") or {}
            self.assertEqual(int(counts.get("recent_sessions") or 0), 5)
            self.assertEqual(int(counts.get("sessions_considered_for_coverage") or 0), 3)
            self.assertEqual(int(counts.get("sessions_with_memory_hit") or 0), 2)
            self.assertAlmostEqual(float(p.get("coverage") or 0), 2.0 / 3.0, places=3)
            self.assertEqual(int(counts.get("coverage_skipped_short_goal") or 0), 2)


if __name__ == "__main__":
    unittest.main()
