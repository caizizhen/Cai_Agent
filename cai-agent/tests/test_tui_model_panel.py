"""tui_model_panel 纯函数与 profile 解析辅助。"""

from __future__ import annotations

from cai_agent.profiles import Profile
from cai_agent.tui_model_panel import _next_active_id, _profile_row


def test_profile_row_shows_active_marker() -> None:
    p = Profile(
        id="local",
        provider="openai_compatible",
        base_url="http://localhost:1234/v1",
        model="m1",
        notes="home",
    )
    row = _profile_row(p, active_id="local")
    assert "[active]" in row
    assert "local" in row
    assert "m1" in row
    assert "openai_compatible" in row


def test_next_active_id_prefer_and_fallback() -> None:
    a = Profile(
        id="a",
        provider="openai",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
    )
    b = Profile(
        id="b",
        provider="openai_compatible",
        base_url="http://x/v1",
        model="m",
    )
    assert _next_active_id("a", (a, b), prefer="b") == "b"
    assert _next_active_id("a", (a, b), prefer=None) == "a"
    assert _next_active_id("x", (a, b), prefer=None) == "a"
