"""glob_search / search_text use root_dir glob and Windows drive-root normalization."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from cai_agent.sandbox import SandboxError, resolve_tool_path
from cai_agent.tools import tool_glob_search, tool_search_text


class ToolGlobSearchTests(unittest.TestCase):
    def test_glob_search_finds_under_relative_root(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            sub = ws / "nest"
            sub.mkdir()
            (sub / "hit.txt").write_text("ok", encoding="utf-8")
            out = tool_glob_search(str(ws), {"pattern": "**/*.txt", "root": "nest"})
            self.assertIn("hit.txt", out)
            self.assertTrue(out.startswith("共 "), out)


class ToolSearchTextRootDirTests(unittest.TestCase):
    def test_search_text_scans_under_relative_root(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            sub = ws / "src"
            sub.mkdir()
            (sub / "a.py").write_text("needle_here\n", encoding="utf-8")
            out = tool_search_text(str(ws), {"query": "needle_here", "root": "src", "glob": "*.py"})
            self.assertIn("needle_here", out)


@unittest.skipUnless(os.name == "nt", "Windows drive-letter semantics")
class WindowsBareDriveLetterTests(unittest.TestCase):
    def test_bare_drive_maps_to_volume_root_when_unrestricted(self) -> None:
        td = Path(tempfile.mkdtemp()).resolve()
        nested = td / "nested_cwd_probe"
        nested.mkdir(parents=True, exist_ok=True)
        ws = td / "ws"
        ws.mkdir()
        letter = td.drive  # "C:", etc.
        old = os.getcwd()
        try:
            os.chdir(nested)
            got = resolve_tool_path(str(ws), letter, unrestricted=True)
            expect = Path(f"{letter}\\").resolve()
            self.assertEqual(got, expect)
        finally:
            try:
                os.chdir(old)
            except OSError:
                pass
            shutil.rmtree(td, ignore_errors=True)

    def test_bare_drive_rejected_when_restricted(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td) / "w"
            ws.mkdir()
            letter = ws.resolve().drive
            with self.assertRaises(SandboxError):
                resolve_tool_path(str(ws), letter, unrestricted=False)

