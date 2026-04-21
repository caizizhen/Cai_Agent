from __future__ import annotations

import io
import json
import textwrap
import unittest
from contextlib import redirect_stdout
from contextlib import redirect_stderr
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import URLError

from cai_agent.__main__ import main
from cai_agent.config import Settings


class GatewayTelegramCliTests(unittest.TestCase):
    def test_bind_get_list_unbind_cycle(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            sess = root / ".cai-session-telegram.json"
            sess.write_text('{"version":2}\n', encoding="utf-8")

            buf_bind = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf_bind):
                    rc_bind = main(
                        [
                            "gateway",
                            "telegram",
                            "bind",
                            "--chat-id",
                            "1001",
                            "--user-id",
                            "u-01",
                            "--session-file",
                            str(sess),
                            "--json",
                        ],
                    )
            self.assertEqual(rc_bind, 0)
            bind_payload = json.loads(buf_bind.getvalue().strip())
            self.assertEqual(bind_payload.get("schema_version"), "gateway_telegram_map_v1")
            self.assertEqual(bind_payload.get("action"), "bind")
            self.assertEqual((bind_payload.get("binding") or {}).get("chat_id"), "1001")
            self.assertEqual(bind_payload.get("bindings_count"), 1)

            buf_get = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf_get):
                    rc_get = main(
                        [
                            "gateway",
                            "telegram",
                            "get",
                            "--chat-id",
                            "1001",
                            "--user-id",
                            "u-01",
                            "--json",
                        ],
                    )
            self.assertEqual(rc_get, 0)
            get_payload = json.loads(buf_get.getvalue().strip())
            self.assertIs(get_payload.get("ok"), True)
            self.assertEqual((get_payload.get("binding") or {}).get("session_file"), str(sess.resolve()))

            buf_list = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf_list):
                    rc_list = main(["gateway", "telegram", "list", "--json"])
            self.assertEqual(rc_list, 0)
            list_payload = json.loads(buf_list.getvalue().strip())
            self.assertEqual(list_payload.get("bindings_count"), 1)
            self.assertEqual(len(list_payload.get("bindings") or []), 1)

            buf_unbind = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf_unbind):
                    rc_unbind = main(
                        [
                            "gateway",
                            "telegram",
                            "unbind",
                            "--chat-id",
                            "1001",
                            "--user-id",
                            "u-01",
                            "--json",
                        ],
                    )
            self.assertEqual(rc_unbind, 0)
            unbind_payload = json.loads(buf_unbind.getvalue().strip())
            self.assertIs(unbind_payload.get("removed"), True)
            self.assertEqual(unbind_payload.get("bindings_count"), 0)

    def test_get_missing_returns_nonzero(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            buf = io.StringIO()
            err = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf), redirect_stderr(err):
                    rc = main(
                        [
                            "gateway",
                            "telegram",
                            "get",
                            "--chat-id",
                            "404",
                            "--user-id",
                            "nobody",
                            "--json",
                        ],
                    )
            self.assertEqual(rc, 2)
            payload = json.loads(buf.getvalue().strip())
            self.assertIs(payload.get("ok"), False)
            self.assertIsNone(payload.get("binding"))

    def test_resolve_update_creates_and_reuses_binding(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            update_file = root / "update.json"
            update_file.write_text(
                json.dumps(
                    {
                        "update_id": 777,
                        "message": {
                            "message_id": 10,
                            "chat": {"id": 5001},
                            "from": {"id": 9002},
                            "text": "hello",
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            buf1 = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf1):
                    rc1 = main(
                        [
                            "gateway",
                            "telegram",
                            "resolve-update",
                            "--update-file",
                            str(update_file),
                            "--create-missing",
                            "--session-template",
                            ".cai/gateway/sessions/tg-chat-{chat_id}-user-{user_id}.json",
                            "--json",
                        ],
                    )
            self.assertEqual(rc1, 0)
            p1 = json.loads(buf1.getvalue().strip())
            self.assertEqual(p1.get("action"), "resolve-update")
            self.assertEqual(p1.get("chat_id"), "5001")
            self.assertEqual(p1.get("user_id"), "9002")
            self.assertIs(p1.get("created"), True)
            sess1 = str((p1.get("binding") or {}).get("session_file") or "")
            # Windows returns backslashes in absolute paths; normalize before suffix match.
            sess1_norm = sess1.replace("\\", "/")
            self.assertTrue(
                sess1_norm.endswith(".cai/gateway/sessions/tg-chat-5001-user-9002.json"),
            )

            buf2 = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf2):
                    rc2 = main(
                        [
                            "gateway",
                            "telegram",
                            "resolve-update",
                            "--update-file",
                            str(update_file),
                            "--json",
                        ],
                    )
            self.assertEqual(rc2, 0)
            p2 = json.loads(buf2.getvalue().strip())
            self.assertIs(p2.get("created"), False)
            self.assertEqual(str((p2.get("binding") or {}).get("session_file") or ""), sess1)

    def test_resolve_update_missing_user_returns_nonzero(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            update_file = root / "bad-update.json"
            update_file.write_text(
                json.dumps(
                    {
                        "update_id": 778,
                        "message": {
                            "message_id": 11,
                            "chat": {"id": 5001},
                            "text": "no user",
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "gateway",
                            "telegram",
                            "resolve-update",
                            "--update-file",
                            str(update_file),
                            "--json",
                        ],
                    )
            self.assertEqual(rc, 2)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("action"), "resolve-update")
            self.assertEqual(payload.get("error"), "invalid_update")

    def test_webhook_serve_executes_update_and_writes_log(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                map_path = root / ".cai" / "gateway" / "telegram-session-map.json"
                log_path = root / ".cai" / "gateway" / "telegram-webhook-events.jsonl"
                from cai_agent import __main__ as m

                update = {
                    "update_id": 9001,
                    "message": {
                        "message_id": 3,
                        "chat": {"id": 2222},
                        "from": {"id": 3333},
                        "text": "ping",
                    },
                }

                payload = m._resolve_gateway_session_from_update(
                    root=root,
                    map_path=map_path,
                    update_obj=update,
                    create_missing=True,
                    session_template=".cai/gateway/sessions/tg-{chat_id}-{user_id}.json",
                )
                self.assertTrue(payload.get("ok"))

                goal = "Telegram inbound message from chat 2222 user 3333:\nping"
                with patch(
                    "cai_agent.__main__._execute_scheduled_goal",
                    return_value=(True, "answer from mock"),
                ) as mock_exec:
                    ok, answer = m._execute_scheduled_goal(
                        config_path=None,
                        workspace_hint=str(root),
                        workspace_override=str(root),
                        model_override=None,
                        goal=goal,
                    )
                self.assertTrue(ok)
                self.assertEqual(answer, "answer from mock")
                self.assertEqual(mock_exec.call_count, 1)

                log_path.parent.mkdir(parents=True, exist_ok=True)
                row = {
                    "ts": "2026-04-21T00:00:00+00:00",
                    "remote": "127.0.0.1",
                    "payload": payload,
                    "execution": {"triggered": True, "ok": ok, "answer_preview": answer},
                }
                with log_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")

            log_path = root / ".cai" / "gateway" / "telegram-webhook-events.jsonl"
            self.assertTrue(log_path.is_file())
            log_rows = [ln.strip() for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
            self.assertTrue(log_rows)
            item = json.loads(log_rows[-1])
            payload_row = item.get("payload") if isinstance(item, dict) else {}
            if not isinstance(payload_row, dict):
                payload_row = {}
            self.assertEqual(payload_row.get("chat_id"), "2222")
            self.assertEqual(payload_row.get("user_id"), "3333")
            execution = item.get("execution") if isinstance(item, dict) else {}
            if not isinstance(execution, dict):
                execution = {}
            self.assertTrue(execution.get("triggered"))
            self.assertTrue(execution.get("ok"))

    def test_send_telegram_message_success_and_failure(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                from cai_agent import __main__ as m

                with patch(
                    "cai_agent.__main__.urllib.request.urlopen",
                ) as mock_urlopen:
                    class _Resp:
                        def __enter__(self):
                            return self

                        def __exit__(self, exc_type, exc, tb):
                            return False

                        def read(self):
                            return b'{"ok": true, "result": {"message_id": 1}}'

                    mock_urlopen.return_value = _Resp()
                    ok, payload = m._send_telegram_message(
                        bot_token="tkn",
                        chat_id="100",
                        text="hello",
                        timeout_sec=5.0,
                    )
                self.assertTrue(ok)
                self.assertTrue(isinstance(payload, dict))
                self.assertTrue(payload.get("ok"))

                with patch(
                    "cai_agent.__main__.urllib.request.urlopen",
                    side_effect=URLError("boom"),
                ):
                    ok2, payload2 = m._send_telegram_message(
                        bot_token="tkn",
                        chat_id="100",
                        text="hello",
                        timeout_sec=5.0,
                    )
                self.assertFalse(ok2)
                self.assertEqual(payload2.get("error"), "send_failed")
