from __future__ import annotations

import io
import json
import shutil
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cai_agent.__main__ import main


class BrowserProviderCliTests(unittest.TestCase):
    def _workspace(self) -> Path:
        root = Path.cwd() / ".tmp" / f"browser-provider-{uuid.uuid4().hex}"
        root.mkdir(parents=True, exist_ok=False)
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        return root

    def _config(self, root: Path) -> Path:
        cfg = root / "cai-agent.toml"
        cfg.write_text(
            '[llm]\nprovider = "openai_compatible"\nbase_url = "http://127.0.0.1:9/v1"\n'
            'model = "m"\napi_key = "k"\n\n[agent]\nmock = true\n'
            'mcp_enabled = true\n\n[mcp]\nbase_url = "http://127.0.0.1:8787"\n',
            encoding="utf-8",
        )
        return cfg.resolve()

    def test_tools_browser_check_json_ready(self) -> None:
        root = self._workspace()
        cfg = self._config(root)
        buf = io.StringIO()
        tools = "browser_navigate\tNavigate\nbrowser_click\tClick\nbrowser_snapshot\tSnapshot\n"
        with patch("cai_agent.tool_provider.dispatch", return_value=tools):
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "tools",
                            "--config",
                            str(cfg),
                            "browser-check",
                            "--max-steps",
                            "12",
                            "--allow-host",
                            "example.com",
                            "--json",
                        ],
                    )

        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue().strip())
        self.assertEqual(payload.get("schema_version"), "browser_provider_check_v1")
        self.assertIs(payload.get("ok"), True)
        self.assertEqual(payload.get("provider"), "mcp_bridge")
        session = payload.get("session") or {}
        self.assertEqual(session.get("max_steps"), 12)
        self.assertEqual(session.get("allow_hosts"), ["example.com"])
        self.assertIs(session.get("isolated"), True)
        self.assertIn("screenshots_dir", payload.get("artifacts") or {})
        self.assertEqual(payload.get("permissions"), {"key": "mcp_call_tool", "mode": "ask"})

    def test_browser_check_rejects_invalid_allow_host(self) -> None:
        root = self._workspace()
        cfg = self._config(root)
        buf = io.StringIO()
        with patch("cai_agent.tool_provider.dispatch", return_value="browser_navigate\tNavigate\n"):
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "browser",
                            "--config",
                            str(cfg),
                            "check",
                            "--allow-host",
                            "https://example.com/path",
                            "--json",
                        ],
                    )

        self.assertEqual(rc, 2)
        payload = json.loads(buf.getvalue().strip())
        self.assertEqual(payload.get("error"), "invalid_allow_host")
        self.assertIn("invalid_allow_host", payload.get("errors") or [])

    def test_browser_task_json_uses_stable_contract(self) -> None:
        root = self._workspace()
        cfg = self._config(root)
        buf = io.StringIO()
        with patch("cai_agent.tool_provider.dispatch", return_value="browser_navigate\tNavigate\nbrowser_click\tClick\n"):
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "browser",
                            "--config",
                            str(cfg),
                            "task",
                            "open dashboard and summarize",
                            "--url",
                            "https://example.com",
                            "--json",
                        ],
                    )

        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue().strip())
        self.assertEqual(payload.get("schema_version"), "browser_task_v1")
        self.assertIs(payload.get("ok"), True)
        self.assertEqual(payload.get("provider"), "mcp_bridge")
        self.assertEqual(payload.get("url"), "https://example.com")
        self.assertIs(payload.get("dry_run"), True)
        self.assertTrue((payload.get("execution") or {}).get("implemented"))
        self.assertTrue((payload.get("execution") or {}).get("dry_run"))
        calls = (payload.get("execution") or {}).get("calls") or []
        self.assertEqual(calls[0].get("tool"), "browser_navigate")
        self.assertGreaterEqual(len(payload.get("steps") or []), 2)
        self.assertIn("session", payload)
        self.assertIn("artifacts", payload)

    def test_browser_task_execute_requires_explicit_confirm(self) -> None:
        root = self._workspace()
        cfg = self._config(root)
        buf = io.StringIO()
        with patch("cai_agent.tool_provider.dispatch", return_value="browser_navigate\tNavigate\nbrowser_snapshot\tSnapshot\n"):
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "browser",
                            "--config",
                            str(cfg),
                            "task",
                            "open dashboard",
                            "--url",
                            "https://example.com",
                            "--execute",
                            "--json",
                        ],
                    )

        self.assertEqual(rc, 2)
        payload = json.loads(buf.getvalue().strip())
        execution = payload.get("execution") or {}
        self.assertEqual(execution.get("schema_version"), "browser_mcp_execution_v1")
        self.assertEqual(execution.get("error"), "explicit_confirmation_required")
        self.assertTrue(all(c.get("status") == "refused" for c in execution.get("calls") or []))
        audit_file = Path(str((execution.get("audit") or {}).get("audit_file")))
        self.assertTrue(audit_file.is_file())
        event = json.loads(audit_file.read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual(event.get("schema_version"), "browser_audit_event_v1")
        self.assertFalse(event.get("confirmed"))
        manifest_file = Path(str((execution.get("artifact_manifest") or {}).get("manifest_file")))
        self.assertTrue(manifest_file.is_file())

    def test_browser_task_execute_confirm_maps_to_mcp_calls(self) -> None:
        root = self._workspace()
        cfg = self._config(root)
        screenshots = root / ".cai" / "browser" / "screenshots"
        screenshots.mkdir(parents=True)
        (screenshots / "before.png").write_bytes(b"png")
        buf = io.StringIO()
        listed = "browser_navigate\tNavigate\nbrowser_snapshot\tSnapshot\n"

        def fake_dispatch(_settings, name, args):
            if name == "mcp_list_tools":
                return listed
            if name == "mcp_call_tool":
                return json.dumps({"ok": True, "tool": args.get("name")})
            return ""

        with patch("cai_agent.tool_provider.dispatch", side_effect=fake_dispatch):
            with patch("cai_agent.browser_provider.dispatch", side_effect=fake_dispatch):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                    with redirect_stdout(buf):
                        rc = main(
                            [
                                "browser",
                                "--config",
                                str(cfg),
                                "task",
                                "open dashboard",
                                "--url",
                                "https://example.com",
                                "--execute",
                                "--confirm",
                                "--json",
                            ],
                        )

        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue().strip())
        execution = payload.get("execution") or {}
        self.assertFalse(execution.get("dry_run"))
        self.assertTrue(execution.get("confirmed"))
        calls = execution.get("calls") or []
        self.assertEqual([c.get("tool") for c in calls], ["browser_navigate", "browser_snapshot"])
        self.assertTrue(all(c.get("status") == "executed" for c in calls))
        audit_file = Path(str((execution.get("audit") or {}).get("audit_file")))
        self.assertTrue(audit_file.is_file())
        event = json.loads(audit_file.read_text(encoding="utf-8").splitlines()[-1])
        self.assertTrue(event.get("ok"))
        self.assertTrue(event.get("confirmed"))
        manifest = execution.get("artifact_manifest") or {}
        self.assertEqual(manifest.get("schema_version"), "browser_artifact_manifest_v1")
        self.assertEqual(manifest.get("files_count"), 1)
        self.assertEqual((manifest.get("files") or [])[0].get("relative_path"), "screenshots/before.png")


if __name__ == "__main__":
    unittest.main()
