from __future__ import annotations

import shutil
import unittest
import uuid
from pathlib import Path

from cai_agent.command_registry import (
    build_command_discovery_payload,
    list_command_names,
    load_command_text,
)
from cai_agent.config import Settings


class CommandRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path.cwd() / ".tmp-tests" / f"command-registry-{uuid.uuid4().hex}"
        root.mkdir(parents=True)
        self.root = root
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        self.cfg = root / "cai-agent.toml"
        self.cfg.write_text(
            '[llm]\nbase_url = "http://localhost/v1"\nmodel = "m"\napi_key = "k"\n',
            encoding="utf-8",
        )
        self.settings = Settings.from_env(config_path=str(self.cfg))

    def test_discovers_commands_under_cursor_dir(self) -> None:
        cmd_dir = self.root / ".cursor" / "commands"
        cmd_dir.mkdir(parents=True)
        (cmd_dir / "code-review.md").write_text("# review\n", encoding="utf-8")
        (cmd_dir / "README.md").write_text("# ignored\n", encoding="utf-8")

        names = list_command_names(self.settings)
        self.assertIn("code-review", names)
        self.assertNotIn("README", names)

    def test_load_prefers_project_commands_over_cursor_commands(self) -> None:
        plain = self.root / "commands"
        cursor = self.root / ".cursor" / "commands"
        plain.mkdir(parents=True)
        cursor.mkdir(parents=True)
        (plain / "verify.md").write_text("from commands", encoding="utf-8")
        (cursor / "verify.md").write_text("from .cursor/commands", encoding="utf-8")

        txt = load_command_text(self.settings, "verify")
        self.assertEqual(txt, "from commands")

    def test_command_discovery_payload_reports_paths_and_unique_names(self) -> None:
        plain = self.root / "commands"
        cursor = self.root / ".cursor" / "commands"
        plain.mkdir(parents=True)
        cursor.mkdir(parents=True)
        (plain / "code-review.md").write_text("# project review\n", encoding="utf-8")
        (plain / "README.md").write_text("# ignored\n", encoding="utf-8")
        (cursor / "code-review.md").write_text("# cursor review\n", encoding="utf-8")
        (cursor / "verify.md").write_text("# verify\n", encoding="utf-8")

        payload = build_command_discovery_payload(self.settings)

        self.assertEqual(payload.get("schema_version"), "command_discovery_v1")
        commands = payload.get("commands")
        self.assertIsInstance(commands, list)
        self.assertIn("code-review", commands)
        self.assertIn("verify", commands)
        self.assertEqual(commands.count("code-review"), 1)
        self.assertEqual(commands.count("verify"), 1)
        self.assertEqual(payload.get("commands_count"), len(commands))
        self.assertTrue(payload.get("ok"))
        self.assertIsNone(payload.get("repair_hint"))
        rows = payload.get("search_paths")
        self.assertIsInstance(rows, list)
        existing = [r for r in rows if isinstance(r, dict) and r.get("exists")]
        self.assertGreaterEqual(len(existing), 2)
        self.assertIn("code-review", existing[0].get("commands") or [])


if __name__ == "__main__":
    unittest.main()
