"""Tool JSON normalization for LangGraph executor."""

from __future__ import annotations

import unittest

from cai_agent.graph import merge_tool_call_args


class MergeToolCallArgsTests(unittest.TestCase):
    def test_flat_path_merged_for_list_dir(self) -> None:
        obj = {"type": "tool", "name": "list_dir", "path": "E:\\"}
        self.assertEqual(merge_tool_call_args(obj), {"path": "E:\\"})

    def test_nested_args_used_when_present(self) -> None:
        obj = {
            "type": "tool",
            "name": "list_dir",
            "args": {"path": "."},
            "path": "E:\\",
        }
        self.assertEqual(merge_tool_call_args(obj)["path"], ".")

    def test_top_level_fills_missing_keys_only(self) -> None:
        obj = {"type": "tool", "name": "read_file", "args": {"path": "a.py"}, "line_start": 1}
        self.assertEqual(
            merge_tool_call_args(obj),
            {"path": "a.py", "line_start": 1},
        )

    def test_empty_args_and_flat_content(self) -> None:
        obj = {
            "type": "tool",
            "name": "write_file",
            "path": "out.txt",
            "content": "hi",
        }
        self.assertEqual(
            merge_tool_call_args(obj),
            {"path": "out.txt", "content": "hi"},
        )

