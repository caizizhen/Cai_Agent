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
