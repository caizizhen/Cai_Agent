from __future__ import annotations

import asyncio

from starlette.testclient import TestClient

from cai_agent.pi_core.messages import AgentMessage
from cai_agent.surfaces.web import SessionHub, build_app


def test_feedback_branch_stats(tmp_path, monkeypatch):
    monkeypatch.setenv("CAI_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CAI_WORKSPACE", str(tmp_path / "ws"))
    (tmp_path / "ws").mkdir()
    hub = SessionHub()
    client = TestClient(build_app(hub))
    sid = client.post("/api/session/new").json()["session_id"]
    hub.store.append(sid, AgentMessage(role="user", content="hello"))
    hub.store.append(
        sid,
        AgentMessage(
            role="assistant",
            content="world",
            meta={"usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}},
        ),
    )
    rows = hub.store.load_rows(sid)
    aseq = next(r["seq"] for r in rows if r["role"] == "assistant")

    fb = client.post(f"/api/session/{sid}/feedback", json={"seq": aseq, "vote": "up"})
    assert fb.status_code == 200
    assert fb.json()["feedback"] == "up"

    stats = client.get(f"/api/session/{sid}/stats").json()
    assert stats["total_tokens"] >= 15
    assert stats["messages"] == 2
    assert "rounds" in stats
    assert "tps" in stats
    assert "cache_hit_pct" in stats
    hub.store.add_run_metrics(sid, {"rounds": 1, "steps": 3, "model_ms": 1200, "tool_ms": 300, "ttft_sum_ms": 400, "ttft_count": 1})
    hub.store.add_usage(sid, {"cache_read_tokens": 80, "prompt_tokens": 20, "completion_tokens": 5, "total_tokens": 25})
    stats2 = client.get(f"/api/session/{sid}/stats").json()
    assert stats2["rounds"] >= 1
    assert stats2["steps"] >= 3
    assert stats2["cache_read_tokens"] >= 80
    html = client.get("/").text
    assert "pill-session" in html
    assert "pill-token" in html
    assert "note-modal" in html
    assert "confirm-modal" in html

    br = client.post(f"/api/session/{sid}/branch", json={"upto_seq": aseq})
    assert br.status_code == 200
    new_id = br.json()["session_id"]
    assert new_id != sid
    tr = client.get(f"/api/session/{new_id}/transcript").json()
    assert len(tr["messages"]) == 2

    html = client.get("/").text
    assert "session-stats" in html
    assert "composer-model-btn" in html
    assert "btn-plus" in html
    assert 'id="approve"' in html


def test_image_chat_and_convert(tmp_path, monkeypatch):
    monkeypatch.setenv("CAI_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CAI_WORKSPACE", str(tmp_path / "ws"))
    (tmp_path / "ws").mkdir()
    hub = SessionHub()
    client = TestClient(build_app(hub))
    sid = client.post("/api/session/new").json()["session_id"]
    # 1x1 PNG
    png_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    ref = hub.store.save_image_b64(sid, data_b64=png_b64, mime="image/png", name="dot.png")
    assert ref["file"].endswith(".png")
    att = client.get(f"/api/session/{sid}/attachment/{ref['file']}")
    assert att.status_code == 200

    from cai_agent.pi_core.messages import AgentMessage, convert_to_llm

    msg = AgentMessage(
        role="user",
        content="what is this?",
        meta={"images": [{"mime": "image/png", "data": png_b64}]},
    )
    llm_msgs = convert_to_llm([msg])
    assert isinstance(llm_msgs[0]["content"], list)
    assert llm_msgs[0]["content"][1]["type"] == "image_url"

    from cai_agent.llm.anthropic_messages import openai_messages_to_anthropic

    _, amsgs = openai_messages_to_anthropic(llm_msgs)
    assert amsgs[0]["content"][1]["type"] == "image"


def test_approval_deny_blocks_write(tmp_path, monkeypatch):
    monkeypatch.setenv("CAI_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CAI_WORKSPACE", str(tmp_path / "ws"))
    (tmp_path / "ws").mkdir()
    hub = SessionHub()
    client = TestClient(build_app(hub))
    client.put("/api/runtime", json={"approval": "deny"})
    sid = client.post("/api/session/new").json()["session_id"]
    handle = hub.get_or_create(sid)

    out = asyncio.run(
        handle.session.agent.tools.execute("write", {"path": "x.txt", "content": "a"}, tool_call_id="t1"),
    )
    assert "denied" in out
    assert not (tmp_path / "ws" / "x.txt").exists()

    (tmp_path / "ws" / "ok.txt").write_text("hi", encoding="utf-8")
    text = asyncio.run(
        handle.session.agent.tools.execute("read", {"path": "ok.txt"}, tool_call_id="t2"),
    )
    assert "hi" in text
