from __future__ import annotations

import json
from pathlib import Path

from cai_agent.context_compaction import (
    build_llm_compaction_prompt,
    compact_messages,
    evaluate_compaction_quality,
    evaluate_compaction_retention,
)
from cai_agent.llm import estimate_tokens_from_messages


_SCHEMAS = Path(__file__).resolve().parents[1] / "src" / "cai_agent" / "schemas"


def _load_schema(name: str) -> dict[str, object]:
    return json.loads((_SCHEMAS / name).read_text(encoding="utf-8"))


def _summary_payload(result_content: str) -> dict[str, object]:
    _, raw = result_content.split("\n", 1)
    return json.loads(raw)


def _assert_required(schema: dict[str, object], payload: dict[str, object]) -> None:
    for key in schema.get("required", []):
        assert key in payload


def test_compact_messages_preserves_system_goal_and_tail() -> None:
    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "original goal"},
        {"role": "assistant", "content": '{"type":"tool","name":"read_file","args":{"path":"a.py"}}' + (" plan " * 400)},
        {
            "role": "user",
            "content": json.dumps(
                    {"tool": "read_file", "result": "a.py\n" + ("alpha beta " * 1200)},
                ensure_ascii=False,
            ),
        },
        {"role": "assistant", "content": '{"type":"tool","name":"search_text","args":{"query":"alpha"}}' + (" search " * 400)},
        {
            "role": "user",
            "content": json.dumps(
                    {"tool": "search_text", "result": "src/pkg/a.py:1: alpha\n" + ("gamma " * 1200)},
                ensure_ascii=False,
            ),
        },
        {"role": "assistant", "content": '{"type":"finish","message":"latest answer"}'},
        {"role": "user", "content": "latest follow up"},
    ]

    result = compact_messages(messages, keep_tail_messages=2, summary_max_chars=2500)

    assert result.compacted is True
    assert result.messages[0]["role"] == "system"
    assert result.messages[1]["content"] == "original goal"
    assert result.messages[-1]["content"] == "latest follow up"
    assert result.compacted_message_count < result.original_message_count
    assert result.compacted_estimated_tokens < result.original_estimated_tokens

    summary = result.summary_message or {}
    content = str(summary.get("content") or "")
    assert "[context_summary_v1]" in content
    assert "context_compaction_summary_v1" in content
    assert "read_file" in content
    assert "src/pkg/a.py" in content


def test_compact_messages_noops_when_history_too_short() -> None:
    messages = [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "u"},
        {"role": "assistant", "content": "a"},
    ]

    result = compact_messages(messages)

    assert result.compacted is False
    assert result.messages == messages
    assert result.original_estimated_tokens == estimate_tokens_from_messages(messages)


def test_compact_messages_accepts_llm_summary_payload() -> None:
    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "original goal"},
        {"role": "assistant", "content": "older " * 1000},
        {"role": "user", "content": "middle " * 1000},
        {"role": "assistant", "content": "recent assistant"},
        {"role": "user", "content": "recent user"},
    ]
    payload = {
        "goal": "original goal",
        "decisions": ["use context compaction"],
        "facts": ["older history was summarized"],
        "files_touched": ["cai-agent/src/cai_agent/context_compaction.py"],
        "tool_evidence": [],
        "open_todos": ["continue implementation"],
        "risks": [],
        "last_user_intent": "recent user",
    }

    result = compact_messages(
        messages,
        keep_tail_messages=2,
        summary_payload=payload,
        summary_source="llm",
    )

    assert result.compacted is True
    content = str((result.summary_message or {}).get("content") or "")
    assert '"summary_source": "llm"' in content
    assert "use context compaction" in content
    assert result.compacted_estimated_tokens < result.original_estimated_tokens


def test_build_llm_compaction_prompt_is_bounded() -> None:
    prompt = build_llm_compaction_prompt(
        [
            {"role": "system", "content": "s"},
            {"role": "user", "content": "x" * 10000},
            {"role": "assistant", "content": "y" * 10000},
        ],
        max_source_chars=2500,
    )

    assert len(prompt) == 2
    assert "Return only one JSON object" in prompt[0]["content"]
    assert len(prompt[1]["content"]) < 5000


