"""Unit tests for TUI slash-command completion (Suggester)."""

from __future__ import annotations

import asyncio
import unittest

from cai_agent.tui import (
    CompactStatusSnapshot,
    SlashCommandSuggester,
    SlashCompletionContext,
    _SLASH_COMMAND_CANDIDATES,
    _cai_brand_markup,
    _compact_quality_score,
    _format_compact_status,
    _parse_mcp_tool_lines,
    _slash_menu_matches,
    _slash_menu_rows,
    _slash_typo_hint,
)


def _suggest(s: SlashCommandSuggester, value: str) -> str | None:
    return asyncio.run(s.get_suggestion(value))


class SlashCommandSuggesterTests(unittest.TestCase):
    def test_no_slash_prefix(self) -> None:
        s = SlashCommandSuggester()
        self.assertIsNone(_suggest(s, "hello"))
        self.assertIsNone(_suggest(s, ""))

    def test_slash_only(self) -> None:
        s = SlashCommandSuggester()
        self.assertEqual(_suggest(s, "/"), "/?")

    def test_help_prefix(self) -> None:
        s = SlashCommandSuggester()
        self.assertEqual(_suggest(s, "/h"), "/help")
        self.assertIsNone(_suggest(s, "/help"))

    def test_models_before_mcp(self) -> None:
        s = SlashCommandSuggester()
        self.assertEqual(_suggest(s, "/m"), "/models")

    def test_models_trailing_space_suggests_refresh(self) -> None:
        s = SlashCommandSuggester()
        self.assertEqual(_suggest(s, "/models "), "/models refresh")

    def test_mcp_subcommands(self) -> None:
        s = SlashCommandSuggester()
        self.assertEqual(_suggest(s, "/mcp"), "/mcp refresh")
        self.assertEqual(_suggest(s, "/mcp "), "/mcp call ")
        self.assertEqual(_suggest(s, "/mcp r"), "/mcp refresh")
        self.assertEqual(_suggest(s, "/mcp c"), "/mcp call ")

    def test_fix_build_and_security_scan_completion(self) -> None:
        s = SlashCommandSuggester()
        self.assertEqual(_suggest(s, "/f"), "/fix-build")
        self.assertEqual(_suggest(s, "/se"), "/sessions")
        self.assertIsNone(_suggest(s, "/fix-build"))
        self.assertIsNone(_suggest(s, "/security-scan"))

    def test_unrestricted_and_danger_approve_completion(self) -> None:
        s = SlashCommandSuggester()
        self.assertEqual(_suggest(s, "/un"), "/undo")
        self.assertEqual(_suggest(s, "/unr"), "/unrestricted")
        self.assertEqual(_suggest(s, "/d"), "/danger-approve")
        self.assertIsNone(_suggest(s, "/danger-approve"))

    def test_load_latest_in_list(self) -> None:
        s = SlashCommandSuggester()
        self.assertEqual(_suggest(s, "/load"), "/load ")
        self.assertEqual(_suggest(s, "/load "), "/load latest")

    def test_candidates_tuple_is_sorted_for_docs(self) -> None:
        self.assertGreater(len(_SLASH_COMMAND_CANDIDATES), 5)


class CaiBrandMarkupTests(unittest.TestCase):
    def test_brand_contains_wordmark(self) -> None:
        s = _cai_brand_markup()
        self.assertIn("Cai", s)
        self.assertIn("$primary", s)


class CompactStatusFormatTests(unittest.TestCase):
    def test_no_compact_run(self) -> None:
        self.assertEqual(_format_compact_status(None), "compact: no run yet")

    def test_compact_snapshot_line(self) -> None:
        line = _format_compact_status(
            CompactStatusSnapshot(
                mode="llm",
                summary_source="heuristic",
                original_message_count=12,
                compacted_message_count=5,
                original_estimated_tokens=1000,
                compacted_estimated_tokens=250,
                fallback_reason="llm_compaction_quality_failed: paths_retained",
                quality_score=0.875,
            ),
        )
        self.assertIn("mode=llm", line)
        self.assertIn("source=heuristic", line)
        self.assertIn("messages=12->5", line)
        self.assertIn("tokens=1000->250", line)
        self.assertIn("ratio=75.0%", line)
        self.assertIn("fallback=llm_compaction_quality_failed", line)
        self.assertIn("quality=0.88", line)

    def test_quality_score_from_retention_payload(self) -> None:
        score = _compact_quality_score(
            {
                "checks": {
                    "initial_goal_retained": True,
                    "tail_retained": True,
                    "paths_retained": False,
                },
                "retention": {
                    "tail_retention_ratio": 1.0,
                    "path_retention_ratio": 0.5,
                    "tool_retention_ratio": 1.0,
                    "marker_retention_ratio": 1.0,
                },
            },
        )
        self.assertIsNotNone(score)
        self.assertGreater(score or 0.0, 0.0)
        self.assertLess(score or 1.0, 1.0)


