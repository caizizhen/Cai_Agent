from __future__ import annotations

import unittest
from pathlib import Path

from cai_agent.tools import DISPATCH_TOOL_NAMES
from cai_agent.tools_registry_doc import BUILTIN_TOOLS_DOC_ROWS, render_tools_registry_markdown_zh_cn


class ToolsRegistryDocSyncTests(unittest.TestCase):
    def test_dispatch_matches_registry_rows(self) -> None:
        reg = {r.name for r in BUILTIN_TOOLS_DOC_ROWS}
        self.assertEqual(
            reg,
            DISPATCH_TOOL_NAMES,
            msg="Update BUILTIN_TOOLS_DOC_ROWS and/or DISPATCH_TOOL_NAMES together",
        )

    def test_repo_doc_matches_generated(self) -> None:
        root = Path(__file__).resolve().parents[2]
        path = root / "docs" / "TOOLS_REGISTRY.zh-CN.md"
        self.assertTrue(path.is_file(), msg=f"expected {path}")
        on_disk = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        self.assertEqual(
            on_disk,
            render_tools_registry_markdown_zh_cn(),
            msg="Run: python scripts/gen_tools_registry_zh.py",
        )


if __name__ == "__main__":
    unittest.main()