def test_evaluate_compaction_quality_passes_when_evidence_retained() -> None:
    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "goal marker-alpha"},
        {"role": "assistant", "content": "older " * 1200},
        {
            "role": "user",
            "content": json.dumps(
                {"tool": "read_file", "result": "cai-agent/src/cai_agent/context_compaction.py\n" + ("body " * 1200)},
                ensure_ascii=False,
            ),
        },
        {"role": "assistant", "content": "recent assistant"},
        {"role": "user", "content": "recent user marker-omega"},
    ]

    payload = evaluate_compaction_quality(
        messages,
        keep_tail_messages=2,
        required_markers=("marker-alpha", "marker-omega"),
    ).payload

    assert payload["schema_version"] == "context_compaction_eval_v1"
    assert payload["passed"] is True
    assert payload["checks"]["token_reduction"] is True
    assert payload["retention"]["tools"][0]["tool"] == "read_file"


def test_evaluate_compaction_quality_fails_missing_marker() -> None:
    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "goal marker-alpha"},
        {"role": "assistant", "content": "older " * 1200},
        {"role": "user", "content": "middle " * 1200},
        {"role": "assistant", "content": "recent assistant"},
        {"role": "user", "content": "recent user marker-omega"},
    ]

    payload = evaluate_compaction_quality(
        messages,
        keep_tail_messages=2,
        required_markers=("missing-marker",),
    ).payload

    assert payload["passed"] is False
    assert payload["checks"]["markers_retained"] is False


def test_context_compaction_summary_v1_schema_matches_heuristic_fixture() -> None:
    schema = _load_schema("context_compaction_summary_v1.schema.json")
    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "goal marker-alpha"},
        {"role": "assistant", "content": "older " * 1200},
        {
            "role": "user",
            "content": json.dumps(
                {"tool": "read_file", "result": "cai-agent/src/cai_agent/context_compaction.py\n" + ("body " * 1200)},
                ensure_ascii=False,
            ),
        },
        {"role": "assistant", "content": "recent assistant"},
        {"role": "user", "content": "recent user"},
    ]

    comp = compact_messages(messages, keep_tail_messages=2, summary_max_chars=3000)
    payload = _summary_payload(str((comp.summary_message or {}).get("content") or ""))

    assert schema["properties"]["schema_version"]["const"] == "context_compaction_summary_v1"
    _assert_required(schema, payload)
    assert payload["schema_version"] == "context_compaction_summary_v1"
    assert payload["summary_source"] == "heuristic"
    assert isinstance(payload["role_counts"], dict)
    assert payload["tool_calls"][0]["tool"] == "read_file"
    assert "cai-agent/src/cai_agent/context_compaction.py" in payload["important_paths"]


def test_context_compaction_summary_v1_schema_matches_llm_fixture() -> None:
    schema = _load_schema("context_compaction_summary_v1.schema.json")
    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "original goal"},
        {"role": "assistant", "content": "older " * 1000},
        {"role": "user", "content": "middle " * 1000},
        {"role": "assistant", "content": "recent assistant"},
        {"role": "user", "content": "recent user"},
    ]
    comp = compact_messages(
        messages,
        keep_tail_messages=2,
        summary_payload={
            "goal": "original goal",
            "decisions": ["use llm summary"],
            "facts": ["semantic payload survives"],
            "files_touched": ["cai-agent/src/cai_agent/graph.py"],
            "tool_evidence": [],
            "open_todos": ["verify"],
            "risks": [],
            "last_user_intent": "recent user",
        },
        summary_source="llm",
    )
    payload = _summary_payload(str((comp.summary_message or {}).get("content") or ""))

    _assert_required(schema, payload)
    assert payload["schema_version"] == "context_compaction_summary_v1"
    assert payload["summary_source"] == "llm"
    assert payload["goal"] == "original goal"
    assert payload["files_touched"] == ["cai-agent/src/cai_agent/graph.py"]


