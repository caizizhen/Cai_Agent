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
        self.assertFalse((payload.get("execution") or {}).get("implemented"))
        self.assertGreaterEqual(len(payload.get("steps") or []), 2)
        self.assertIn("session", payload)
        self.assertIn("artifacts", payload)


if __name__ == "__main__":
    unittest.main()
