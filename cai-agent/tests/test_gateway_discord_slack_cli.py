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
from cai_agent.gateway_signal import (
    signal_allow_add,
    signal_allow_list,
    signal_allow_rm,
    signal_bind,
    signal_gateway_health,
    signal_get_binding,
    signal_list_bindings,
    signal_unbind,
)
from cai_agent.gateway_email import (
    email_allow_add,
    email_allow_list,
    email_allow_rm,
    email_bind,
    email_gateway_health,
    email_get_binding,
    email_receive,
    email_send,
    email_unbind,
)
from cai_agent.gateway_matrix import (
    matrix_allow_add,
    matrix_allow_list,
    matrix_allow_rm,
    matrix_bind,
    matrix_gateway_health,
    matrix_get_binding,
    matrix_receive,
    matrix_send,
    matrix_unbind,
)
from cai_agent.gateway_teams import (
    build_teams_manifest_payload,
    teams_activity_response,
    teams_allow_add,
    teams_allow_list,
    teams_allow_rm,
    teams_bind,
    teams_gateway_health,
    teams_get_binding,
    teams_list_bindings,
    teams_unbind,
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
# Signal 会话映射 / skeleton 健康检查
# ---------------------------------------------------------------------------


def test_signal_bind_and_get(tmp_path: Path) -> None:
    r = signal_bind(tmp_path, "+8613000000000", "signal.json", label="ops")
    assert r["ok"] is True
    r2 = signal_get_binding(tmp_path, "+8613000000000")
    assert r2["found"] is True
    assert r2["binding"]["label"] == "ops"


def test_signal_unbind(tmp_path: Path) -> None:
    signal_bind(tmp_path, "u1", "s.json")
    r = signal_unbind(tmp_path, "u1")
    assert r["was_bound"] is True
    assert signal_get_binding(tmp_path, "u1")["found"] is False


def test_signal_allow_add_rm_list(tmp_path: Path) -> None:
    signal_allow_add(tmp_path, "u1")
    signal_allow_add(tmp_path, "u2")
    r = signal_allow_list(tmp_path)
    assert "u1" in r["allowed_sender_ids"]
    assert r["allowlist_enabled"] is True
    signal_allow_rm(tmp_path, "u1")
    r2 = signal_allow_list(tmp_path)
    assert "u1" not in r2["allowed_sender_ids"]


def test_signal_map_file_schema(tmp_path: Path) -> None:
    signal_bind(tmp_path, "u-map", "x.json")
    map_file = tmp_path / ".cai" / "gateway" / "signal-session-map.json"
    assert map_file.is_file()
    data = json.loads(map_file.read_text(encoding="utf-8"))
    assert data["schema_version"] == "gateway_signal_map_v1"


def test_signal_health_config_presence(tmp_path: Path) -> None:
    signal_bind(tmp_path, "u-health", "s.json")
    r = signal_gateway_health(
        tmp_path,
        service_url="http://127.0.0.1:8080",
        account="default",
        phone_number="+8613000000000",
    )
    assert r["schema_version"] == "gateway_signal_health_v1"
    assert r["bindings_count"] == 1
    assert r["service_url_configured"] is True
    assert r["account_configured"] is True
    assert r["phone_number_configured"] is True
    assert (r.get("token_check") or {}).get("performed") is False


# ---------------------------------------------------------------------------
# Email 会话映射 / send-receive 最小链路
# ---------------------------------------------------------------------------


def test_email_bind_and_get(tmp_path: Path) -> None:
    r = email_bind(tmp_path, "ops@example.com", "mail.json", label="ops")
    assert r["ok"] is True
    r2 = email_get_binding(tmp_path, "ops@example.com")
    assert r2["found"] is True
    assert r2["binding"]["label"] == "ops"


def test_email_unbind(tmp_path: Path) -> None:
    email_bind(tmp_path, "a@example.com", "s.json")
    r = email_unbind(tmp_path, "a@example.com")
    assert r["was_bound"] is True
    assert email_get_binding(tmp_path, "a@example.com")["found"] is False


def test_email_allow_add_rm_list(tmp_path: Path) -> None:
    email_allow_add(tmp_path, "sender-a@example.com")
    email_allow_add(tmp_path, "sender-b@example.com")
    r = email_allow_list(tmp_path)
    assert "sender-a@example.com" in r["allowed_senders"]
    assert r["allowlist_enabled"] is True
    email_allow_rm(tmp_path, "sender-a@example.com")
    r2 = email_allow_list(tmp_path)
    assert "sender-a@example.com" not in r2["allowed_senders"]


def test_email_send_receive_chain(tmp_path: Path) -> None:
    email_send(
        tmp_path,
        from_address="sender@example.com",
        to_address="ops@example.com",
        subject="hello",
        text="world",
        mirror_inbox=True,
    )
    out = email_receive(tmp_path, inbox_address="ops@example.com", limit=5)
    assert out["ok"] is True
    assert out["messages_count"] >= 1
    assert (out["messages"] or [{}])[-1].get("subject") == "hello"


def test_email_health_config_presence(tmp_path: Path) -> None:
    email_bind(tmp_path, "ops@example.com", "mail.json")
    r = email_gateway_health(
        tmp_path,
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="ops",
        imap_host="imap.example.com",
        imap_port=993,
        imap_user="ops",
    )
    assert r["schema_version"] == "gateway_email_health_v1"
    assert r["bindings_count"] == 1
    assert (r["smtp"] or {}).get("host_configured") is True
    assert (r["imap"] or {}).get("host_configured") is True


# ---------------------------------------------------------------------------
# Matrix room map / send-receive 最小链路
# ---------------------------------------------------------------------------


def test_matrix_bind_and_get(tmp_path: Path) -> None:
    r = matrix_bind(tmp_path, "!room:example.org", "matrix.json", label="ops")
    assert r["ok"] is True
    r2 = matrix_get_binding(tmp_path, "!room:example.org")
    assert r2["found"] is True
    assert r2["binding"]["label"] == "ops"


def test_matrix_unbind(tmp_path: Path) -> None:
    matrix_bind(tmp_path, "!room:a", "s.json")
    r = matrix_unbind(tmp_path, "!room:a")
    assert r["was_bound"] is True
    assert matrix_get_binding(tmp_path, "!room:a")["found"] is False


def test_matrix_allow_add_rm_list(tmp_path: Path) -> None:
    matrix_allow_add(tmp_path, "!room:a")
    matrix_allow_add(tmp_path, "!room:b")
    r = matrix_allow_list(tmp_path)
    assert "!room:a" in r["allowed_room_ids"]
    assert r["allowlist_enabled"] is True
    matrix_allow_rm(tmp_path, "!room:a")
    r2 = matrix_allow_list(tmp_path)
    assert "!room:a" not in r2["allowed_room_ids"]


def test_matrix_send_receive_chain(tmp_path: Path) -> None:
    matrix_send(
        tmp_path,
        room_id="!room:ops",
        sender="@bot:example.org",
        text="hello",
        mirror_inbound=True,
    )
    out = matrix_receive(tmp_path, room_id="!room:ops", limit=5)
    assert out["ok"] is True
    assert out["messages_count"] >= 1
    assert (out["messages"] or [{}])[-1].get("text") == "hello"


def test_matrix_health_config_presence(tmp_path: Path) -> None:
    matrix_bind(tmp_path, "!room:ops", "matrix.json")
    r = matrix_gateway_health(
        tmp_path,
        homeserver="https://matrix.example.org",
        access_token="token-x",
        user_id="@ops:example.org",
    )
    assert r["schema_version"] == "gateway_matrix_health_v1"
    assert r["bindings_count"] == 1
    assert r["homeserver_configured"] is True
    assert r["access_token_configured"] is True
    assert r["user_id_configured"] is True


# ---------------------------------------------------------------------------
# Teams 会话映射 / Activity 响应
# ---------------------------------------------------------------------------


def test_teams_bind_and_get(tmp_path: Path) -> None:
    r = teams_bind(
        tmp_path,
        "conv-1",
        "session.json",
        tenant_id="tenant-1",
        service_url="https://smba.trafficmanager.net/amer/",
        channel_id="msteams",
        label="ops",
    )
    assert r["ok"] is True
    r2 = teams_get_binding(tmp_path, "conv-1")
    assert r2["found"] is True
    assert r2["binding"]["tenant_id"] == "tenant-1"
    assert r2["binding"]["label"] == "ops"


def test_teams_unbind(tmp_path: Path) -> None:
    teams_bind(tmp_path, "conv-1", "session.json")
    r = teams_unbind(tmp_path, "conv-1")
    assert r["was_bound"] is True
    assert teams_get_binding(tmp_path, "conv-1")["found"] is False


def test_teams_allow_add_rm_list(tmp_path: Path) -> None:
    teams_allow_add(tmp_path, "conv-1")
    teams_allow_add(tmp_path, "conv-2")
    r = teams_allow_list(tmp_path)
    assert "conv-1" in r["allowed_conversation_ids"]
    assert r["allowlist_enabled"] is True
    teams_allow_rm(tmp_path, "conv-1")
    r2 = teams_allow_list(tmp_path)
    assert "conv-1" not in r2["allowed_conversation_ids"]
    assert "conv-2" in r2["allowed_conversation_ids"]


def test_teams_map_file_schema(tmp_path: Path) -> None:
    teams_bind(tmp_path, "conv-9", "x.json")
    map_file = tmp_path / ".cai" / "gateway" / "teams-session-map.json"
    assert map_file.is_file()
    data = json.loads(map_file.read_text(encoding="utf-8"))
    assert data["schema_version"] == "gateway_teams_map_v1"


def test_teams_health_no_secret(tmp_path: Path) -> None:
    teams_bind(tmp_path, "conv-1", "s.json")
    r = teams_gateway_health(tmp_path)
    assert r["schema_version"] == "gateway_teams_health_v1"
    assert r["bindings_count"] == 1
    assert r["app_id_configured"] is False
    assert r["token_check"]["performed"] is False


def test_teams_manifest_payload() -> None:
    r = build_teams_manifest_payload(
        app_id="app-123",
        bot_id="bot-456",
        name="CAI Agent",
        valid_domains=["example.com"],
    )
    assert r["schema_version"] == "gateway_teams_manifest_v1"
    manifest = r["manifest"]
    assert manifest["id"] == "app-123"
    assert manifest["bots"][0]["botId"] == "bot-456"
    assert manifest["validDomains"] == ["example.com"]


def test_teams_activity_response_ping(tmp_path: Path) -> None:
    teams_bind(tmp_path, "conv-1", "s.json")
    status, resp, meta = teams_activity_response(
        root=tmp_path,
        activity={
            "type": "message",
            "text": "ping",
            "conversation": {"id": "conv-1"},
            "from": {"id": "user-1"},
            "channelData": {"tenant": {"id": "tenant-1"}},
        },
    )
    assert status == 200
    assert resp["text"] == "pong"
    assert meta["command"] == "ping"


def test_teams_activity_response_allowlist_blocks(tmp_path: Path) -> None:
    teams_allow_add(tmp_path, "allowed")
    status, resp, meta = teams_activity_response(
        root=tmp_path,
        activity={"type": "message", "text": "ping", "conversation": {"id": "blocked"}},
    )
    assert status == 200
    assert "白名单" in resp["text"]
    assert meta["blocked"] is True


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
    result = _cli(
        "gateway",
        "slack",
        "-w",
        str(tmp_path),
        "bind",
        "C_SLACK",
        "session.json",
        "--team-id",
        "T_TEAM",
        "--label",
        "ops",
        "--json",
    )
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["ok"] is True
    binding = out.get("binding") or {}
    assert binding.get("team_id") == "T_TEAM"
    assert binding.get("label") == "ops"


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


def test_gateway_slack_health_cli_no_token(tmp_path: Path) -> None:
    result = _cli("gateway", "slack", "-w", str(tmp_path), "health", "--json")
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out.get("schema_version") == "gateway_slack_health_v1"
    assert out.get("bindings_count") == 0
    assert out.get("signing_secret_configured") is False
    tc = out.get("token_check") or {}
    assert tc.get("performed") is False


# ---------------------------------------------------------------------------
# CLI 集成测试：gateway teams
# ---------------------------------------------------------------------------


def test_gateway_teams_bind_cli(tmp_path: Path) -> None:
    result = _cli(
        "gateway",
        "teams",
        "-w",
        str(tmp_path),
        "bind",
        "CONV_TEAMS",
        "session.json",
        "--tenant-id",
        "TENANT",
        "--service-url",
        "https://smba.trafficmanager.net/amer/",
        "--label",
        "ops",
        "--json",
    )
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["ok"] is True
    assert out["binding"]["tenant_id"] == "TENANT"
    assert out["binding"]["label"] == "ops"


def test_gateway_teams_list_cli(tmp_path: Path) -> None:
    teams_bind(tmp_path, "CONV_X", "sx.json")
    result = _cli("gateway", "teams", "-w", str(tmp_path), "list", "--json")
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert "CONV_X" in out["bindings"]


def test_gateway_teams_allow_add_cli(tmp_path: Path) -> None:
    result = _cli("gateway", "teams", "-w", str(tmp_path), "allow", "add", "CONV_ALLOW", "--json")
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["ok"] is True
    assert "CONV_ALLOW" in out["allowed_conversation_ids"]


def test_gateway_teams_health_cli_no_secret(tmp_path: Path) -> None:
    result = _cli("gateway", "teams", "-w", str(tmp_path), "health", "--json")
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out.get("schema_version") == "gateway_teams_health_v1"
    assert out.get("bindings_count") == 0
    assert out.get("webhook_secret_configured") is False
    assert (out.get("token_check") or {}).get("performed") is False


def test_gateway_teams_manifest_cli() -> None:
    result = _cli(
        "gateway",
        "teams",
        "manifest",
        "--app-id",
        "APP",
        "--bot-id",
        "BOT",
        "--valid-domain",
        "example.com",
        "--json",
    )
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["schema_version"] == "gateway_teams_manifest_v1"
    assert out["manifest"]["id"] == "APP"
    assert out["manifest"]["bots"][0]["botId"] == "BOT"


def test_gateway_signal_bind_cli(tmp_path: Path) -> None:
    result = _cli("gateway", "signal", "-w", str(tmp_path), "bind", "SENDER_001", "session.json", "--json")
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["ok"] is True


def test_gateway_signal_list_cli(tmp_path: Path) -> None:
    signal_bind(tmp_path, "SENDER_X", "sx.json")
    result = _cli("gateway", "signal", "-w", str(tmp_path), "list", "--json")
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert "SENDER_X" in out["bindings"]


def test_gateway_signal_allow_add_cli(tmp_path: Path) -> None:
    result = _cli("gateway", "signal", "-w", str(tmp_path), "allow", "add", "SENDER_ALLOW", "--json")
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["ok"] is True
    assert "SENDER_ALLOW" in out["allowed_sender_ids"]


def test_gateway_signal_health_cli_no_config(tmp_path: Path) -> None:
    result = _cli("gateway", "signal", "-w", str(tmp_path), "health", "--json")
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out.get("schema_version") == "gateway_signal_health_v1"
    assert out.get("bindings_count") == 0
    assert out.get("service_url_configured") is False
    assert (out.get("token_check") or {}).get("performed") is False


def test_gateway_email_bind_cli(tmp_path: Path) -> None:
    result = _cli("gateway", "email", "-w", str(tmp_path), "bind", "ops@example.com", "mail.json", "--json")
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["ok"] is True


def test_gateway_email_send_receive_cli(tmp_path: Path) -> None:
    send_r = _cli(
        "gateway",
        "email",
        "-w",
        str(tmp_path),
        "send",
        "--from",
        "sender@example.com",
        "--to",
        "ops@example.com",
        "--subject",
        "hello",
        "--text",
        "world",
        "--mirror-inbox",
        "--json",
    )
    assert send_r.returncode == 0, send_r.stderr
    recv_r = _cli(
        "gateway",
        "email",
        "-w",
        str(tmp_path),
        "receive",
        "--inbox",
        "ops@example.com",
        "--limit",
        "10",
        "--json",
    )
    assert recv_r.returncode == 0, recv_r.stderr
    out = json.loads(recv_r.stdout)
    assert out.get("schema_version") == "gateway_email_messages_v1"
    assert out.get("messages_count", 0) >= 1


def test_gateway_email_health_cli_no_config(tmp_path: Path) -> None:
    result = _cli("gateway", "email", "-w", str(tmp_path), "health", "--json")
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out.get("schema_version") == "gateway_email_health_v1"
    assert (out.get("smtp") or {}).get("host_configured") is False
    assert (out.get("imap") or {}).get("host_configured") is False


def test_gateway_matrix_bind_cli(tmp_path: Path) -> None:
    result = _cli("gateway", "matrix", "-w", str(tmp_path), "bind", "!room:ops", "matrix.json", "--json")
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["ok"] is True


def test_gateway_matrix_send_receive_cli(tmp_path: Path) -> None:
    send_r = _cli(
        "gateway",
        "matrix",
        "-w",
        str(tmp_path),
        "send",
        "--room-id",
        "!room:ops",
        "--sender",
        "@bot:example.org",
        "--text",
        "hello",
        "--mirror-inbound",
        "--json",
    )
    assert send_r.returncode == 0, send_r.stderr
    recv_r = _cli(
        "gateway",
        "matrix",
        "-w",
        str(tmp_path),
        "receive",
        "--room-id",
        "!room:ops",
        "--limit",
        "10",
        "--json",
    )
    assert recv_r.returncode == 0, recv_r.stderr
    out = json.loads(recv_r.stdout)
    assert out.get("schema_version") == "gateway_matrix_messages_v1"
    assert out.get("messages_count", 0) >= 1


def test_gateway_matrix_health_cli_no_config(tmp_path: Path) -> None:
    result = _cli("gateway", "matrix", "-w", str(tmp_path), "health", "--json")
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out.get("schema_version") == "gateway_matrix_health_v1"
    assert out.get("homeserver_configured") is False
    assert out.get("user_id_configured") is False


# ---------------------------------------------------------------------------
# gateway platforms 目录验证（Discord/Slack/Teams 升级为 mvp）
# ---------------------------------------------------------------------------


def test_gateway_platforms_shows_discord_slack_teams_mvp() -> None:
    from cai_agent.gateway_platforms import build_gateway_platforms_payload

    p = build_gateway_platforms_payload()
    plat_map = {pl["id"]: pl for pl in p["platforms"]}
    assert plat_map["discord"]["implementation"] == "mvp"
    assert plat_map["slack"]["implementation"] == "mvp"
    assert plat_map["teams"]["implementation"] == "mvp"
    assert plat_map["signal"]["implementation"] == "mvp"
    assert plat_map["email"]["implementation"] == "mvp"
    assert plat_map["matrix"]["implementation"] == "mvp"
    assert plat_map["telegram"]["implementation"] == "full"
