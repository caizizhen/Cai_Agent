from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cai_agent.__main__ import main
from cai_agent.schedule import aggregate_schedule_audit_by_calendar_day_utc
from cai_agent.session import save_session


class InsightsCrossDomainTests(unittest.TestCase):
    def test_cross_domain_requires_json(self) -> None:
        with TemporaryDirectory() as td:
            err = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(td)):
                with redirect_stderr(err):
                    rc = main(["insights", "--cross-domain", "--days", "1"])
            self.assertEqual(rc, 2)

    def test_cross_domain_json_empty_workspace(self) -> None:
        with TemporaryDirectory() as td:
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(td)):
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "insights",
                            "--json",
                            "--cross-domain",
                            "--days",
                            "4",
                            "--limit",
                            "5",
                        ],
                    )
            self.assertEqual(rc, 0)
            doc = json.loads(buf.getvalue().strip())
            self.assertEqual(doc.get("schema_version"), "insights_cross_domain_v1")
            self.assertEqual(doc.get("recall_hit_rate_metric_kind"), "index_probe")
            self.assertIsInstance(doc.get("negative_queries_top"), list)
            self.assertIsInstance(doc.get("recall_hit_rate_metric_note"), str)
            self.assertEqual(doc.get("insights", {}).get("schema_version"), "1.1")
            self.assertEqual(len(doc.get("recall_hit_rate_trend") or []), 4)
            self.assertEqual(len(doc.get("memory_health_trend") or []), 4)
            self.assertEqual(len(doc.get("schedule_success_trend") or []), 4)
            r0 = (doc.get("recall_hit_rate_trend") or [])[0]
            self.assertEqual(r0.get("no_index_reason"), "index_missing")
            self.assertEqual(r0.get("metric_kind"), "unavailable")
            self.assertEqual(r0.get("metric_unavailability_reason"), "index_missing")

    def test_schedule_aggregate_by_day_counts_completed(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            now = datetime.now(UTC)
            yesterday = now - timedelta(days=1)
            lines = [
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "ts": now.isoformat(),
                        "event": "task.completed",
                        "task_id": "a",
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "ts": yesterday.isoformat(),
                        "event": "task.failed",
                        "task_id": "b",
                    },
                    ensure_ascii=False,
                ),
            ]
            (root / ".cai-schedule-audit.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
            rows = aggregate_schedule_audit_by_calendar_day_utc(cwd=str(root), days=7)
            self.assertEqual(len(rows), 7)
            today_row = next(r for r in rows if r.get("date") == now.date().isoformat())
            self.assertGreaterEqual(int(today_row.get("success_count") or 0), 1)
            y_row = next(r for r in rows if r.get("date") == yesterday.date().isoformat())
            self.assertGreaterEqual(int(y_row.get("fail_count") or 0), 1)

    def test_cross_domain_with_index_probe(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            mt = int(datetime.now(UTC).timestamp())
            idx = {
                "version": 1,
                "entries": [
                    {"path": "/x", "mtime": mt, "content": "hello there"},
                    {"path": "/y", "mtime": mt, "content": "xyz 123 nope"},
                ],
            }
            (root / ".cai-recall-index.json").write_text(
                json.dumps(idx, ensure_ascii=False),
                encoding="utf-8",
            )
            save_session(
                str(root / ".cai-session-a.json"),
                {
                    "version": 2,
                    "goal": "x" * 10,
                    "total_tokens": 0,
                    "error_count": 0,
                    "messages": [],
                },
            )
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(
                        ["insights", "--json", "--cross-domain", "--days", "2", "--limit", "5"],
                    )
            self.assertEqual(rc, 0)
            doc = json.loads(buf.getvalue().strip())
            trends = doc.get("recall_hit_rate_trend") or []
            today_tr = next(t for t in trends if t.get("date") == datetime.now(UTC).date().isoformat())
            self.assertEqual(today_tr.get("metric_kind"), "index_probe")
            self.assertIsNotNone(today_tr.get("hit_rate"))
            self.assertEqual(int(today_tr.get("indexed_rows") or 0), 2)
            self.assertEqual(doc.get("recall_hit_rate_metric_kind"), "index_probe")


if __name__ == "__main__":
    unittest.main()
