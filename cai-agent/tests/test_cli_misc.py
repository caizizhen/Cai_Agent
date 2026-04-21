from __future__ import annotations

import io
import json
import os
import unittest
from contextlib import redirect_stdout

from cai_agent.__main__ import main


class McpCheckCliTests(unittest.TestCase):
    def test_mcp_check_json_never_crashes(self) -> None:
        """mcp-check --json always prints one JSON line; exit 0 if probe ok else 2."""
        old = os.environ.get("MCP_ENABLED")
        try:
            os.environ.pop("MCP_ENABLED", None)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(["mcp-check", "--json"])
        finally:
            if old is None:
                os.environ.pop("MCP_ENABLED", None)
            else:
                os.environ["MCP_ENABLED"] = old

        self.assertIn(rc, (0, 2))
        line = buf.getvalue().strip().splitlines()[-1]
        payload = json.loads(line)
        self.assertIn("ok", payload)
        self.assertEqual(rc == 0, bool(payload["ok"]))

    def test_mcp_check_json_with_websearch_preset(self) -> None:
        old = os.environ.get("MCP_ENABLED")
        try:
            os.environ.pop("MCP_ENABLED", None)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(["mcp-check", "--json", "--preset", "websearch", "--list-only"])
        finally:
            if old is None:
                os.environ.pop("MCP_ENABLED", None)
            else:
                os.environ["MCP_ENABLED"] = old

        self.assertIn(rc, (0, 2))
        payload = json.loads(buf.getvalue().strip())
        preset = payload.get("preset")
        self.assertTrue(isinstance(preset, dict))
        self.assertEqual(preset.get("name"), "websearch")
        self.assertIn("recommended_tools", preset)
        self.assertIn("matched_tools", preset)
        self.assertIn("missing_tools", preset)


class PluginsCliTests(unittest.TestCase):
    def test_plugins_json_returns_0(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["plugins", "--json"])
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue().strip())
        self.assertIn("project_root", payload)
        self.assertIn("components", payload)


class ObserveCliTests(unittest.TestCase):
    def test_observe_json_returns_0(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["observe", "--json", "--limit", "5"])
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue().strip())
        self.assertEqual(payload.get("schema_version"), "1.1")
        self.assertIn("task", payload)
        self.assertEqual(payload["task"].get("type"), "observe")
        self.assertIn("events", payload)
        self.assertTrue(isinstance(payload["events"], list))
        ag = payload.get("aggregates") or {}
        self.assertIn("run_events_total", ag)
        self.assertIn("sessions_with_events", ag)
