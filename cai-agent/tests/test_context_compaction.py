from __future__ import annotations

import json

from cai_agent.context_compaction import (
    build_llm_compaction_prompt,
    compact_messages,
    evaluate_compaction_quality,
)
from cai_agent.llm import estimate_tokens_from_messages


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
