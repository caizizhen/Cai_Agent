from __future__ import annotations

import json
import tempfile
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

from cai_agent.config import Settings
from cai_agent.runtime.registry import get_runtime_backend
from cai_agent.runtime.ssh import SSHRuntime


def test_ssh_exec_builds_known_hosts_key_timeout_and_audit(tmp_path: Path) -> None:
    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text("host key\n", encoding="utf-8")
    key = tmp_path / "id_ed25519"
    key.write_text("key\n", encoding="utf-8")
    audit = tmp_path / "audit.jsonl"
    rt = SSHRuntime(
        host="example.com",
        user="deploy",
        key_path=str(key),
        strict_host_key=True,
        known_hosts_path=str(known_hosts),
        connect_timeout_sec=7.0,
        audit_log_path=str(audit),
        audit_label="ci",
    )
    mock_run = MagicMock(return_value=MagicMock(stdout="ok", stderr="", returncode=0))
    with patch("cai_agent.runtime.ssh.shutil.which", return_value="ssh"):
        with patch("cai_agent.runtime.ssh.subprocess.run", mock_run):
            result = rt.exec(["echo", "hi"], cwd="/workspace", timeout_sec=9.0)
    assert result.returncode == 0
    argv = mock_run.call_args[0][0]
    assert argv[:2] == ["ssh", "-o"]
    assert "BatchMode=yes" in argv
    assert "ConnectTimeout=7" in argv
    assert f"UserKnownHostsFile={known_hosts}" in argv
    assert "StrictHostKeyChecking=yes" in argv
    assert "-i" in argv and str(key) in argv
    assert "deploy@example.com" in argv
    event = json.loads(audit.read_text(encoding="utf-8").splitlines()[0])
    assert event["schema_version"] == "runtime_ssh_audit_v1"
    assert event["label"] == "ci"
    assert event["returncode"] == 0
    assert "command_preview" not in event


def test_ssh_describe_reports_diagnostic_fields(tmp_path: Path) -> None:
    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text("host key\n", encoding="utf-8")
    rt = SSHRuntime(
        host="example.com",
        user="deploy",
        strict_host_key=True,
        known_hosts_path=str(known_hosts),
        audit_log_path=str(tmp_path / "audit.jsonl"),
        audit_label="ops",
    )
    with patch("cai_agent.runtime.ssh.shutil.which", return_value="ssh"):
        d = rt.describe()
    assert d["ssh_binary_present"] is True
    assert d["known_hosts_path"] == str(known_hosts)
    assert d["known_hosts_exists"] is True
    assert d["audit_enabled"] is True
    assert d["audit_label"] == "ops"
    assert d["key_path_configured"] is False


def test_runtime_ssh_settings_parse_audit_fields(tmp_path: Path) -> None:
    audit = tmp_path / "ssh-audit.jsonl"
    toml = textwrap.dedent(
        f"""
        [llm]
        base_url = "http://localhost:1/v1"
        model = "m"
        api_key = "k"
        [agent]
        workspace = "{tmp_path.as_posix()}"
        [runtime]
        backend = "ssh"
        [runtime.ssh]
        host = "example.com"
        user = "deploy"
        known_hosts_path = "{(tmp_path / 'known_hosts').as_posix()}"
        connect_timeout_sec = 9
        audit_log_path = "{audit.as_posix()}"
        audit_label = "ci"
        audit_include_command = true
        """,
    )
    with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False, encoding="utf-8") as f:
        f.write(toml)
        cfg = f.name
    try:
        settings = Settings.from_env(config_path=cfg)
        rt = get_runtime_backend("ssh", settings=settings)
        d = rt.describe()
        assert d["host"] == "example.com"
        assert d["user"] == "deploy"
        assert d["connect_timeout_sec"] == 9.0
        assert d["audit_enabled"] is True
        assert d["audit_include_command"] is True
    finally:
        import os

        os.unlink(cfg)
