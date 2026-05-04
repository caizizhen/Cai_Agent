from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from cai_agent.config import Settings
from cai_agent.context import augment_system_prompt
from cai_agent.memory import build_structured_memory_prompt_block


def _valid_row(**overrides: object) -> dict:
    row = {
        "id": "inj-1",
        "category": "prefs",
        "text": "User prefers pytest for this repo.",
        "confidence": 0.9,
        "expires_at": None,
        "created_at": datetime.now(UTC).isoformat(),
    }
    row.update(overrides)
    return row


class MemoryPromptInjectTests(unittest.TestCase):
    def test_build_block_includes_active_entries(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mem = root / "memory"
            mem.mkdir(parents=True, exist_ok=True)
            (mem / "entries.jsonl").write_text(
                json.dumps(_valid_row(), ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            blk = build_structured_memory_prompt_block(root, max_entries=10, max_chars=8000)
            self.assertIn("结构化记忆", blk)
            self.assertIn("prefs", blk)
            self.assertIn("pytest", blk)

    def test_augment_system_prompt_injects_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mem = root / "memory"
            mem.mkdir(parents=True, exist_ok=True)
            (mem / "entries.jsonl").write_text(
                json.dumps(_valid_row(), ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            base = Settings.from_env(workspace_hint=str(root))
            s = replace(base, workspace=str(root), memory_inject_enabled=True)
            out = augment_system_prompt(s, "CORE")
            self.assertIn("CORE", out)
            self.assertIn("结构化记忆", out)
            self.assertIn("pytest", out)

    def test_augment_system_prompt_skips_when_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mem = root / "memory"
            mem.mkdir(parents=True, exist_ok=True)
            (mem / "entries.jsonl").write_text(
                json.dumps(_valid_row(), ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            base = Settings.from_env(workspace_hint=str(root))
            s = replace(base, workspace=str(root), memory_inject_enabled=False)
            out = augment_system_prompt(s, "CORE")
            self.assertIn("CORE", out)
            self.assertNotIn("结构化记忆", out)


if __name__ == "__main__":
    unittest.main()
