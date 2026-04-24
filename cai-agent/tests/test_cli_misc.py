from __future__ import annotations

import argparse
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

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
        self.assertEqual(preset.get("onboarding_path"), "docs/ONBOARDING.zh-CN.md")
        hint = payload.get("fallback_hint") or {}
        self.assertTrue(isinstance(hint, dict))
        self.assertEqual(hint.get("doc_path"), "docs/WEBSEARCH_NOTEBOOK_MCP.zh-CN.md")
        self.assertEqual(hint.get("onboarding_path"), "docs/ONBOARDING.zh-CN.md")

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
        self.assertIn("docs/ONBOARDING.zh-CN.md", str(tmpl))

    def test_mcp_check_json_with_combined_preset(self) -> None:
        old = os.environ.get("MCP_ENABLED")
        try:
            os.environ.pop("MCP_ENABLED", None)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(["mcp-check", "--json", "--preset", "websearch/notebook", "--list-only"])
        finally:
            if old is None:
                os.environ.pop("MCP_ENABLED", None)
            else:
                os.environ["MCP_ENABLED"] = old

        self.assertIn(rc, (0, 2))
        payload = json.loads(buf.getvalue().strip())
        preset = payload.get("preset") or {}
        presets = payload.get("presets") or []
        self.assertEqual(preset.get("name"), "websearch/notebook")
        self.assertEqual(preset.get("selected_presets"), ["websearch", "notebook"])
        self.assertTrue(isinstance(presets, list))
        self.assertEqual(len(presets), 2)
        self.assertEqual([row.get("name") for row in presets], ["websearch", "notebook"])
        self.assertIn("next_step", payload)

    def test_mcp_check_text_prints_quickstart_for_preset(self) -> None:
        old = os.environ.get("MCP_ENABLED")
        try:
            os.environ.pop("MCP_ENABLED", None)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(["mcp-check", "--preset", "websearch", "--list-only"])
        finally:
            if old is None:
                os.environ.pop("MCP_ENABLED", None)
            else:
                os.environ["MCP_ENABLED"] = old

        self.assertIn(rc, (0, 2))
        out = buf.getvalue()
        self.assertIn("--- preset quickstart ---", out)
        self.assertIn("cai-agent mcp-check --json --preset websearch --list-only", out)
        self.assertIn("docs=docs/WEBSEARCH_NOTEBOOK_MCP.zh-CN.md", out)


class PluginsCliTests(unittest.TestCase):
    def test_plugins_json_returns_0(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["plugins", "--json"])
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue().strip())
        self.assertEqual(payload.get("schema_version"), "plugins_surface_v1")
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


class CommandsAgentsJsonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.cfg = root / "cai-agent.toml"
        self.cfg.write_text(
            '[llm]\nbase_url = "http://localhost/v1"\nmodel = "m"\napi_key = "k"\n',
            encoding="utf-8",
        )
        (root / "commands").mkdir()
        (root / "commands" / "hello.md").write_text("# x", encoding="utf-8")
        (root / "agents").mkdir()
        (root / "agents" / "coder.md").write_text("# y", encoding="utf-8")

    def test_commands_json_envelope(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["commands", "--config", str(self.cfg), "--json"])
        self.assertEqual(rc, 0)
        o = json.loads(buf.getvalue().strip())
        self.assertEqual(o.get("schema_version"), "commands_list_v1")
        self.assertEqual(o.get("commands"), ["hello"])

    def test_agents_json_envelope(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["agents", "--config", str(self.cfg), "--json"])
        self.assertEqual(rc, 0)
        o = json.loads(buf.getvalue().strip())
        self.assertEqual(o.get("schema_version"), "agents_list_v1")
        self.assertEqual(o.get("agents"), ["coder"])


class CostBudgetCliTests(unittest.TestCase):
    def test_cost_budget_json_has_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = root / "cai-agent.toml"
            cfg.write_text(
                '[llm]\nbase_url = "http://x/v1"\nmodel = "m"\napi_key = "k"\n'
                "[cost]\nbudget_max_tokens = 1000\n",
                encoding="utf-8",
            )
            prev = os.environ.get("CAI_CONFIG")
            try:
                os.environ["CAI_CONFIG"] = str(cfg)
                buf = io.StringIO()
                with (
                    patch("cai_agent.__main__.os.getcwd", return_value=str(root)),
                    patch(
                        "cai_agent.__main__.aggregate_sessions",
                        return_value={"total_tokens": 100},
                    ),
                ):
                    with redirect_stdout(buf):
                        rc = main(["cost", "budget"])
            finally:
                if prev is None:
                    os.environ.pop("CAI_CONFIG", None)
                else:
                    os.environ["CAI_CONFIG"] = prev
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("schema_version"), "cost_budget_v1")
            self.assertEqual(payload.get("state"), "pass")
            self.assertEqual(payload.get("total_tokens"), 100)
            self.assertEqual(payload.get("max_tokens"), 1000)
            ex = payload.get("explain")
            self.assertIsInstance(ex, dict)
            self.assertEqual(ex.get("schema_version"), "cost_budget_explain_v1")
            self.assertIn("summary_zh", ex)


class ExportCliTests(unittest.TestCase):
    def test_export_cursor_json_has_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = root / "cai-agent.toml"
            cfg.write_text(
                '[llm]\nbase_url = "http://localhost:9/v1"\nmodel = "m"\napi_key = "k"\n',
                encoding="utf-8",
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(["export", "--config", str(cfg), "--target", "cursor"])
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("schema_version"), "export_cli_v1")
            self.assertEqual(payload.get("target"), "cursor")
            self.assertEqual(payload.get("mode"), "structured")
            self.assertIn("output_dir", payload)
            self.assertIn("manifest", payload)


class MainDispatchFallbackTests(unittest.TestCase):
    def test_defensive_unknown_subcommand_returns_2(self) -> None:
        """S1-03: main() fallthrough uses exit 2 with stderr (never expected in production)."""
        ns = argparse.Namespace(command="__cai_test_unknown_subcommand__")
        err = io.StringIO()
        with patch.object(argparse.ArgumentParser, "parse_args", return_value=ns):
            with redirect_stderr(err):
                rc = main([])
        self.assertEqual(rc, 2)
        self.assertIn("__cai_test_unknown_subcommand__", err.getvalue())
        self.assertIn("未处理", err.getvalue())
