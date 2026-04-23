from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock
from unittest.mock import patch

from cai_agent import __main__ as m


class GatewayTelegramExecuteGoalTests(unittest.TestCase):
    def test_execute_persists_bound_session(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            (root / "cai-agent.toml").write_text(
                '[llm]\nbase_url = "http://127.0.0.1:9/v1"\nmodel = "m"\napi_key = "k"\n',
                encoding="utf-8",
            )
            sess = root / "s.json"
            sess.write_text(
                json.dumps({"version": 2, "messages": [{"role": "user", "content": "hi"}]}),
                encoding="utf-8",
            )
            final = {
                "finished": True,
                "answer": "DONE",
                "messages": [
                    {"role": "user", "content": "hi"},
                    {"role": "user", "content": "goal"},
                    {"role": "assistant", "content": "DONE"},
                ],
            }
            mock_app = MagicMock()
            mock_app.invoke.return_value = final
            with patch.object(m, "build_app", return_value=mock_app):
                ok, out = m._execute_gateway_telegram_goal(
                    config_path=str(root / "cai-agent.toml"),
                    workspace_root=str(root),
                    session_file=str(sess),
                    model_override=None,
                    goal="goal",
                )
            self.assertTrue(ok)
            self.assertIn("DONE", out)
            data = json.loads(sess.read_text(encoding="utf-8"))
            self.assertEqual(data.get("answer"), "DONE")
            self.assertEqual(data.get("run_schema_version"), "1.1")
            ev = data.get("events")
            self.assertIsInstance(ev, dict)
            self.assertEqual(ev.get("schema_version"), "run_events_envelope_v1")

    def test_execute_creates_session_when_path_missing(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            (root / "cai-agent.toml").write_text(
                '[llm]\nbase_url = "http://127.0.0.1:9/v1"\nmodel = "m"\napi_key = "k"\n',
                encoding="utf-8",
            )
            sess = root / "new.json"
            self.assertFalse(sess.is_file())
            final = {
                "finished": True,
                "answer": "first",
                "messages": [
                    {"role": "user", "content": "goal"},
                    {"role": "assistant", "content": "first"},
                ],
            }
            mock_app = MagicMock()
            mock_app.invoke.return_value = final
            with patch.object(m, "build_app", return_value=mock_app):
                ok, out = m._execute_gateway_telegram_goal(
                    config_path=str(root / "cai-agent.toml"),
                    workspace_root=str(root),
                    session_file=str(sess),
                    model_override=None,
                    goal="goal",
                )
            self.assertTrue(ok)
            self.assertEqual(out, "first")
            self.assertTrue(sess.is_file())
            data = json.loads(sess.read_text(encoding="utf-8"))
            self.assertEqual(data.get("answer"), "first")

    def test_execute_load_invalid_session_returns_error(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            (root / "cai-agent.toml").write_text(
                '[llm]\nbase_url = "http://127.0.0.1:9/v1"\nmodel = "m"\napi_key = "k"\n',
                encoding="utf-8",
            )
            bad = root / "bad.json"
            bad.write_text('{"version":2,"messages":[]}', encoding="utf-8")
            ok, out = m._execute_gateway_telegram_goal(
                config_path=str(root / "cai-agent.toml"),
                workspace_root=str(root),
                session_file=str(bad),
                model_override=None,
                goal="x",
            )
            self.assertFalse(ok)
            self.assertIn("不合法", out)

    def test_slash_stop_default_message(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CAI_TELEGRAM_STOP_WEBHOOK", None)
            os.environ.pop("CAI_TELEGRAM_ADMIN_USER_IDS", None)
            t = m._telegram_slash_reply_text(
                "/stop",
                map_path=Path("/tmp/map.json"),
                root=Path("/tmp"),
                user_id="999",
            )
        self.assertIn("gateway stop", t)

    def test_slash_stop_admin_calls_lifecycle(self) -> None:
        with patch.dict(
            os.environ,
            {"CAI_TELEGRAM_STOP_WEBHOOK": "1", "CAI_TELEGRAM_ADMIN_USER_IDS": "42,43"},
        ):
            with patch(
                "cai_agent.gateway_lifecycle.stop_webhook_subprocess",
                return_value={"ok": True, "stopped": True, "error": None},
            ) as sp:
                t = m._telegram_slash_reply_text(
                    "/stop",
                    map_path=Path("/x.json"),
                    root=Path("/r"),
                    user_id="42",
                )
        sp.assert_called_once_with(Path("/r"))
        self.assertIn("已执行", t)
        self.assertIn("ok=True", t)
