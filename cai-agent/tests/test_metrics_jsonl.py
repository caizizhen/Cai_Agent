from __future__ import annotations

import io
import json
import os
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cai_agent.__main__ import main


class MetricsJsonlTests(unittest.TestCase):
    def test_observe_summary_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "metrics.jsonl"
            tdir = Path(td) / "ws"
            tdir.mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(tdir)):
                    with redirect_stdout(buf):
                        rc = main(["observe", "--json"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            raw = metrics_path.read_text(encoding="utf-8").strip()
            self.assertTrue(raw)
            row = json.loads(raw.splitlines()[-1])
            self.assertEqual(row.get("schema_version"), "metrics_schema_v1")
            self.assertEqual(row.get("module"), "observe")
            self.assertEqual(row.get("event"), "observe.summary")

    def test_observe_report_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "m2.jsonl"
            ws = Path(td) / "ws2"
            ws.mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(ws)):
                    with redirect_stdout(buf):
                        rc = main(["observe", "report", "--format", "json", "--days", "1"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("event"), "observe.report")

    def test_memory_health_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "mh.jsonl"
            ws = Path(td) / "wsm"
            (ws / "memory" / "instincts").mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(ws)):
                    with redirect_stdout(buf):
                        rc = main(["memory", "health", "--json"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "memory")
            self.assertEqual(row.get("event"), "memory.health")

    def test_recall_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "rc.jsonl"
            ws = Path(td) / "wsr"
            ws.mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(ws)):
                    with redirect_stdout(buf):
                        rc = main(
                            [
                                "recall",
                                "--query",
                                "x",
                                "--days",
                                "7",
                                "--json",
                            ],
                        )
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "recall")
            self.assertEqual(row.get("event"), "recall.query")

    def test_schedule_stats_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "ss.jsonl"
            ws = Path(td) / "wss"
            ws.mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(ws)):
                    with redirect_stdout(buf):
                        rc = main(["schedule", "stats", "--json", "--days", "1"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "schedule")
            self.assertEqual(row.get("event"), "schedule.stats")

    def test_gateway_status_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "gw.jsonl"
            ws = Path(td) / "wsg"
            ws.mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(ws)):
                    with redirect_stdout(buf):
                        rc = main(["gateway", "status", "--json"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "gateway")
            self.assertEqual(row.get("event"), "gateway.status")

    def test_recall_index_build_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "rix.jsonl"
            ws = Path(td) / "wsrix"
            ws.mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(ws)):
                    with redirect_stdout(buf):
                        rc = main(["recall-index", "build", "--json"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "recall_index")
            self.assertEqual(row.get("event"), "recall_index.build")

    def test_schedule_list_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "sl.jsonl"
            ws = Path(td) / "wssl"
            ws.mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(ws)):
                    with redirect_stdout(buf):
                        rc = main(["schedule", "list", "--json"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "schedule")
            self.assertEqual(row.get("event"), "schedule.list")

    def test_schedule_add_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "sa.jsonl"
            ws = Path(td) / "wssa"
            ws.mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(ws)):
                    with redirect_stdout(buf):
                        rc = main(
                            [
                                "schedule",
                                "add",
                                "--goal",
                                "metrics smoke",
                                "--every-minutes",
                                "120",
                                "--json",
                            ],
                        )
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "schedule")
            self.assertEqual(row.get("event"), "schedule.add")

    def test_gateway_telegram_list_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "gtl.jsonl"
            root = Path(td) / "gwroot"
            root.mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                    with redirect_stdout(buf):
                        rc = main(["gateway", "telegram", "list", "--json"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "gateway")
            self.assertEqual(row.get("event"), "gateway.telegram.list")

    def test_run_invoke_appends_metrics_when_env_set(self) -> None:
        prev_mock = os.environ.get("CAI_MOCK")
        prev_cfg = os.environ.get("CAI_CONFIG")
        os.environ["CAI_MOCK"] = "1"
        cfg: str | None = None
        metrics_raw: str | None = None
        buf = io.StringIO()
        rc = 99
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                suffix=".toml",
                delete=False,
                encoding="utf-8",
            ) as f:
                f.write(
                    textwrap.dedent(
                        """
                        [llm]
                        base_url = "http://127.0.0.1:9/v1"
                        model = "m"
                        api_key = "k"
                        """,
                    ),
                )
                cfg = f.name
            os.environ["CAI_CONFIG"] = cfg
            with TemporaryDirectory() as td:
                metrics_path = Path(td) / "runm.jsonl"
                with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                    with redirect_stdout(buf):
                        rc = main(["run", "--json", "hello metrics"])
                metrics_raw = metrics_path.read_text(encoding="utf-8").strip()
        finally:
            if prev_mock is None:
                os.environ.pop("CAI_MOCK", None)
            else:
                os.environ["CAI_MOCK"] = prev_mock
            if prev_cfg is None:
                os.environ.pop("CAI_CONFIG", None)
            else:
                os.environ["CAI_CONFIG"] = prev_cfg
            if cfg:
                try:
                    os.unlink(cfg)
                except OSError:
                    pass

        self.assertEqual(rc, 0)
        json.loads(buf.getvalue().strip())
        self.assertTrue(metrics_raw)
        row = json.loads(metrics_raw.splitlines()[-1])
        self.assertEqual(row.get("module"), "run")
        self.assertEqual(row.get("event"), "run.invoke")


if __name__ == "__main__":
    unittest.main()