class SlashTypoHintTests(unittest.TestCase):
    def test_typo_models(self) -> None:
        h = _slash_typo_hint("/model")
        self.assertIsNotNone(h)
        self.assertIn("/models", h or "")

    def test_exact_known_no_hint(self) -> None:
        self.assertIsNone(_slash_typo_hint("/help"))
        self.assertIsNone(_slash_typo_hint("/models"))

    def test_load_with_path_no_hint(self) -> None:
        self.assertIsNone(_slash_typo_hint("/load foo.json"))


class ParseMcpToolLinesTests(unittest.TestCase):
    def test_tab_separated(self) -> None:
        txt = "alpha\tDesc A\nbeta\tDesc B\n"
        self.assertEqual(_parse_mcp_tool_lines(txt), ["alpha", "beta"])

    def test_skips_failures_and_empty(self) -> None:
        txt = "\n[mcp_list_tools 失败] x\n(无 MCP 工具)\n"
        self.assertEqual(_parse_mcp_tool_lines(txt), [])


class DynamicSlashCompletionTests(unittest.TestCase):
    def test_registered_command_names(self) -> None:
        ctx = SlashCompletionContext()
        ctx.command_names = ("plan", "verify")
        s = SlashCommandSuggester(context=ctx)
        self.assertEqual(_suggest(s, "/p"), "/plan")
        self.assertEqual(_suggest(s, "/v"), "/verify")
        self.assertIsNone(_suggest(s, "/plan"))

    def test_slash_menu_includes_registered_and_static_commands(self) -> None:
        ctx = SlashCompletionContext()
        ctx.command_names = ("code-review", "plan", "verify")
        hits = _slash_menu_matches("/", context=ctx)
        self.assertIn("/plan", hits)
        self.assertIn("/code-review", hits)
        self.assertIn("/verify", hits)
        self.assertIn("/help", hits)
        self.assertIn("/status", hits)

    def test_slash_menu_filters_prefix_with_dynamic_priority(self) -> None:
        ctx = SlashCompletionContext()
        ctx.command_names = ("plan",)
        self.assertEqual(_slash_menu_matches("/p", context=ctx)[0], "/plan")

    def test_slash_menu_rows_include_descriptions(self) -> None:
        ctx = SlashCompletionContext()
        ctx.command_names = ("code-review",)
        rows = _slash_menu_rows("/c", context=ctx)
        self.assertEqual(rows[0].value, "/code-review")
        self.assertEqual(rows[0].source, "template")
        self.assertIn("commands/code-review.md", rows[0].description)

    def test_use_model_profiles(self) -> None:
        ctx = SlashCompletionContext()
        ctx.profile_ids = ("local", "remote")
        s = SlashCommandSuggester(context=ctx)
        self.assertEqual(_suggest(s, "/use-model "), "/use-model local")
        self.assertEqual(_suggest(s, "/use-model r"), "/use-model remote")
        self.assertIsNone(_suggest(s, "/use-model remote"))

    def test_mcp_call_tools(self) -> None:
        ctx = SlashCompletionContext()
        ctx.mcp_tool_names = ("ping", "pong")
        s = SlashCommandSuggester(context=ctx)
        self.assertEqual(_suggest(s, "/mcp call "), "/mcp call ping {}")
        self.assertEqual(_suggest(s, "/mcp call p"), "/mcp call ping {}")
        self.assertEqual(_suggest(s, "/mcp call po"), "/mcp call pong {}")
        self.assertEqual(_suggest(s, "/mcp call ping"), "/mcp call ping {}")
        self.assertIsNone(_suggest(s, "/mcp call ping {"))

    def test_dynamic_before_static_use_model_space(self) -> None:
        """/use-model + space 应由 profile 补全，而不是停在静态 ``/use-model ``。"""
        ctx = SlashCompletionContext()
        ctx.profile_ids = ("p1",)
        s = SlashCommandSuggester(context=ctx)
        self.assertEqual(_suggest(s, "/use-model "), "/use-model p1")


class DynamicLoadSaveCompletionTests(unittest.TestCase):
    def test_load_latest_priority(self) -> None:
        ctx = SlashCompletionContext()
        ctx.session_paths = (".cai-session-a.json",)
        s = SlashCommandSuggester(context=ctx)
        self.assertEqual(_suggest(s, "/load "), "/load latest")
        self.assertEqual(_suggest(s, "/load l"), "/load latest")

    def test_load_session_file(self) -> None:
        ctx = SlashCompletionContext()
        ctx.session_paths = (".cai-session-a.json", ".cai-session-b.json")
        s = SlashCommandSuggester(context=ctx)
        self.assertEqual(_suggest(s, "/load .cai-session-a"), "/load .cai-session-a.json")
        self.assertEqual(_suggest(s, "/load .cai-session-b"), "/load .cai-session-b.json")

    def test_load_skips_subpath(self) -> None:
        ctx = SlashCompletionContext()
        ctx.session_paths = ("x.json",)
        s = SlashCommandSuggester(context=ctx)
        self.assertIsNone(_suggest(s, "/load sub/x.json"))

    def test_save_session_file(self) -> None:
        ctx = SlashCompletionContext()
        ctx.session_paths = ("out.json",)
        s = SlashCommandSuggester(context=ctx)
        self.assertEqual(_suggest(s, "/save o"), "/save out.json")
