from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import tempfile
import unittest
import uuid
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cai_agent.__main__ import main


class ApiCliTests(unittest.TestCase):
    def test_api_openapi_json_outputs_unified_contract(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["api", "openapi", "--json"])

        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue().strip())
        self.assertEqual(payload.get("openapi"), "3.1.0")
        self.assertEqual((payload.get("x-cai-contract") or {}).get("schema_version"), "api_openapi_v1")
        paths = payload.get("paths") or {}
        self.assertIn("/v1/status", paths)
        self.assertIn("/v1/doctor/summary", paths)
        self.assertIn("/v1/models", paths)
        self.assertIn("/v1/chat/completions", paths)
        self.assertIn("/v1/ops/dashboard", paths)


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

    def test_mcp_check_help_shows_epilog(self) -> None:
        buf = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(err):
            with self.assertRaises(SystemExit) as ctx:
                main(["mcp-check", "--help"])
        self.assertEqual(ctx.exception.code, 0)
        combined = buf.getvalue() + err.getvalue()
        self.assertIn("WEBSEARCH_NOTEBOOK_MCP", combined)
        self.assertIn("websearch/notebook", combined)


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


class OnboardingCliTests(unittest.TestCase):
    def test_onboarding_json_without_config(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(["onboarding", "-w", str(root), "--json"])
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("schema_version"), "onboarding_quickstart_v1")
            self.assertEqual(payload.get("workspace"), str(root.resolve()))
            self.assertFalse(payload.get("config_exists"))
            flow = payload.get("recommended_flow") or []
            self.assertTrue(isinstance(flow, list) and flow)
            self.assertEqual(flow[0], "cai-agent init --preset starter")
            self.assertIn("cai-agent sessions --recap --json", flow)
            flows = payload.get("recovery_flows") or {}
            self.assertEqual(flows.get("schema_version"), "install_recovery_flows_v1")
            self.assertIn("cai-agent init --preset starter", payload.get("next_steps") or [])
            self.assertIn("cai-agent repair --dry-run --json", payload.get("next_steps") or [])

    def test_onboarding_json_with_config(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "cai-agent.toml").write_text(
                '[llm]\nbase_url = "http://127.0.0.1:9/v1"\nmodel = "m"\napi_key = "k"\n',
                encoding="utf-8",
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(["onboarding", "--config", str(root / "cai-agent.toml"), "-w", str(root), "--json"])
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertTrue(payload.get("config_exists"))
            flow = payload.get("recommended_flow") or []
            self.assertTrue(isinstance(flow, list))
            self.assertEqual(flow[0], "cai-agent doctor")
            self.assertIn("cai-agent ui", flow)
            self.assertEqual((payload.get("recovery_flows") or {}).get("schema_version"), "install_recovery_flows_v1")
            self.assertIn("cai-agent doctor --json", payload.get("next_steps") or [])


class ExperiencePhase2CliTests(unittest.TestCase):
    def test_root_help_shows_onboarding_quickstart(self) -> None:
        buf = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(err):
            with self.assertRaises(SystemExit) as ctx:
                main(["--help"])
        self.assertEqual(ctx.exception.code, 0)
        out = buf.getvalue() + err.getvalue()
        self.assertIn("Quickstart", out)
        self.assertIn("cai-agent onboarding", out)

    def test_doctor_missing_config_prints_onboarding_hint(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            missing_cfg = str(Path(td) / "missing.toml")
            out = io.StringIO()
            err = io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = main(["doctor", "--config", missing_cfg])
            self.assertEqual(rc, 2)
            em = err.getvalue()
            self.assertIn("doctor: 未检测到可用配置", em)
            self.assertIn("cai-agent onboarding", em)

    def test_sessions_help_shows_continue_quickstart(self) -> None:
        buf = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(err):
            with self.assertRaises(SystemExit) as ctx:
                main(["sessions", "--help"])
        self.assertEqual(ctx.exception.code, 0)
        out = buf.getvalue() + err.getvalue()
        self.assertIn("Quickstart", out)
        self.assertIn("sessions --recap --json", out)
        self.assertIn("cai-agent continue", out)

    def test_continue_help_shows_how_to_find_sessions(self) -> None:
        buf = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(err):
            with self.assertRaises(SystemExit) as ctx:
                main(["continue", "--help"])
        self.assertEqual(ctx.exception.code, 0)
        out = buf.getvalue() + err.getvalue()
        self.assertIn("sessions --details", out)
        self.assertIn("sessions --recap --json", out)

    def test_continue_json_load_session_failed_includes_hints(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = root / "cai-agent.toml"
            cfg.write_text(
                '[llm]\nbase_url = "http://127.0.0.1:9/v1"\nmodel = "m"\napi_key = "k"\n',
                encoding="utf-8",
            )
            missing_session = root / "missing-session.json"
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(
                    [
                        "continue",
                        "--config",
                        str(cfg),
                        str(missing_session),
                        "继续",
                        "--json",
                    ],
                )
            self.assertEqual(rc, 2)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("error"), "load_session_failed")
            hints = payload.get("hints") or []
            self.assertTrue(isinstance(hints, list) and hints)
            self.assertIn("cai-agent sessions --details", hints)

    def test_continue_text_invalid_session_prints_hints(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = root / "cai-agent.toml"
            cfg.write_text(
                '[llm]\nbase_url = "http://127.0.0.1:9/v1"\nmodel = "m"\napi_key = "k"\n',
                encoding="utf-8",
            )
            bad_session = root / "bad-session.json"
            bad_session.write_text("{}", encoding="utf-8")
            err = io.StringIO()
            with redirect_stderr(err):
                rc = main(
                    [
                        "continue",
                        "--config",
                        str(cfg),
                        str(bad_session),
                        "继续",
                    ],
                )
            self.assertEqual(rc, 2)
            em = err.getvalue()
            self.assertIn("会话文件不合法", em)
            self.assertIn("hint: cai-agent sessions --details", em)

    def test_command_not_found_json_includes_discovery_hints(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = root / "cai-agent.toml"
            cfg.write_text(
                '[llm]\nbase_url = "http://127.0.0.1:9/v1"\nmodel = "m"\napi_key = "k"\n',
                encoding="utf-8",
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(["command", "--config", str(cfg), "not-exist", "执行任务", "--json"])
            self.assertEqual(rc, 2)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("error"), "command_not_found")
            hints = payload.get("hints") or []
            self.assertIn("cai-agent commands --json", hints)

    def test_agent_not_found_text_prints_hints(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = root / "cai-agent.toml"
            cfg.write_text(
                '[llm]\nbase_url = "http://127.0.0.1:9/v1"\nmodel = "m"\napi_key = "k"\n',
                encoding="utf-8",
            )
            err = io.StringIO()
            with redirect_stderr(err):
                rc = main(["agent", "--config", str(cfg), "not-exist-agent", "执行任务"])
            self.assertEqual(rc, 2)
            em = err.getvalue()
            self.assertIn("子代理模板不存在", em)
            self.assertIn("hint: cai-agent agents --json", em)


class CommandsAgentsJsonTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path.cwd() / ".tmp-tests" / f"commands-agents-{uuid.uuid4().hex}"
        root.mkdir(parents=True)
        self.root = root
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
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
        self.assertIn("hello", o.get("commands"))

    def test_commands_json_uses_workspace_when_config_is_global(self) -> None:
        workspace = self.root / "workspace"
        workspace.mkdir()
        (workspace / "commands").mkdir()
        (workspace / "commands" / "code-review.md").write_text("# review", encoding="utf-8")
        global_dir = self.root / "global"
        global_dir.mkdir()
        global_cfg = global_dir / "cai-agent.toml"
        global_cfg.write_text(
            '[llm]\nbase_url = "http://localhost/v1"\nmodel = "m"\napi_key = "k"\n',
            encoding="utf-8",
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["commands", "--config", str(global_cfg), "-w", str(workspace), "--json"])
        self.assertEqual(rc, 0)
        o = json.loads(buf.getvalue().strip())
        self.assertIn("code-review", o.get("commands"))

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

    def test_cost_report_json_includes_compact_policy_explain(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = root / "cai-agent.toml"
            cfg.write_text(
                '[llm]\nbase_url = "http://x/v1"\nmodel = "m"\napi_key = "k"\n'
                "[cost]\nbudget_max_tokens = 2000\n",
                encoding="utf-8",
            )
            prev = os.environ.get("CAI_CONFIG")
            try:
                os.environ["CAI_CONFIG"] = str(cfg)
                buf = io.StringIO()
                with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                    with redirect_stdout(buf):
                        rc = main(["cost", "report", "--json"])
            finally:
                if prev is None:
                    os.environ.pop("CAI_CONFIG", None)
                else:
                    os.environ["CAI_CONFIG"] = prev
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("schema_version"), "cost_by_profile_v1")
            cpe = payload.get("compact_policy_explain_v1")
            self.assertIsInstance(cpe, dict)
            self.assertEqual(cpe.get("schema_version"), "compact_policy_explain_v1")
            self.assertEqual(cpe.get("cost_budget_max_tokens"), 2000)

    def test_cost_report_text_ok(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = root / "cai-agent.toml"
            cfg.write_text(
                '[llm]\nbase_url = "http://x/v1"\nmodel = "m"\napi_key = "k"\n',
                encoding="utf-8",
            )
            prev = os.environ.get("CAI_CONFIG")
            try:
                os.environ["CAI_CONFIG"] = str(cfg)
                buf = io.StringIO()
                with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                    with redirect_stdout(buf):
                        rc = main(["cost", "report"])
            finally:
                if prev is None:
                    os.environ.pop("CAI_CONFIG", None)
                else:
                    os.environ["CAI_CONFIG"] = prev
            self.assertEqual(rc, 0)
            out = buf.getvalue()
            self.assertIn("cost report", out.lower())
            self.assertIn("--json", out)


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
            self.assertIn("local_catalog", payload)
            catalog_path = Path(str(payload.get("local_catalog")))
            self.assertTrue(catalog_path.is_file())
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            self.assertEqual(catalog.get("schema_version"), "local_catalog_v1")
            manifest = json.loads(Path(str(payload.get("manifest"))).read_text(encoding="utf-8"))
            self.assertEqual(manifest.get("local_catalog_schema_version"), "local_catalog_v1")
            self.assertEqual(manifest.get("active_memory_provider"), "local_entries_jsonl")
            self.assertEqual(manifest.get("active_memory_provider_source"), "default")


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
