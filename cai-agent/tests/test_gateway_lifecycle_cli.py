from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock
from unittest.mock import patch

from cai_agent.__main__ import main


class GatewayLifecycleCliTests(unittest.TestCase):
    def test_setup_status_stop_no_pid(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "gateway",
                            "setup",
                            "--json",
                            "--host",
                            "0.0.0.0",
                            "--port",
                            "19999",
                            "--execute-on-update",
                            "--allow-chat-id",
                            "42",
                        ],
                    )
            self.assertEqual(rc, 0)
            setup_o = json.loads(buf.getvalue().strip())
            self.assertEqual(setup_o.get("schema_version"), "gateway_telegram_config_v1")
            self.assertIs(setup_o.get("ok"), True)
            cfg_p = root / ".cai" / "gateway" / "telegram-config.json"
            self.assertTrue(cfg_p.is_file())
            doc = json.loads(cfg_p.read_text(encoding="utf-8"))
            sw = doc.get("serve_webhook") or {}
            self.assertEqual(sw.get("host"), "0.0.0.0")
            self.assertEqual(sw.get("port"), 19999)
            self.assertIs(sw.get("execute_on_update"), True)
            map_p = root / ".cai" / "gateway" / "telegram-session-map.json"
            self.assertTrue(map_p.is_file())
            mp = json.loads(map_p.read_text(encoding="utf-8"))
            self.assertIn("42", mp.get("allowed_chat_ids") or [])

            buf2 = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf2):
                    rc2 = main(["gateway", "status", "--json"])
            self.assertEqual(rc2, 0)
            st = json.loads(buf2.getvalue().strip())
            self.assertEqual(st.get("schema_version"), "gateway_lifecycle_status_v1")
            self.assertIs(st.get("config_exists"), True)
            self.assertIs(st.get("webhook_running"), False)
            summary = st.get("gateway_summary") or {}
            self.assertEqual(summary.get("schema_version"), "gateway_summary_v1")
            self.assertEqual(summary.get("status"), "configured")
            self.assertEqual(summary.get("allowed_chat_ids_count"), 1)
            self.assertEqual(summary.get("bindings_count"), 0)

            buf3 = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf3):
                    rc3 = main(["gateway", "stop", "--json"])
            self.assertEqual(rc3, 0)
            sp = json.loads(buf3.getvalue().strip())
            self.assertIs(sp.get("ok"), False)
            self.assertEqual(sp.get("error"), "no_pid_file")

    def test_prod_status_summarizes_multi_platform_contract(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            gdir = root / ".cai" / "gateway"
            gdir.mkdir(parents=True, exist_ok=True)
            (gdir / "telegram-session-map.json").write_text(
                json.dumps(
                    {
                        "schema_version": "gateway_telegram_map_v1",
                        "bindings": {"1:2": {"chat_id": "1", "user_id": "2", "session_file": "s.json"}},
                        "allowed_chat_ids": ["1"],
                    },
                ),
                encoding="utf-8",
            )
            (gdir / "slack-session-map.json").write_text(
                json.dumps(
                    {
                        "schema_version": "gateway_slack_map_v1",
                        "bindings": {"C1": {"session_file": "slack.json"}},
                        "allowed_channel_ids": [],
                    },
                ),
                encoding="utf-8",
            )
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["gateway", "prod-status", "--json"])
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("schema_version"), "gateway_production_summary_v1")
            self.assertEqual(payload.get("summary", {}).get("platforms_count"), 7)
            self.assertEqual(payload.get("summary", {}).get("bindings_count"), 2)
            fed = payload.get("federation") or {}
            self.assertEqual(fed.get("schema_version"), "gateway_workspace_federation_v1")
            self.assertEqual(fed.get("workspaces_count"), 1)
            rows = {r.get("id"): r for r in payload.get("platforms") or []}
            self.assertEqual(rows["telegram"]["production_state"], "configured")
            self.assertEqual(rows["slack"]["health"]["bindings_count"], 1)
            slack_ready = rows["slack"].get("readiness") or {}
            self.assertEqual(slack_ready.get("schema_version"), "gateway_platform_readiness_v1")
            self.assertEqual(slack_ready.get("state"), "blocked")
            self.assertGreaterEqual(int(slack_ready.get("checks_total") or 0), 3)
            self.assertTrue(rows["slack"].get("readiness_checklist"))
            slack_diagnostics = rows["slack"].get("diagnostics") or []
            self.assertTrue(any(d.get("check_id") == "slack_bot_token" for d in slack_diagnostics))
            teams_diagnostics = rows["teams"].get("diagnostics") or []
            self.assertTrue(any(d.get("check_id") == "cai_teams_app_id" for d in teams_diagnostics))
            self.assertGreaterEqual(int(payload.get("summary", {}).get("blocked_count") or 0), 1)
            self.assertGreaterEqual(int(payload.get("summary", {}).get("diagnostics_count") or 0), 1)
            tg_mon = rows["telegram"].get("channel_monitoring") or {}
            self.assertEqual(tg_mon.get("schema_version"), "gateway_channel_monitoring_v1")
            self.assertGreaterEqual(int(tg_mon.get("channels_count") or 0), 1)
            tg_ch = (tg_mon.get("channels") or [{}])[0]
            self.assertIn("last_seen", tg_ch)
            self.assertIn("latency_ms", tg_ch)
            self.assertIn("error_count", tg_ch)
            self.assertIn("owner", tg_ch)

    def test_start_patches_popen(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            cfg = {
                "schema_version": "gateway_telegram_config_v1",
                "serve_webhook": {
                    "host": "127.0.0.1",
                    "port": 18765,
                    "max_events": 0,
                },
            }
            gdir = root / ".cai" / "gateway"
            gdir.mkdir(parents=True, exist_ok=True)
            (gdir / "telegram-config.json").write_text(
                json.dumps(cfg, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            mock_proc = MagicMock()
            mock_proc.pid = 424242
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with patch("cai_agent.gateway_lifecycle.subprocess.Popen", return_value=mock_proc) as pp:
                    with redirect_stdout(buf):
                        rc = main(["gateway", "start", "--json"])
            self.assertEqual(rc, 0)
            out = json.loads(buf.getvalue().strip())
            self.assertIs(out.get("ok"), True)
            self.assertEqual(out.get("pid"), 424242)
            pp.assert_called_once()
            pid_f = gdir / "telegram-webhook.pid"
            self.assertTrue(pid_f.is_file())

    def test_workspace_flag_telegram_list(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            other = root / "nested"
            other.mkdir()
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(other)):
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "gateway",
                            "telegram",
                            "-w",
                            str(root),
                            "list",
                            "--json",
                        ],
                    )
            self.assertEqual(rc, 0)
            lo = json.loads(buf.getvalue().strip())
            self.assertTrue(str(lo.get("map_file") or "").endswith("telegram-session-map.json"))

    def test_gateway_route_preview_json(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "gateway",
                            "route-preview",
                            "--platform",
                            "telegram",
                            "--channel-id",
                            "42:7",
                            "--target-profile-id",
                            "p1",
                            "--json",
                        ],
                    )
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("schema_version"), "gateway_proxy_route_v1")
            self.assertIs(payload.get("dry_run"), True)
            src = payload.get("source") or {}
            route = payload.get("route") or {}
            self.assertEqual(src.get("platform"), "telegram")
            self.assertEqual(src.get("channel_id"), "42:7")
            self.assertEqual(route.get("target_profile_id"), "p1")

    def test_gateway_federation_summary_json(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            gdir = root / ".cai" / "gateway"
            gdir.mkdir(parents=True, exist_ok=True)
            (gdir / "telegram-session-map.json").write_text(
                json.dumps(
                    {
                        "schema_version": "gateway_telegram_map_v1",
                        "bindings": {"1:2": {"chat_id": "1", "user_id": "2", "session_file": "s.json"}},
                        "allowed_chat_ids": ["1"],
                    },
                ),
                encoding="utf-8",
            )
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["gateway", "federation-summary", "--json"])
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("schema_version"), "gateway_federation_summary_v1")
            self.assertEqual(payload.get("summary", {}).get("platforms_count"), 7)
            self.assertGreaterEqual(payload.get("summary", {}).get("channels_count"), 1)

    def test_gateway_channel_monitor_json_filters_platform_and_errors(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            gdir = root / ".cai" / "gateway"
            gdir.mkdir(parents=True, exist_ok=True)
            (gdir / "telegram-session-map.json").write_text(
                json.dumps(
                    {
                        "schema_version": "gateway_telegram_map_v1",
                        "bindings": {"1:2": {"chat_id": "1", "user_id": "2", "session_file": "s.json"}},
                        "allowed_chat_ids": ["1"],
                    },
                ),
                encoding="utf-8",
            )
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["gateway", "channel-monitor", "--platform", "telegram", "--json"])
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("schema_version"), "gateway_channel_monitor_v1")
            self.assertEqual(payload.get("platform_filter"), "telegram")
            self.assertEqual(payload.get("platforms_count"), 1)
            self.assertGreaterEqual(payload.get("channels_count"), 1)
            row = (payload.get("platforms") or [{}])[0]
            self.assertEqual(row.get("id"), "telegram")
            channel = (row.get("channels") or [{}])[0]
            self.assertEqual(channel.get("channel_id"), "1:2")

            buf2 = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf2):
                    rc2 = main(["gateway", "channel-monitor", "--platform", "telegram", "--only-errors", "--json"])
            self.assertEqual(rc2, 0)
            only_errors = json.loads(buf2.getvalue().strip())
            self.assertIs(only_errors.get("only_errors"), True)
            self.assertEqual(only_errors.get("channels_count"), 0)

    def test_gateway_slash_catalog_json(self) -> None:
        root = (Path.cwd() / ".tmp-test" / "gateway-slash-catalog-cli").resolve()
        root.mkdir(parents=True, exist_ok=True)
        buf = io.StringIO()
        with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
            with redirect_stdout(buf):
                rc = main(["gateway", "slash-catalog", "--json"])
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue().strip())
        self.assertEqual(payload.get("schema_version"), "gateway_slash_catalog_v1")
        self.assertGreaterEqual(payload.get("platforms_count"), 3)
        platforms = {p.get("id"): p for p in payload.get("platforms") or []}
        self.assertIn("discord", platforms)
        self.assertIn("slack", platforms)
        self.assertIn("teams", platforms)
        slack_commands = platforms["slack"].get("commands") or []
        self.assertTrue(any(c.get("name") == "/cai <goal>" and c.get("execute_capable") for c in slack_commands))