def test_context_compaction_retention_v1_schema_matches_fixture() -> None:
    schema = _load_schema("context_compaction_retention_v1.schema.json")
    source = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "goal marker-alpha"},
        {
            "role": "user",
            "content": json.dumps(
                {"tool": "read_file", "result": "cai-agent/src/cai_agent/graph.py\nmarker-middle"},
                ensure_ascii=False,
            ),
        },
        {"role": "assistant", "content": "recent assistant marker-tail"},
        {"role": "user", "content": "recent user marker-omega"},
    ]
    comp = compact_messages(source, keep_tail_messages=2, summary_max_chars=2400)
    payload = evaluate_compaction_retention(
        source,
        comp.messages,
        keep_tail_messages=2,
        required_markers=("marker-alpha", "marker-tail", "marker-omega"),
    ).payload

    assert schema["properties"]["schema_version"]["const"] == "context_compaction_retention_v1"
    _assert_required(schema, payload)
    assert payload["passed"] is True
    assert payload["checks"]["tools_retained"] is True
    assert payload["retention"]["tools"][0]["tool"] == "read_file"


def test_context_compaction_eval_v1_schema_matches_fixture() -> None:
    schema = _load_schema("context_compaction_eval_v1.schema.json")
    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "goal marker-alpha"},
        {"role": "assistant", "content": "older " * 1200},
        {
            "role": "user",
            "content": json.dumps(
                {"tool": "read_file", "result": "cai-agent/src/cai_agent/context_compaction.py\n" + ("body " * 1200)},
                ensure_ascii=False,
            ),
        },
        {"role": "assistant", "content": "recent assistant"},
        {"role": "user", "content": "recent user marker-omega"},
    ]
    payload = evaluate_compaction_quality(
        messages,
        keep_tail_messages=2,
        required_markers=("marker-alpha", "marker-omega"),
    ).payload

    assert schema["properties"]["schema_version"]["const"] == "context_compaction_eval_v1"
    _assert_required(schema, payload)
    assert payload["schema_version"] == "context_compaction_eval_v1"
    assert payload["checks"]["compacted"] is True
    assert payload["message_counts"]["compacted"] < payload["message_counts"]["original"]
    assert payload["estimated_tokens"]["reduction_ratio"] > 0


def test_compact_messages_merges_existing_context_summary_on_second_generation() -> None:
    first_messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "original goal marker-alpha"},
        {"role": "assistant", "content": "older research " * 1200},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "tool": "read_file",
                    "result": "cai-agent/src/cai_agent/context_compaction.py\n" + ("alpha " * 1200),
                },
                ensure_ascii=False,
            ),
        },
        {"role": "assistant", "content": "recent first assistant"},
        {"role": "user", "content": "recent first user"},
    ]
    first = compact_messages(first_messages, keep_tail_messages=2, summary_max_chars=2800)
    first_payload = _summary_payload(str((first.summary_message or {}).get("content") or ""))
    assert "cai-agent/src/cai_agent/context_compaction.py" in first_payload["important_paths"]
    assert first_payload["tool_calls"][0]["tool"] == "read_file"

    second_messages = first.messages + [
        {"role": "assistant", "content": "second wave implementation " * 1200},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "tool": "search_text",
                    "result": "cai-agent/src/cai_agent/graph.py:10: compact\n" + ("beta " * 1200),
                },
                ensure_ascii=False,
            ),
        },
        {"role": "assistant", "content": "latest second assistant"},
        {"role": "user", "content": "latest second user marker-omega"},
    ]

    second = compact_messages(second_messages, keep_tail_messages=2, summary_max_chars=3600)
    content = "\n".join(str(m.get("content") or "") for m in second.messages)
    second_payload = _summary_payload(str((second.summary_message or {}).get("content") or ""))

    assert second.compacted is True
    assert second.compacted_estimated_tokens < second.original_estimated_tokens
    assert content.count("[context_summary_v1]") == 1
    assert "original goal marker-alpha" in content
    assert "latest second user marker-omega" in content
    assert "cai-agent/src/cai_agent/context_compaction.py" in second_payload["important_paths"]
    assert "cai-agent/src/cai_agent/graph.py" in second_payload["important_paths"]
    tools = {row["tool"] for row in second_payload["tool_calls"]}
    assert {"read_file", "search_text"}.issubset(tools)
    assert second_payload["merged_summary_count"] == 1
    assert second_payload["merged_source_message_count"] == first_payload["source_message_count"]


