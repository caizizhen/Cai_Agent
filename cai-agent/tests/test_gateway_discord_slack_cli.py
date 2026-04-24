"""Tests for §24: Discord + Slack Gateway MVP."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"


def _cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_SRC)
    return subprocess.run(
        [sys.executable, "-m", "cai_agent", *args],
        cwd=str(cwd or Path.cwd()),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

from cai_agent.gateway_discord import (
    discord_allow_add,
    discord_allow_list,
    discord_allow_rm,
    discord_bind,
    discord_get_binding,
    discord_list_bindings,
    discord_unbind,
)
from cai_agent.gateway_slack import (
    slack_allow_add,
    slack_allow_list,
    slack_allow_rm,
    slack_bind,
    slack_get_binding,
    slack_list_bindings,
    slack_unbind,
)


# ---------------------------------------------------------------------------
# Discord 会话映射
# ---------------------------------------------------------------------------


def test_discord_bind_and_get(tmp_path: Path) -> None:
    r = discord_bind(tmp_path, "123456789", "session.json")
    assert r["ok"] is True
    r2 = discord_get_binding(tmp_path, "123456789")
    assert r2["found"] is True
    assert r2["binding"]["session_file"] == "session.json"


def test_discord_unbind(tmp_path: Path) -> None:
    discord_bind(tmp_path, "111", "s.json")
    r = discord_unbind(tmp_path, "111")
    assert r["was_bound"] is True
    r2 = discord_get_binding(tmp_path, "111")
    assert r2["found"] is False


def test_discord_list_bindings(tmp_path: Path) -> None:
    discord_bind(tmp_path, "aaa", "a.json")
    discord_bind(tmp_path, "bbb", "b.json")
    r = discord_list_bindings(tmp_path)
    assert "aaa" in r["bindings"]
    assert "bbb" in r["bindings"]


def test_discord_allow_add_rm_list(tmp_path: Path) -> None:
    discord_allow_add(tmp_path, "ch1")
    discord_allow_add(tmp_path, "ch2")
    r = discord_allow_list(tmp_path)
    assert "ch1" in r["allowed_channel_ids"]
    assert r["allowlist_enabled"] is True
    discord_allow_rm(tmp_path, "ch1")
    r2 = discord_allow_list(tmp_path)
    assert "ch1" not in r2["allowed_channel_ids"]
    assert "ch2" in r2["allowed_channel_ids"]


def test_discord_map_file_schema(tmp_path: Path) -> None:
    discord_bind(tmp_path, "c1", "f.json")
    map_file = tmp_path / ".cai" / "gateway" / "discord-session-map.json"
    assert map_file.is_file()
    data = json.loads(map_file.read_text(encoding="utf-8"))
    assert data["schema_version"] == "gateway_discord_map_v1"


# ---------------------------------------------------------------------------
# Slack 会话映射
# ---------------------------------------------------------------------------


def test_slack_bind_and_get(tmp_path: Path) -> None:
    r = slack_bind(tmp_path, "C123", "sess.json")
    assert r["ok"] is True
    r2 = slack_get_binding(tmp_path, "C123")
    assert r2["found"] is True


def test_slack_unbind(tmp_path: Path) -> None:
    slack_bind(tmp_path, "C001", "s.json")
    r = slack_unbind(tmp_path, "C001")
    assert r["was_bound"] is True
    r2 = slack_get_binding(tmp_path, "C001")
    assert r2["found"] is False


def test_slack_list_bindings(tmp_path: Path) -> None:
    slack_bind(tmp_path, "C001", "a.json")
    slack_bind(tmp_path, "C002", "b.json")
    r = slack_list_bindings(tmp_path)
    assert "C001" in r["bindings"]


def test_slack_allow_add_rm_list(tmp_path: Path) -> None:
    slack_allow_add(tmp_path, "C001")
    slack_allow_add(tmp_path, "C002")
    r = slack_allow_list(tmp_path)
    assert "C001" in r["allowed_channel_ids"]
    slack_allow_rm(tmp_path, "C001")
    r2 = slack_allow_list(tmp_path)
    assert "C001" not in r2["allowed_channel_ids"]


def test_slack_map_file_schema(tmp_path: Path) -> None:
    slack_bind(tmp_path, "C999", "x.json")
    map_file = tmp_path / ".cai" / "gateway" / "slack-session-map.json"
    assert map_file.is_file()
    data = json.loads(map_file.read_text(encoding="utf-8"))
    assert data["schema_version"] == "gateway_slack_map_v1"


# ---------------------------------------------------------------------------
# CLI 集成测试：gateway discord
# ---------------------------------------------------------------------------


def test_gateway_discord_bind_cli(tmp_path: Path) -> None:
    result = _cli("gateway", "discord", "-w", str(tmp_path), "bind", "CHANNEL_001", "session.json", "--json")
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["ok"] is True


def test_gateway_discord_list_cli(tmp_path: Path) -> None:
    discord_bind(tmp_path, "CH1", "s1.json")
    result = _cli("gateway", "discord", "-w", str(tmp_path), "list", "--json")
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert "CH1" in out["bindings"]


def test_gateway_discord_allow_add_cli(tmp_path: Path) -> None:
    result = _cli("gateway", "discord", "-w", str(tmp_path), "allow", "add", "CH_ALLOW", "--json")
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["ok"] is True
    assert "CH_ALLOW" in out["allowed_channel_ids"]


def test_gateway_discord_health_cli_no_token(tmp_path: Path) -> None:
    result = _cli("gateway", "discord", "-w", str(tmp_path), "health", "--json")
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out.get("schema_version") == "gateway_discord_health_v1"
    assert out.get("bindings_count") == 0
    tc = out.get("token_check") or {}
    assert tc.get("performed") is False


def test_gateway_discord_register_commands_no_token_exit_2(tmp_path: Path) -> None:
    result = _cli(
        "gateway",
        "discord",
        "-w",
        str(tmp_path),
        "register-commands",
        "--dry-run",
        "--json",
    )
    assert result.returncode == 2, result.stderr


def test_gateway_discord_list_commands_no_token_exit_2(tmp_path: Path) -> None:
    result = _cli("gateway", "discord", "-w", str(tmp_path), "list-commands", "--json")
    assert result.returncode == 2, result.stderr


# ---------------------------------------------------------------------------
# CLI 集成测试：gateway slack
# ---------------------------------------------------------------------------


def test_gateway_slack_bind_cli(tmp_path: Path) -> None:
    result = _cli("gateway", "slack", "-w", str(tmp_path), "bind", "C_SLACK", "session.json", "--json")
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["ok"] is True


def test_gateway_slack_list_cli(tmp_path: Path) -> None:
    slack_bind(tmp_path, "C_X", "sx.json")
    result = _cli("gateway", "slack", "-w", str(tmp_path), "list", "--json")
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert "C_X" in out["bindings"]


def test_gateway_slack_allow_add_cli(tmp_path: Path) -> None:
    result = _cli("gateway", "slack", "-w", str(tmp_path), "allow", "add", "C_ALLOW", "--json")
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["ok"] is True


# ---------------------------------------------------------------------------
# gateway platforms 目录验证（Discord/Slack 升级为 mvp）
# ---------------------------------------------------------------------------


def test_gateway_platforms_shows_discord_slack_mvp() -> None:
    from cai_agent.gateway_platforms import build_gateway_platforms_payload

    p = build_gateway_platforms_payload()
    plat_map = {pl["id"]: pl for pl in p["platforms"]}
    assert plat_map["discord"]["implementation"] == "mvp"
    assert plat_map["slack"]["implementation"] == "mvp"
    assert plat_map["telegram"]["implementation"] == "full"
