from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cai_agent.__main__ import main


class ToolProviderContractCliTests(unittest.TestCase):
    def test_tools_contract_json_schema(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = root / "cai-agent.toml"
            cfg.write_text(
                '[llm]\nprovider = "openai_compatible"\nbase_url = "http://127.0.0.1:9/v1"\n'
                'model = "m"\napi_key = "k"\n\n[agent]\nmock = true\n',
                encoding="utf-8",
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(["tools", "--config", str(cfg), "contract", "--json"])
            self.assertEqual(rc, 0)
            pl = json.loads(buf.getvalue().strip())
            self.assertEqual(pl.get("schema_version"), "tool_provider_contract_v1")
            providers = pl.get("providers") or {}
            self.assertIn("web", providers)
            self.assertIn("image", providers)
            self.assertIn("browser", providers)
            self.assertIn("tts", providers)
            self.assertEqual((pl.get("guard") or {}).get("schema_version"), "tool_gateway_guard_v1")

    def test_tools_registry_list_enable_disable_flow(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = root / "cai-agent.toml"
            cfg.write_text(
                '[llm]\nprovider = "openai_compatible"\nbase_url = "http://127.0.0.1:9/v1"\n'
                'model = "m"\napi_key = "k"\n\n[agent]\nmock = true\n',
                encoding="utf-8",
            )
            buf_enable = io.StringIO()
            with redirect_stdout(buf_enable):
                rc_enable = main(["tools", "--config", str(cfg), "enable", "image", "--json"])
            self.assertEqual(rc_enable, 0)
            p_enable = json.loads(buf_enable.getvalue().strip())
            self.assertEqual(p_enable.get("schema_version"), "tool_provider_toggle_v1")
            self.assertIs(p_enable.get("enabled"), True)

            buf_list = io.StringIO()
            with redirect_stdout(buf_list):
                rc_list = main(["tools", "--config", str(cfg), "list", "--json"])
            self.assertEqual(rc_list, 0)
            p_list = json.loads(buf_list.getvalue().strip())
            self.assertEqual(p_list.get("schema_version"), "tool_provider_registry_v1")
            image = (p_list.get("providers") or {}).get("image") or {}
            self.assertIs(image.get("enabled"), True)
            self.assertEqual(image.get("enabled_source"), "config")

            buf_disable = io.StringIO()
            with redirect_stdout(buf_disable):
                rc_disable = main(["tools", "--config", str(cfg), "disable", "image", "--json"])
            self.assertEqual(rc_disable, 0)
            p_disable = json.loads(buf_disable.getvalue().strip())
            self.assertIs(p_disable.get("enabled"), False)

    def test_tools_bridge_json_uses_mcp_preset_reports(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = root / "cai-agent.toml"
            cfg.write_text(
                '[llm]\nprovider = "openai_compatible"\nbase_url = "http://127.0.0.1:9/v1"\n'
                'model = "m"\napi_key = "k"\n\n[agent]\nmock = true\nmcp_enabled = true\nmcp_base_url = "http://127.0.0.1:8787"\n',
                encoding="utf-8",
            )
            buf = io.StringIO()
            from unittest.mock import patch

            with patch("cai_agent.tool_provider.dispatch", return_value="search\tWeb search\nnotebook\tJupyter\n"):
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "tools",
                            "--config",
                            str(cfg),
                            "bridge",
                            "--preset",
                            "websearch/notebook",
                            "--json",
                        ],
                    )
            self.assertEqual(rc, 0)
            out = json.loads(buf.getvalue().strip())
            self.assertEqual(out.get("schema_version"), "tool_mcp_bridge_v1")
            self.assertEqual(out.get("preset"), "websearch/notebook")
            self.assertIn("websearch", out.get("selected_presets") or [])
            self.assertIn("notebook", out.get("selected_presets") or [])
            self.assertTrue((out.get("tools_count") or 0) >= 2)

    def test_tools_web_fetch_success_and_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = root / "cai-agent.toml"
            cfg.write_text(
                '[llm]\nprovider = "openai_compatible"\nbase_url = "http://127.0.0.1:9/v1"\n'
                'model = "m"\napi_key = "k"\n\n[agent]\nmock = true\n'
                '[fetch_url]\nenabled = true\nunrestricted = true\n'
                '[permissions]\nfetch_url = "allow"\n',
                encoding="utf-8",
            )
            buf_ok = io.StringIO()
            with patch("cai_agent.tool_provider.dispatch", return_value="[fetch_url] HTTP 200\nok"):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                    with redirect_stdout(buf_ok):
                        rc_ok = main(
                            [
                                "tools",
                                "--config",
                                str(cfg),
                                "web-fetch",
                                "--url",
                                "https://example.com",
                                "--json",
                            ],
                        )
            self.assertEqual(rc_ok, 0)
            p_ok = json.loads(buf_ok.getvalue().strip())
            self.assertEqual(p_ok.get("schema_version"), "tool_provider_web_fetch_v1")
            self.assertIs(p_ok.get("ok"), True)

            # disable web then web-fetch should fail fast
            buf_dis = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf_dis):
                    rc_disable = main(["tools", "--config", str(cfg), "disable", "web", "--json"])
            self.assertEqual(rc_disable, 0)
            buf_fail = io.StringIO()
            with patch("cai_agent.tool_provider.dispatch", return_value="[fetch_url] HTTP 200\nok"):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                    with redirect_stdout(buf_fail):
                        rc_fail = main(
                            [
                                "tools",
                                "--config",
                                str(cfg),
                                "web-fetch",
                                "--url",
                                "https://example.com",
                                "--json",
                            ],
                        )
            self.assertEqual(rc_fail, 2)
            p_fail = json.loads(buf_fail.getvalue().strip())
            self.assertEqual(p_fail.get("error"), "web_provider_disabled")

    def test_tools_guard_and_web_fetch_cost_guard(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = root / "cai-agent.toml"
            cfg.write_text(
                '[llm]\nprovider = "openai_compatible"\nbase_url = "http://127.0.0.1:9/v1"\n'
                'model = "m"\napi_key = "k"\n\n[agent]\nmock = true\n'
                '[fetch_url]\nenabled = true\nunrestricted = true\n'
                '[cost]\nbudget_max_tokens = 100\n'
                '[permissions]\nfetch_url = "allow"\n',
                encoding="utf-8",
            )
            buf_guard = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf_guard):
                    rc_guard = main(["tools", "--config", str(cfg), "guard", "--json"])
            self.assertEqual(rc_guard, 0)
            p_guard = json.loads(buf_guard.getvalue().strip())
            self.assertEqual(p_guard.get("schema_version"), "tool_gateway_guard_v1")
            self.assertIs((p_guard.get("cost_guard") or {}).get("enabled"), True)
            pol = p_guard.get("policy") or {}
            self.assertFalse(pol.get("unrestricted_mode"))
            self.assertTrue(pol.get("dangerous_confirmation_required"))
            self.assertFalse(pol.get("dangerous_audit_log_enabled"))
            self.assertEqual(int(pol.get("dangerous_write_file_critical_basenames_count") or 0), 0)
            self.assertEqual(int(pol.get("run_command_extra_danger_basenames_count") or 0), 0)
            dg = p_guard.get("danger_gateway_contract_v1") or {}
            self.assertEqual(dg.get("schema_version"), "danger_gateway_goal_prefix_contract_v1")
            self.assertIn("[danger-approve]", dg.get("tokens_effective") or [])

            buf_cost = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf_cost):
                    rc_cost = main(
                        [
                            "tools",
                            "--config",
                            str(cfg),
                            "web-fetch",
                            "--url",
                            "https://example.com",
                            "--estimated-tokens",
                            "200",
                            "--json",
                        ],
                    )
            self.assertEqual(rc_cost, 2)
            p_cost = json.loads(buf_cost.getvalue().strip())
            self.assertEqual(p_cost.get("error"), "cost_guard_exceeded")


if __name__ == "__main__":
    unittest.main()