def test_compact_messages_extracts_tool_type_evidence() -> None:
    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "inspect tool outputs"},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "tool": "run_command",
                    "result": (
                        "FAILED cai-agent/tests/test_context_compaction.py::test_x\n"
                        "E AssertionError: expected compact summary\n"
                        "1 failed, 2 passed in 0.12s"
                    ),
                },
                ensure_ascii=False,
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "tool": "python",
                    "result": (
                        "Traceback (most recent call last):\n"
                        "  File \"cai-agent/src/cai_agent/context_compaction.py\", line 10, in <module>\n"
                        "ValueError: boom"
                    ),
                },
                ensure_ascii=False,
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "tool": "git_diff",
                    "result": (
                        "diff --git a/cai-agent/src/cai_agent/graph.py b/cai-agent/src/cai_agent/graph.py\n"
                        "@@ -1,2 +1,3 @@\n"
                        "-old\n"
                        "+new\n"
                        "+extra\n"
                    ),
                },
                ensure_ascii=False,
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "tool": "search_text",
                    "result": (
                        "cai-agent/src/cai_agent/context_compaction.py:10:def compact_messages\n"
                        "cai-agent/src/cai_agent/graph.py:20:compact"
                    ),
                },
                ensure_ascii=False,
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "tool": "read_file",
                    "result": "cai-agent/src/cai_agent/tui.py\nclass App:\n    pass\n",
                },
                ensure_ascii=False,
            ),
        },
        {"role": "assistant", "content": "latest assistant"},
        {"role": "user", "content": "latest user"},
    ]

    comp = compact_messages(messages, keep_tail_messages=2, summary_max_chars=5000)
    payload = _summary_payload(str((comp.summary_message or {}).get("content") or ""))
    rows = {row["tool"]: row for row in payload["tool_calls"]}

    assert rows["run_command"]["tool_kind"] == "test"
    assert "failure_summary" in rows["run_command"]
    assert rows["python"]["tool_kind"] == "traceback"
    assert rows["git_diff"]["tool_kind"] == "git_diff"
    assert rows["git_diff"]["diff_stats"] == {"added_lines": 2, "removed_lines": 1}
    assert rows["search_text"]["tool_kind"] == "search"
    assert "cai-agent/src/cai_agent/graph.py" in rows["search_text"]["paths"]
    assert rows["read_file"]["tool_kind"] == "read"
    assert rows["read_file"]["evidence"][0] == "cai-agent/src/cai_agent/tui.py"


def test_evaluate_compaction_retention_fails_missing_marker_path_tool_and_tail() -> None:
    source = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "goal marker-alpha"},
        {
            "role": "user",
            "content": json.dumps(
                {"tool": "read_file", "result": "cai-agent/src/cai_agent/graph.py\nmarker-middle"},
                ensure_ascii=False,
            ),
        },
        {"role": "assistant", "content": "recent assistant marker-tail"},
        {"role": "user", "content": "recent user marker-omega"},
    ]
    candidate = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "goal marker-alpha"},
        {
            "role": "user",
            "content": '[context_summary_v1]\n{"facts":["summary without evidence"]}',
        },
        {"role": "assistant", "content": "recent assistant"},
        {"role": "user", "content": "recent user"},
    ]

    result = evaluate_compaction_retention(
        source,
        candidate,
        keep_tail_messages=2,
        required_markers=("marker-middle", "marker-tail", "marker-omega"),
    ).payload

    assert result["passed"] is False
    assert result["checks"]["paths_retained"] is False
    assert result["checks"]["tools_retained"] is False
    assert result["checks"]["tail_retained"] is False
    assert result["checks"]["markers_retained"] is False
    assert "paths_retained" in result["failed_reasons"]
