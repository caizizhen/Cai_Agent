"""Tests for ``cai_agent.tui_path_complete`` (slash path completion)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cai_agent.tui_path_complete import (
    safe_descendant,
    split_dir_fragment,
    suggest_path_after_command,
)


class SplitDirFragmentTests(unittest.TestCase):
    def test_empty(self) -> None:
        self.assertEqual(split_dir_fragment(""), ("", ""))

    def test_single_segment(self) -> None:
        self.assertEqual(split_dir_fragment("foo"), ("", "foo"))

    def test_nested(self) -> None:
        self.assertEqual(split_dir_fragment("a/b/c"), ("a/b", "c"))

    def test_trailing_slash(self) -> None:
        self.assertEqual(split_dir_fragment("a/b/"), ("a/b", ""))

    def test_backslash_norm(self) -> None:
        self.assertEqual(split_dir_fragment(r"a\b\c"), ("a/b", "c"))


class SafeDescendantTests(unittest.TestCase):
    def test_escape_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "r"
            root.mkdir()
            self.assertIsNone(safe_descendant(root, "../.."))


class SuggestPathTests(unittest.TestCase):
    def test_relative_file_completion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "alpha.json").write_text("{}", encoding="utf-8")
            (root / "beta.txt").write_text("x", encoding="utf-8")
            hit = suggest_path_after_command(
                cmd_prefix="/load ",
                line_value="/load al",
                roots=(root,),
                filter_json_files_only=True,
            )
            self.assertEqual(hit, "/load alpha.json")

    def test_save_allows_non_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "note.txt").write_text("x", encoding="utf-8")
            hit = suggest_path_after_command(
                cmd_prefix="/save ",
                line_value="/save no",
                roots=(root,),
                filter_json_files_only=False,
            )
            self.assertEqual(hit, "/save note.txt")

    def test_load_skips_non_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "only.txt").write_text("x", encoding="utf-8")
            hit = suggest_path_after_command(
                cmd_prefix="/load ",
                line_value="/load on",
                roots=(root,),
                filter_json_files_only=True,
            )
            self.assertIsNone(hit)

    def test_subdirectory_trailing_slash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sub = root / "docs"
            sub.mkdir()
            (sub / "x.json").write_text("{}", encoding="utf-8")
            hit = suggest_path_after_command(
                cmd_prefix="/load ",
                line_value="/load docs/",
                roots=(root,),
                filter_json_files_only=True,
            )
            self.assertEqual(hit, "/load docs/x.json")
