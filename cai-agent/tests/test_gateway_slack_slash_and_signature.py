"""Slack 签名、Slash 与 Interactivity 响应（无 HTTP 服务）。"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from pathlib import Path
from unittest.mock import patch

from cai_agent.gateway_slack import (
    _build_slack_http_response,
    build_slack_slash_command_http_response,
    slack_interactivity_http_response,
    verify_slack_request_signature,
)


def test_verify_slack_request_signature_accepts_valid_hmac() -> None:
    secret = "shh_test_secret"
    ts = str(int(time.time()))
    body = b"foo=bar&baz=1"
    base = f"v0:{ts}:".encode("utf-8") + body
    sig = "v0=" + hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()
    assert verify_slack_request_signature(secret, ts, body, sig) is True


def test_verify_slack_request_signature_rejects_bad_sig() -> None:
    secret = "shh_test_secret"
    ts = str(int(time.time()))
    body = b"x=1"
    assert verify_slack_request_signature(secret, ts, body, "v0=deadbeef") is False


def test_slash_cai_help_returns_blocks(tmp_path: Path) -> None:
    resp, meta = build_slack_slash_command_http_response(
        root=tmp_path,
        command="/cai",
        text="help",
        channel_id="C1",
        user_id="U1",
        bot_token="x",
        execute_on_slash=False,
        reply_on_execution=False,
    )
    assert resp["response_type"] == "ephemeral"
    assert "blocks" in resp
    assert any(b.get("type") == "header" for b in resp["blocks"])
    assert not meta.get("blocked")


def test_slash_not_allowed_channel(tmp_path: Path) -> None:
    from cai_agent.gateway_slack import slack_allow_add

    slack_allow_add(tmp_path, "C_OTHER")
    resp, meta = build_slack_slash_command_http_response(
        root=tmp_path,
        command="/cai",
        text="ping",
        channel_id="C1",
        user_id="U1",
        bot_token="x",
        execute_on_slash=False,
        reply_on_execution=False,
    )
    assert "白名单" in resp.get("text", "")
    assert meta.get("blocked") is True


def test_slash_cai_goal_executes_when_flag_on(tmp_path: Path) -> None:
    with patch(
        "cai_agent.gateway_slack.slack_try_execute_channel_text",
        return_value={"executed": True, "answer_preview": "DONE"},
    ) as ex:
        resp, meta = build_slack_slash_command_http_response(
            root=tmp_path,
            command="/cai",
            text="hello goal",
            channel_id="C1",
            user_id="U1",
            bot_token="x",
            execute_on_slash=True,
            reply_on_execution=False,
        )
    ex.assert_called_once()
    assert "DONE" in resp.get("text", "")
    assert meta.get("executed") is True


def test_interactivity_block_actions() -> None:
    payload = {
        "type": "block_actions",
        "actions": [{"action_id": "btn_ok", "type": "button"}],
    }
    r = slack_interactivity_http_response(payload)
    assert r["response_type"] == "ephemeral"
    assert "block_actions" in json.dumps(r, ensure_ascii=False)


def test_http_form_slash_dispatch_returns_pong(tmp_path: Path) -> None:
    status, payload = _build_slack_http_response(
        root=tmp_path,
        body_bytes=b"command=%2Fcai&text=ping&channel_id=C1&user_id=U1",
        content_type="application/x-www-form-urlencoded; charset=utf-8",
        bot_token="x",
        execute_on_slash=False,
        reply_on_execution=False,
    )
    assert status == 200
    assert payload["response_type"] == "ephemeral"
    assert payload["text"] == "pong"


def test_http_form_interactivity_dispatch_returns_ephemeral_ack(tmp_path: Path) -> None:
    raw = json.dumps({"type": "block_actions", "actions": [{"action_id": "ok"}]}, ensure_ascii=False)
    body = f"payload={raw}".encode("utf-8")
    status, payload = _build_slack_http_response(
        root=tmp_path,
        body_bytes=body,
        content_type="application/x-www-form-urlencoded",
        bot_token="x",
        execute_on_slash=False,
        reply_on_execution=False,
    )
    assert status == 200
    assert payload["response_type"] == "ephemeral"
    assert "block_actions" in json.dumps(payload, ensure_ascii=False)
