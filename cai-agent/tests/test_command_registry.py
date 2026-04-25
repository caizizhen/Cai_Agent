from __future__ import annotations

import shutil
import unittest
import uuid
from pathlib import Path

from cai_agent.command_registry import list_command_names, load_command_text
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


if __name__ == "__main__":
    unittest.main()
