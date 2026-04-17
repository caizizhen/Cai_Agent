from __future__ import annotations

import io
import json
import os
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cai_agent.__main__ import main
from cai_agent.session import save_session


class PlanJsonSchemaTests(unittest.TestCase):
    def test_plan_json_has_stable_schema(self) -> None:
        prev_mock = os.environ.get("CAI_MOCK")
        prev_cfg = os.environ.get("CAI_CONFIG")
        os.environ["CAI_MOCK"] = "1"
        cfg: str | None = None
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
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(["plan", "do", "something", "--json"])
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
        payload = json.loads(buf.getvalue().strip())
        self.assertEqual(payload.get("plan_schema_version"), "1.0")
        self.assertTrue(payload.get("ok", False))
        self.assertIn("generated_at", payload)
        self.assertIn("task", payload)
        self.assertEqual(payload["task"].get("type"), "plan")

    def test_plan_json_llm_error_envelope(self) -> None:
        prev_mock = os.environ.get("CAI_MOCK")
        prev_cfg = os.environ.get("CAI_CONFIG")
        os.environ.pop("CAI_MOCK", None)
        cfg: str | None = None
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
            buf = io.StringIO()
            with patch(
                "cai_agent.__main__.chat_completion",
                side_effect=RuntimeError("boom"),
            ):
                with redirect_stdout(buf):
                    rc = main(["plan", "my goal", "--json"])
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

        self.assertEqual(rc, 2)
        payload = json.loads(buf.getvalue().strip())
        self.assertEqual(payload.get("plan_schema_version"), "1.0")
        self.assertIs(payload.get("ok"), False)
        self.assertEqual(payload.get("error"), "llm_error")
        self.assertIn("boom", str(payload.get("message", "")))
        self.assertEqual(payload["task"].get("status"), "failed")

    def test_plan_json_config_not_found(self) -> None:
        buf = io.StringIO()
        missing = os.path.join(tempfile.gettempdir(), "cai-no-such-config-999999.toml")
        with redirect_stdout(buf):
            rc = main(
                [
                    "plan",
                    "--config",
                    missing,
                    "hello",
                    "--json",
                ],
            )
        self.assertEqual(rc, 2)
        payload = json.loads(buf.getvalue().strip())
        self.assertEqual(payload.get("error"), "config_not_found")
        self.assertIs(payload.get("ok"), False)


class SessionsJsonExtraTests(unittest.TestCase):
    def test_sessions_json_includes_events_without_details(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            save_session(
                str(root / ".cai-session-z.json"),
                {
                    "version": 2,
                    "run_schema_version": "1.0",
                    "goal": "g",
                    "workspace": td,
                    "elapsed_ms": 1,
                    "total_tokens": 3,
                    "prompt_tokens": 2,
                    "completion_tokens": 1,
                    "error_count": 0,
                    "task": {
                        "task_id": "run-zzzzzzzzzz",
                        "type": "run",
                        "status": "completed",
                        "started_at": 0.0,
                        "ended_at": 1.0,
                        "elapsed_ms": 1,
                        "error": None,
                    },
                    "events": [{"event": "run.started"}, {"event": "run.finished"}],
                },
            )
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["sessions", "--pattern", ".cai-session*.json", "--json"])
            self.assertEqual(rc, 0)
            arr = json.loads(buf.getvalue().strip())
            self.assertEqual(len(arr), 1)
            row = arr[0]
            self.assertEqual(row.get("events_count"), 2)
            self.assertEqual(row.get("run_schema_version"), "1.0")
            self.assertEqual(row.get("task_id"), "run-zzzzzzzzzz")
