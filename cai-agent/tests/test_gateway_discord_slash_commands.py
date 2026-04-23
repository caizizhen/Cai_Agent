"""Discord Application Commands（Slash）注册与列出 — 无网络，mock REST。"""
from __future__ import annotations

from unittest.mock import patch

from cai_agent.gateway_discord import (
    discord_default_slash_command_specs,
    discord_list_application_commands,
    discord_register_application_commands,
    discord_resolve_application,
)


def test_default_slash_specs_match_telegram_surface() -> None:
    names = {c["name"] for c in discord_default_slash_command_specs()}
    assert names == {"ping", "help", "status", "new"}
    for c in discord_default_slash_command_specs():
        assert c.get("type") == 1


def test_resolve_application_error_propagates() -> None:
    err = {"_error": True, "status": 401, "message": "nope"}
    with patch("cai_agent.gateway_discord._discord_exchange", return_value=err):
        r = discord_resolve_application("token")
    assert r["ok"] is False
    assert r["error"] == err


def test_list_commands_success() -> None:
    fake_cmds = [{"id": "1", "name": "ping", "type": 1}]
    with patch(
        "cai_agent.gateway_discord.discord_resolve_application",
        return_value={"ok": True, "application_id": "app9"},
    ), patch(
        "cai_agent.gateway_discord._discord_exchange",
        return_value=fake_cmds,
    ) as ex:
        r = discord_list_application_commands("tok", guild_id="G1")
    assert r["ok"] is True
    assert r["commands"] == fake_cmds
    assert r["guild_id"] == "G1"
    ex.assert_called_once_with("GET", "/applications/app9/guilds/G1/commands", "tok")


def test_register_commands_dry_run_skips_put() -> None:
    with patch(
        "cai_agent.gateway_discord.discord_resolve_application",
        return_value={"ok": True, "application_id": "app9"},
    ), patch("cai_agent.gateway_discord._discord_exchange") as ex:
        r = discord_register_application_commands("tok", guild_id=None, dry_run=True)
    assert r["ok"] is True
    assert r["dry_run"] is True
    assert r["registered"] is False
    assert len(r["commands"]) == 4
    ex.assert_not_called()


def test_register_commands_put_on_success() -> None:
    put_resp = [{"name": "ping", "id": "10", "type": 1}]
    with patch(
        "cai_agent.gateway_discord.discord_resolve_application",
        return_value={"ok": True, "application_id": "app9"},
    ), patch(
        "cai_agent.gateway_discord._discord_exchange",
        return_value=put_resp,
    ) as ex:
        r = discord_register_application_commands("tok", guild_id="G2", dry_run=False)
    assert r["ok"] is True
    assert r["registered"] is True
    assert r["commands"] == put_resp
    specs = discord_default_slash_command_specs()
    ex.assert_called_once_with(
        "PUT",
        "/applications/app9/guilds/G2/commands",
        "tok",
        json_data=specs,
    )


def test_register_commands_put_error() -> None:
    err = {"_error": True, "status": 400, "message": "bad"}
    with patch(
        "cai_agent.gateway_discord.discord_resolve_application",
        return_value={"ok": True, "application_id": "app9"},
    ), patch("cai_agent.gateway_discord._discord_exchange", return_value=err):
        r = discord_register_application_commands("tok", dry_run=False)
    assert r["ok"] is False
    assert r["registered"] is False
