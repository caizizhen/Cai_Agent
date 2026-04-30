from __future__ import annotations

import io
import json
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cai_agent.__main__ import main
from cai_agent.session import save_session


def _tmp_root() -> Path:
    root = Path.cwd() / ".tmp-tests" / "sessions-compact-eval"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _case_dir() -> Path:
    root = _tmp_root() / uuid.uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root


class SessionsCompactEvalCliTests(unittest.TestCase):
    def test_sessions_compact_eval_json(self) -> None:
        root = _case_dir()
        try:
            save_session(
                str(root / "session-compact.json"),
                {
                    "version": 2,
                    "goal": "compact eval",
                    "messages": [
                        {"role": "system", "content": "system prompt"},
                        {"role": "user", "content": "goal marker-alpha"},
                        {"role": "assistant", "content": "older " * 1200},
                        {
                            "role": "user",
                            "content": json.dumps(
                                {
                                    "tool": "read_file",
                                    "result": "cai-agent/src/cai_agent/context_compaction.py\n"
                                    + ("body " * 1200),
                                },
                                ensure_ascii=False,
                            ),
                        },
                        {"role": "assistant", "content": "recent assistant"},
                        {"role": "user", "content": "recent user marker-omega"},
                    ],
                    "task": {"task_id": "ctx-compact-cli"},
                },
            )
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "sessions",
                            "--compact-eval",
                            "--json",
                            "--pattern",
                            "session*.json",
                            "--compact-keep-tail",
                            "2",
                            "--compact-required-marker",
                            "marker-alpha",
                            "--compact-required-marker",
                            "marker-omega",
                        ],
                    )
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("schema_version"), "sessions_compact_eval_v1")
            self.assertTrue((payload.get("summary") or {}).get("passed"))
            rows = payload.get("sessions") or []
            self.assertEqual(len(rows), 1)
            ev = rows[0].get("evaluation") or {}
            self.assertEqual(ev.get("schema_version"), "context_compaction_eval_v1")
            self.assertTrue(ev.get("passed"))
        finally:
            pass

    def test_sessions_compact_eval_returns_2_on_missing_marker(self) -> None:
        root = _case_dir()
        try:
            save_session(
                str(root / "session-compact-fail.json"),
                {
                    "version": 2,
                    "messages": [
                        {"role": "system", "content": "system prompt"},
                        {"role": "user", "content": "goal marker-alpha"},
                        {"role": "assistant", "content": "older " * 1200},
                        {"role": "user", "content": "middle " * 1200},
                        {"role": "assistant", "content": "recent assistant"},
                        {"role": "user", "content": "recent user"},
                    ],
                },
            )
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "sessions",
                            "--compact-eval",
                            "--json",
                            "--pattern",
                            "session*.json",
                            "--compact-keep-tail",
                            "2",
                            "--compact-required-marker",
                            "missing-marker",
                        ],
                    )
            self.assertEqual(rc, 2)
            payload = json.loads(buf.getvalue().strip())
            self.assertFalse((payload.get("summary") or {}).get("passed"))
        finally:
            pass
