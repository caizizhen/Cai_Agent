from __future__ import annotations

import io
import json
import os
import sys
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

    def test_mcp_check_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "mcpm.jsonl"
            root = Path(td) / "wsmcp"
            cfg = root / "cai-agent.toml"
            root.mkdir(parents=True, exist_ok=True)
            cfg.write_text(
                "[llm]\nbase_url = \"http://x/v1\"\nmodel = \"m\"\napi_key = \"k\"\n",
                encoding="utf-8",
            )
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                    with patch(
                        "cai_agent.__main__.dispatch",
                        return_value="- tool_a\n- tool_b\n",
                    ):
                        with redirect_stdout(buf):
                            rc = main(["mcp-check", "--config", str(cfg), "--json"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "mcp")
            self.assertEqual(row.get("event"), "mcp.check")
            self.assertEqual(row.get("tokens"), 2)
            self.assertTrue(row.get("success"))

    def test_hooks_run_event_dry_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "hre.jsonl"
            root = Path(td) / "wshre"
            root.mkdir(parents=True, exist_ok=True)
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
                                "command": [sys.executable, "-c", "print(1)"],
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                    with redirect_stdout(buf):
                        rc = main(
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
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "hooks")
            self.assertEqual(row.get("event"), "hooks.run_event")
            self.assertEqual(row.get("tokens"), 1)
            self.assertTrue(row.get("success"))

    def test_gateway_telegram_serve_webhook_appends_metrics_when_env_set(self) -> None:
        fake_payload = {
            "ok": True,
            "handled_requests": 2,
            "host": "127.0.0.1",
            "port": 18765,
            "path": "/telegram/update",
            "map_file": "m.json",
            "log_file": "l.jsonl",
            "create_missing": False,
        }
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "gws.jsonl"
            root = Path(td) / "wsgws"
            root.mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                    with patch(
                        "cai_agent.__main__._run_gateway_telegram_webhook_server",
                        return_value=fake_payload,
                    ):
                        with redirect_stdout(buf):
                            rc = main(
                                [
                                    "gateway",
                                    "telegram",
                                    "serve-webhook",
                                    "--host",
                                    "127.0.0.1",
                                    "--port",
                                    "18766",
                                    "--max-events",
                                    "1",
                                    "--json",
                                ],
                            )
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "gateway")
            self.assertEqual(row.get("event"), "gateway.telegram.serve_webhook")
            self.assertEqual(row.get("tokens"), 2)
            self.assertTrue(row.get("success"))

    def test_sessions_list_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "sess.jsonl"
            ws = Path(td) / "wssess"
            ws.mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(ws)):
                    with redirect_stdout(buf):
                        rc = main(["sessions", "--json"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "sessions")
            self.assertEqual(row.get("event"), "sessions.list")

    def test_stats_summary_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "st.jsonl"
            ws = Path(td) / "wsst"
            ws.mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(ws)):
                    with redirect_stdout(buf):
                        rc = main(["stats", "--json"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "stats")
            self.assertEqual(row.get("event"), "stats.summary")

    def test_insights_summary_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "ins.jsonl"
            ws = Path(td) / "wsins"
            ws.mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(ws)):
                    with redirect_stdout(buf):
                        rc = main(["insights", "--json", "--days", "7"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "insights")
            self.assertEqual(row.get("event"), "insights.summary")

    def test_skills_hub_manifest_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "skm.jsonl"
            ws = Path(td) / "wssk"
            ws.mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(ws)):
                    with redirect_stdout(buf):
                        rc = main(["skills", "hub", "manifest", "--json"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "skills")
            self.assertEqual(row.get("event"), "skills.hub_manifest")

    def test_observe_report_standalone_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "obr.jsonl"
            ws = Path(td) / "wsobr"
            ws.mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(ws)):
                    with redirect_stdout(buf):
                        rc = main(["observe-report", "--json"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "observe")
            self.assertEqual(row.get("event"), "observe.report")

    def test_ops_dashboard_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "opsm.jsonl"
            ws = Path(td) / "wsops"
            ws.mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(ws)):
                    with redirect_stdout(buf):
                        rc = main(["ops", "dashboard", "--json"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "ops")
            self.assertEqual(row.get("event"), "ops.dashboard")

    def test_plan_goal_empty_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "pl.jsonl"
            root = Path(td) / "wspl"
            cfg = root / "cai-agent.toml"
            root.mkdir(parents=True, exist_ok=True)
            cfg.write_text(
                "[llm]\nbase_url = \"http://x/v1\"\nmodel = \"m\"\napi_key = \"k\"\n",
                encoding="utf-8",
            )
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                    with redirect_stdout(buf):
                        rc = main(["plan", "--config", str(cfg), "--json", " ", " "])
            self.assertEqual(rc, 2)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "plan")
            self.assertEqual(row.get("event"), "plan.generate")
            self.assertFalse(row.get("success"))

    def test_doctor_run_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "doc.jsonl"
            root = Path(td) / "wsdoc"
            cfg = root / "cai-agent.toml"
            root.mkdir(parents=True, exist_ok=True)
            cfg.write_text(
                "[llm]\nbase_url = \"http://x/v1\"\nmodel = \"m\"\napi_key = \"k\"\n",
                encoding="utf-8",
            )
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                    with patch("cai_agent.__main__.run_doctor", return_value=0):
                        with redirect_stdout(buf):
                            rc = main(["doctor", "--config", str(cfg), "--json"])
            self.assertEqual(rc, 0)
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "doctor")
            self.assertEqual(row.get("event"), "doctor.run")

    def test_export_target_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "exp.jsonl"
            root = Path(td) / "wsexp"
            cfg = root / "cai-agent.toml"
            root.mkdir(parents=True, exist_ok=True)
            cfg.write_text(
                "[llm]\nbase_url = \"http://x/v1\"\nmodel = \"m\"\napi_key = \"k\"\n",
                encoding="utf-8",
            )
            fake = {
                "schema_version": "export_cli_v1",
                "target": "cursor",
                "copied": ["rules", "skills"],
            }
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                    with patch("cai_agent.__main__.export_target", return_value=fake):
                        with redirect_stdout(buf):
                            rc = main(["export", "--config", str(cfg), "--target", "cursor"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "export")
            self.assertEqual(row.get("event"), "export.target")
            self.assertEqual(row.get("tokens"), 2)

    def test_init_apply_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "ini_m.jsonl"
            root = Path(td) / "wsini"
            root.mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                    with redirect_stdout(buf):
                        rc = main(["init", "--json"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "init")
            self.assertEqual(row.get("event"), "init.apply")
            self.assertEqual(row.get("tokens"), 1)
            self.assertIs(row.get("success"), True)

    def test_init_apply_metrics_on_config_exists_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "ini_fail.jsonl"
            root = Path(td) / "wsinif"
            root.mkdir(parents=True, exist_ok=True)
            (root / "cai-agent.toml").write_text("[llm]\nmodel = \"x\"\n", encoding="utf-8")
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                    with redirect_stdout(buf):
                        rc = main(["init", "--json"])
            self.assertEqual(rc, 2)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "init")
            self.assertEqual(row.get("event"), "init.apply")
            self.assertEqual(row.get("tokens"), 0)
            self.assertIs(row.get("success"), False)

    def test_models_list_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "mdl.jsonl"
            root = Path(td) / "wsmdl"
            root.mkdir(parents=True, exist_ok=True)
            (root / "cai-agent.toml").write_text(
                '[llm]\nbase_url = "http://127.0.0.1:9/v1"\nmodel = "m"\napi_key = "k"\n',
                encoding="utf-8",
            )
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                    with redirect_stdout(buf):
                        rc = main(["models", "list", "--json"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "models")
            self.assertEqual(row.get("event"), "models.list")
            self.assertGreaterEqual(int(row.get("tokens") or 0), 1)
            self.assertIs(row.get("success"), True)

    def test_workflow_run_appends_metrics_when_env_set(self) -> None:
        fake = {
            "schema_version": "workflow_run_v1",
            "task": {
                "task_id": "wf-m",
                "type": "workflow",
                "status": "completed",
            },
            "subagent_io_schema_version": "1.0",
            "subagent_io": {"inputs": {}, "merge": {"conflicts": []}, "outputs": []},
            "steps": [],
            "summary": {
                "steps_count": 0,
                "budget_used": 9,
                "elapsed_ms_total": 1,
                "elapsed_ms_avg": 0,
                "tool_calls_total": 0,
                "tool_errors_total": 0,
            },
            "events": [],
        }
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "wfm.jsonl"
            root = Path(td) / "wswf"
            root.mkdir(parents=True, exist_ok=True)
            (root / "cai-agent.toml").write_text(
                '[llm]\nbase_url = "http://127.0.0.1:9/v1"\nmodel = "m"\napi_key = "k"\n',
                encoding="utf-8",
            )
            wf_path = root / "wf.json"
            wf_path.write_text(
                json.dumps({"steps": [{"name": "s1", "goal": "g"}]}),
                encoding="utf-8",
            )
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                    with patch("cai_agent.__main__.run_workflow", return_value=fake):
                        with redirect_stdout(buf):
                            rc = main(["workflow", str(wf_path), "--json"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "workflow")
            self.assertEqual(row.get("event"), "workflow.run")
            self.assertEqual(row.get("tokens"), 9)
            self.assertIs(row.get("success"), True)

    def test_workflow_run_metrics_on_exception_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "wfe.jsonl"
            root = Path(td) / "wswfe"
            root.mkdir(parents=True, exist_ok=True)
            (root / "cai-agent.toml").write_text(
                '[llm]\nbase_url = "http://127.0.0.1:9/v1"\nmodel = "m"\napi_key = "k"\n',
                encoding="utf-8",
            )
            wf_path = root / "wf.json"
            wf_path.write_text(json.dumps({"steps": [{"name": "s1", "goal": "g"}]}), encoding="utf-8")
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                    with patch(
                        "cai_agent.__main__.run_workflow",
                        side_effect=RuntimeError("boom"),
                    ):
                        with redirect_stdout(buf):
                            rc = main(["workflow", str(wf_path), "--json"])
            self.assertEqual(rc, 2)
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "workflow")
            self.assertEqual(row.get("event"), "workflow.run")
            self.assertEqual(row.get("tokens"), 0)
            self.assertIs(row.get("success"), False)

    def test_release_ga_gate_appends_metrics_when_env_set(self) -> None:
        payload = {
            "schema_version": "release_ga_gate_v1",
            "state": "pass",
            "checks": [{"name": "c1"}, {"name": "c2"}],
            "checks_passed": 2,
            "failure_rate": 0.0,
            "total_tokens": 0,
        }
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "rg.jsonl"
            root = Path(td) / "wsrg"
            root.mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                    with patch("cai_agent.__main__._run_release_ga_gate", return_value=payload):
                        with redirect_stdout(buf):
                            rc = main(["release-ga", "--json"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "release_ga")
            self.assertEqual(row.get("event"), "release_ga.gate")
            self.assertEqual(row.get("tokens"), 2)
            self.assertIs(row.get("success"), True)

    def test_release_ga_gate_metrics_on_fail_state_when_env_set(self) -> None:
        payload = {
            "schema_version": "release_ga_gate_v1",
            "state": "fail",
            "checks": [{"name": "bad"}],
            "checks_passed": 0,
            "failure_rate": 1.0,
            "total_tokens": 0,
            "failed_checks": [{"name": "bad", "reason": "stub"}],
        }
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "rgf.jsonl"
            root = Path(td) / "wsrgf"
            root.mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                    with patch("cai_agent.__main__._run_release_ga_gate", return_value=payload):
                        with redirect_stdout(buf):
                            rc = main(["release-ga", "--json"])
            self.assertEqual(rc, 2)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "release_ga")
            self.assertEqual(row.get("event"), "release_ga.gate")
            self.assertEqual(row.get("tokens"), 1)
            self.assertIs(row.get("success"), False)

    def test_models_fetch_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "mdf.jsonl"
            root = Path(td) / "wsmdf"
            root.mkdir(parents=True, exist_ok=True)
            (root / "cai-agent.toml").write_text(
                '[llm]\nbase_url = "http://127.0.0.1:9/v1"\nmodel = "m"\napi_key = "k"\n',
                encoding="utf-8",
            )
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                    with patch("cai_agent.__main__.fetch_models", return_value=["alpha", "beta"]):
                        with redirect_stdout(buf):
                            rc = main(["models", "fetch", "--json"])
            self.assertEqual(rc, 0)
            out = json.loads(buf.getvalue().strip())
            self.assertIn("models", out)
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "models")
            self.assertEqual(row.get("event"), "models.fetch")
            self.assertEqual(row.get("tokens"), 1)
            self.assertIs(row.get("success"), True)

    def test_workflow_run_metrics_on_fail_on_step_errors_when_env_set(self) -> None:
        fake = {
            "schema_version": "workflow_run_v1",
            "task": {
                "task_id": "wf-fe",
                "type": "workflow",
                "status": "completed",
            },
            "subagent_io_schema_version": "1.0",
            "subagent_io": {"inputs": {}, "merge": {"conflicts": []}, "outputs": []},
            "steps": [{"name": "s1", "index": 1, "error_count": 1}],
            "summary": {
                "steps_count": 1,
                "budget_used": 4,
                "elapsed_ms_total": 1,
                "elapsed_ms_avg": 1,
                "tool_calls_total": 0,
                "tool_errors_total": 0,
            },
            "events": [],
        }
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "wff.jsonl"
            root = Path(td) / "wswff"
            root.mkdir(parents=True, exist_ok=True)
            (root / "cai-agent.toml").write_text(
                '[llm]\nbase_url = "http://127.0.0.1:9/v1"\nmodel = "m"\napi_key = "k"\n',
                encoding="utf-8",
            )
            wf_path = root / "wf.json"
            wf_path.write_text(
                json.dumps({"steps": [{"name": "s1", "goal": "g"}]}),
                encoding="utf-8",
            )
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                    with patch("cai_agent.__main__.run_workflow", return_value=fake):
                        with redirect_stdout(buf):
                            rc = main(
                                ["workflow", str(wf_path), "--json", "--fail-on-step-errors"],
                            )
            self.assertEqual(rc, 2)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "workflow")
            self.assertEqual(row.get("event"), "workflow.run")
            self.assertEqual(row.get("tokens"), 4)
            self.assertIs(row.get("success"), False)

    def test_ui_tui_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "ui.jsonl"
            root = Path(td) / "wsui"
            root.mkdir(parents=True, exist_ok=True)
            (root / "cai-agent.toml").write_text(
                '[llm]\nbase_url = "http://127.0.0.1:9/v1"\nmodel = "m"\napi_key = "k"\n',
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                    with patch("cai_agent.tui.run_tui", return_value=None):
                        rc = main(["ui"])
            self.assertEqual(rc, 0)
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "ui")
            self.assertEqual(row.get("event"), "ui.tui")
            self.assertIs(row.get("success"), True)

    def test_ui_tui_metrics_on_config_missing_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "ui2.jsonl"
            root = Path(td) / "wsui2"
            root.mkdir(parents=True, exist_ok=True)
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                    with patch(
                        "cai_agent.__main__.Settings.from_env",
                        side_effect=FileNotFoundError("no config"),
                    ):
                        rc = main(["ui"])
            self.assertEqual(rc, 2)
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "ui")
            self.assertEqual(row.get("event"), "ui.tui")
            self.assertIs(row.get("success"), False)

    def test_hooks_list_json_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "hl.jsonl"
            root = Path(td) / "wshl"
            root.mkdir(parents=True, exist_ok=True)
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
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                    with redirect_stdout(buf):
                        rc = main(["hooks", "--config", str(cfg), "list", "--json"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "hooks")
            self.assertEqual(row.get("event"), "hooks.list")
            self.assertEqual(row.get("tokens"), 1)


if __name__ == "__main__":
    unittest.main()
