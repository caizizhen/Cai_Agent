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
from cai_agent.session import save_session


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

    def test_command_invoke_appends_metrics_when_env_set(self) -> None:
        prev_mock = os.environ.get("CAI_MOCK")
        prev_cfg = os.environ.get("CAI_CONFIG")
        os.environ["CAI_MOCK"] = "1"
        metrics_raw: str | None = None
        buf = io.StringIO()
        rc = 99
        try:
            with TemporaryDirectory() as td:
                root = Path(td) / "proj"
                root.mkdir(parents=True)
                (root / "commands").mkdir(parents=True)
                (root / "commands" / "mcmd.md").write_text("Minimal command template.\n", encoding="utf-8")
                cfg_path = root / "config.toml"
                cfg_path.write_text(
                    textwrap.dedent(
                        """
                        [llm]
                        base_url = "http://127.0.0.1:9/v1"
                        model = "m"
                        api_key = "k"
                        """,
                    ),
                    encoding="utf-8",
                )
                os.environ["CAI_CONFIG"] = str(cfg_path)
                metrics_path = Path(td) / "cmdm.jsonl"
                with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                    with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                        with redirect_stdout(buf):
                            rc = main(["command", "mcmd", "--json", "do work"])
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

        self.assertEqual(rc, 0)
        json.loads(buf.getvalue().strip())
        self.assertTrue(metrics_raw)
        row = json.loads(metrics_raw.splitlines()[-1])
        self.assertEqual(row.get("module"), "command")
        self.assertEqual(row.get("event"), "command.invoke")

    def test_memory_state_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "mst.jsonl"
            ws = Path(td) / "wsmst"
            (ws / "memory" / "instincts").mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(ws)):
                    with redirect_stdout(buf):
                        rc = main(["memory", "state", "--json"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "memory")
            self.assertEqual(row.get("event"), "memory.state")

    def test_recall_index_info_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "rixi.jsonl"
            ws = Path(td) / "wsrixi"
            ws.mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(ws)):
                    with redirect_stdout(buf):
                        rc = main(["recall-index", "info", "--json"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "recall_index")
            self.assertEqual(row.get("event"), "recall_index.info")

    def test_recall_index_doctor_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "rixd.jsonl"
            root = Path(td) / "rixroot"
            root.mkdir(parents=True, exist_ok=True)
            save_session(
                str(root / ".cai-session-doc.json"),
                {
                    "version": 2,
                    "model": "d1",
                    "messages": [{"role": "assistant", "content": "hello doctor metrics"}],
                },
            )
            buf_b = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf_b):
                    main(["recall-index", "build", "--json"])
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                    with redirect_stdout(buf):
                        rc = main(["recall-index", "doctor", "--json"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "recall_index")
            self.assertEqual(row.get("event"), "recall_index.doctor")
            self.assertIs(row.get("success"), True)

    def test_schedule_run_due_dry_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "srd.jsonl"
            ws = Path(td) / "wssrd"
            ws.mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(ws)):
                    with redirect_stdout(buf):
                        rc = main(["schedule", "run-due", "--json"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "schedule")
            self.assertEqual(row.get("event"), "schedule.run_due")

    def test_schedule_rm_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "srm.jsonl"
            ws = Path(td) / "wssrm"
            ws.mkdir(parents=True, exist_ok=True)
            buf_add = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(ws)):
                with redirect_stdout(buf_add):
                    rc_add = main(
                        [
                            "schedule",
                            "add",
                            "--goal",
                            "rm metrics",
                            "--every-minutes",
                            "999",
                            "--json",
                        ],
                    )
            self.assertEqual(rc_add, 0)
            job = json.loads(buf_add.getvalue().strip())
            tid = str(job.get("id") or "")
            self.assertTrue(tid)
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(ws)):
                    with redirect_stdout(buf):
                        rc = main(["schedule", "rm", tid, "--json"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "schedule")
            self.assertEqual(row.get("event"), "schedule.rm")

    def test_gateway_telegram_bind_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "gtb.jsonl"
            root = Path(td) / "gwbind"
            root.mkdir(parents=True, exist_ok=True)
            sess = root / ".cai-session-telegram.json"
            sess.write_text('{"version":2}\n', encoding="utf-8")
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                    with redirect_stdout(buf):
                        rc = main(
                            [
                                "gateway",
                                "telegram",
                                "bind",
                                "--chat-id",
                                "2002",
                                "--user-id",
                                "u-m",
                                "--session-file",
                                str(sess),
                                "--json",
                            ],
                        )
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "gateway")
            self.assertEqual(row.get("event"), "gateway.telegram.bind")

    def test_memory_list_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "ml.jsonl"
            ws = Path(td) / "wsml"
            (ws / "memory" / "instincts").mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(ws)):
                    with redirect_stdout(buf):
                        rc = main(["memory", "list", "--json", "--limit", "10"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "memory")
            self.assertEqual(row.get("event"), "memory.list")

    def test_quality_gate_appends_metrics_when_env_set(self) -> None:
        fake = {
            "schema_version": "quality_gate_result_v1",
            "ok": True,
            "failed_count": 0,
            "checks": [{"name": "stub", "exit_code": 0}],
        }
        with TemporaryDirectory() as td:
            root = Path(td) / "qgws"
            root.mkdir(parents=True, exist_ok=True)
            cfg = root / "cai-agent.toml"
            cfg.write_text(
                '[llm]\nbase_url = "http://127.0.0.1:9/v1"\nmodel = "m"\napi_key = "k"\n',
                encoding="utf-8",
            )
            metrics_path = Path(td) / "qg.jsonl"
            buf = io.StringIO()
            with patch("cai_agent.__main__.run_quality_gate", return_value=fake):
                with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                    with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                        with redirect_stdout(buf):
                            rc = main(
                                [
                                    "quality-gate",
                                    "--config",
                                    str(cfg),
                                    "--json",
                                    "--no-compile",
                                    "--no-test",
                                ],
                            )
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "quality_gate")
            self.assertEqual(row.get("event"), "quality_gate.run")

    def test_security_scan_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td) / "sscws"
            root.mkdir(parents=True, exist_ok=True)
            cfg = root / "cai-agent.toml"
            cfg.write_text(
                '[llm]\nbase_url = "http://127.0.0.1:9/v1"\nmodel = "m"\napi_key = "k"\n',
                encoding="utf-8",
            )
            metrics_path = Path(td) / "ssc.jsonl"
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                    with redirect_stdout(buf):
                        rc = main(["security-scan", "--config", str(cfg), "--json"])
            self.assertIn(rc, (0, 2))
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "security_scan")
            self.assertEqual(row.get("event"), "security_scan.run")

    def test_gateway_telegram_resolve_update_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td) / "gru"
            root.mkdir(parents=True, exist_ok=True)
            update_file = root / "update.json"
            update_file.write_text(
                json.dumps(
                    {
                        "update_id": 901,
                        "message": {
                            "message_id": 1,
                            "chat": {"id": 6001},
                            "from": {"id": 8001},
                            "text": "m",
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            metrics_path = Path(td) / "gru.jsonl"
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                    with redirect_stdout(buf):
                        rc = main(
                            [
                                "gateway",
                                "telegram",
                                "resolve-update",
                                "--update-file",
                                str(update_file),
                                "--create-missing",
                                "--session-template",
                                ".cai/gateway/sessions/tg-{chat_id}-{user_id}.json",
                                "--json",
                            ],
                        )
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "gateway")
            self.assertEqual(row.get("event"), "gateway.telegram.resolve_update")

    def test_schedule_add_memory_nudge_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "amn.jsonl"
            ws = Path(td) / "wsamn"
            ws.mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(ws)):
                    with redirect_stdout(buf):
                        rc = main(["schedule", "add-memory-nudge", "--json"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "schedule")
            self.assertEqual(row.get("event"), "schedule.add_memory_nudge")


if __name__ == "__main__":
    unittest.main()
