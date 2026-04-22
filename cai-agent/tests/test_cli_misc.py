from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

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
        self.assertEqual(payload.get("schema_version"), "mcp_check_result_v1")
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
        self.assertIn("fallback_hint", payload)
        hint = payload.get("fallback_hint") or {}
        self.assertTrue(isinstance(hint, dict))
        self.assertEqual(hint.get("doc_path"), "docs/WEBSEARCH_NOTEBOOK_MCP.zh-CN.md")

    def test_mcp_check_json_print_template_for_notebook(self) -> None:
        old = os.environ.get("MCP_ENABLED")
        try:
            os.environ.pop("MCP_ENABLED", None)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(
                    [
                        "mcp-check",
                        "--json",
                        "--preset",
                        "notebook",
                        "--print-template",
                    ],
                )
        finally:
            if old is None:
                os.environ.pop("MCP_ENABLED", None)
            else:
                os.environ["MCP_ENABLED"] = old

        self.assertIn(rc, (0, 2))
        payload = json.loads(buf.getvalue().strip())
        tmpl = payload.get("template")
        self.assertTrue(isinstance(tmpl, str))
        self.assertIn("mcp_enabled = true", str(tmpl))
        self.assertIn("preset = notebook", str(tmpl))


class PluginsCliTests(unittest.TestCase):
    def test_plugins_json_returns_0(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["plugins", "--json"])
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue().strip())
        self.assertIn("project_root", payload)
        self.assertIn("components", payload)

    def test_plugins_fail_on_min_health(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["plugins", "--json", "--fail-on-min-health", "101"])
        self.assertEqual(rc, 2)
        payload = json.loads(buf.getvalue().strip())
        self.assertLess(int(payload.get("health_score") or 0), 101)


class GateSecuritySchemaTests(unittest.TestCase):
    def test_quality_gate_result_has_schema_version(self) -> None:
        from dataclasses import replace

        from cai_agent.config import Settings
        from cai_agent.quality_gate import run_quality_gate

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "cai-agent.toml").write_text(
                '[llm]\nbase_url = "http://x/v1"\nmodel = "m"\napi_key = "k"\n',
                encoding="utf-8",
            )
            s = Settings.from_env(config_path=str(root / "cai-agent.toml"))
            s = replace(s, workspace=str(root))
            out = run_quality_gate(
                s,
                enable_compile=False,
                enable_test=False,
                enable_lint=False,
                enable_typecheck=False,
                enable_security_scan=False,
            )
            self.assertEqual(out.get("schema_version"), "quality_gate_result_v1")

    def test_security_scan_result_has_schema_version(self) -> None:
        from dataclasses import replace

        from cai_agent.config import Settings
        from cai_agent.security_scan import run_security_scan

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "cai-agent.toml").write_text(
                '[llm]\nbase_url = "http://x/v1"\nmodel = "m"\napi_key = "k"\n',
                encoding="utf-8",
            )
            s = Settings.from_env(config_path=str(root / "cai-agent.toml"))
            s = replace(s, workspace=str(root))
            out = run_security_scan(s)
            self.assertEqual(out.get("schema_version"), "security_scan_result_v1")


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
