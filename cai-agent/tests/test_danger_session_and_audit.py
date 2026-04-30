"""P3-3 / P3-4: session MCP/http approvals and optional dangerous audit JSONL."""

from __future__ import annotations

import json
import os
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from cai_agent.config import Settings
from cai_agent.tools import (
    append_dangerous_audit_log,
    dispatch,
    grant_dangerous_approval_once,
    prepare_interactive_dangerous_dispatch,
    reset_dangerous_approval_budget_for_testing,
    register_session_fetch_http_host_danger_approval,
    register_session_mcp_tool_danger_approval,
    session_danger_preapproved,
)


def _settings_unrestricted_audit(root: Path) -> Settings:
    content = textwrap.dedent(
        f"""
        [llm]
        base_url = "http://localhost:1/v1"
        model = "m"
        api_key = "k"
        [agent]
        workspace = "{root.as_posix()}"
        [permissions]
        run_command = "allow"
        fetch_url = "allow"
        [fetch_url]
        enabled = true
        unrestricted = true
        [safety]
        unrestricted_mode = true
        dangerous_confirmation_required = true
        dangerous_audit_log_enabled = true
        """,
    )
    with tempfile.NamedTemporaryFile(
        "w",
        suffix=".toml",
        delete=False,
        encoding="utf-8",
    ) as f:
        f.write(content)
        path = f.name
    try:
        return Settings.from_env(config_path=path)
    finally:
        os.unlink(path)


class SessionDangerApprovalsTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_dangerous_approval_budget_for_testing()
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name).resolve()

    def tearDown(self) -> None:
        self._td.cleanup()

    def test_session_mcp_skips_prepare_modal_and_dispatch_without_budget(self) -> None:
        s = _settings_unrestricted_audit(self.root)
        register_session_mcp_tool_danger_approval("my_mcp_tool")
        self.assertTrue(
            session_danger_preapproved(s, "mcp_call_tool", {"name": "my_mcp_tool", "args": {}}),
        )
        ok, msg = prepare_interactive_dangerous_dispatch(
            s,
            "mcp_call_tool",
            {"name": "my_mcp_tool", "args": {}},
            interactive_confirm=lambda _p: False,
        )
        self.assertTrue(ok)
        self.assertIsNone(msg)
        with patch("cai_agent.tools.tool_mcp_call_tool", return_value="ok"):
            out = dispatch(s, "mcp_call_tool", {"name": "my_mcp_tool", "args": {}})
        self.assertEqual(out, "ok")

    def test_session_fetch_http_host_dispatch_without_budget(self) -> None:
        s = _settings_unrestricted_audit(self.root)
        register_session_fetch_http_host_danger_approval("example.org")
        self.assertTrue(
            session_danger_preapproved(
                s,
                "fetch_url",
                {"url": "http://example.org/x"},
            ),
        )
        with patch("cai_agent.tools.tool_fetch_url", return_value="fetched"):
            out = dispatch(s, "fetch_url", {"url": "http://example.org/x"})
        self.assertEqual(out, "fetched")

    def test_audit_jsonl_on_grant_and_dispatch(self) -> None:
        s = _settings_unrestricted_audit(self.root)
        log_path = self.root / ".cai" / "dangerous-approve.jsonl"
        self.assertFalse(log_path.exists())
        grant_dangerous_approval_once(settings=s, audit_via="test")
        self.assertTrue(log_path.is_file())
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertGreaterEqual(len(lines), 1)
        row = json.loads(lines[0])
        self.assertEqual(row.get("schema"), "dangerous_audit_event_v1")
        self.assertEqual(row.get("event"), "dangerous_grant")
        self.assertEqual((row.get("detail") or {}).get("via"), "test")

        with patch("cai_agent.tools.tool_mcp_call_tool", return_value="mcp-ok"):
            dispatch(s, "mcp_call_tool", {"name": "x", "args": {}})
        blob = log_path.read_text(encoding="utf-8")
        self.assertIn("dangerous_executed", blob)
        self.assertIn("budget", blob)

    def test_append_respects_disabled_audit(self) -> None:
        content = textwrap.dedent(
            f"""
            [llm]
            base_url = "http://localhost:1/v1"
            model = "m"
            api_key = "k"
            [agent]
            workspace = "{self.root.as_posix()}"
            [permissions]
            run_command = "allow"
            [safety]
            unrestricted_mode = true
            dangerous_confirmation_required = true
            dangerous_audit_log_enabled = false
            """,
        )
        with tempfile.NamedTemporaryFile(
            "w",
            suffix=".toml",
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(content)
            path = f.name
        try:
            s = Settings.from_env(config_path=path)
        finally:
            os.unlink(path)
        append_dangerous_audit_log(s, "should_not_write", {})
        self.assertFalse((self.root / ".cai" / "dangerous-approve.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
