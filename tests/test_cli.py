from __future__ import annotations

import json

from cai_agent.__main__ import main


def test_dump_config(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("CAI_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CAI_WORKSPACE", str(tmp_path / "ws"))
    (tmp_path / "ws").mkdir()
    assert main(["--dump-config"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["architecture"] == "layered-pi+harness-ui"
    assert data["layers"] == ["ui", "adapter", "engine"]
    assert data["tools"] == ["read", "write", "edit", "bash"]


def test_cli_flags_override_model(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("CAI_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CAI_WORKSPACE", str(tmp_path / "ws"))
    (tmp_path / "ws").mkdir()
    assert main(["--model", "demo-model", "--max-steps", "3", "--dump-config"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["model"] == "demo-model"
    assert data["max_steps"] == 3


def test_run_mock_quiet(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("CAI_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CAI_WORKSPACE", str(tmp_path / "ws"))
    monkeypatch.setenv("CAI_MOCK", "1")
    monkeypatch.setenv("CAI_MOCK_REPLY", "cli-ok")
    (tmp_path / "ws").mkdir()
    assert main(["run", "-q", "hello"]) == 0
    assert "cli-ok" in capsys.readouterr().out


def test_run_json_envelope(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("CAI_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CAI_WORKSPACE", str(tmp_path / "ws"))
    monkeypatch.setenv("CAI_MOCK", "1")
    monkeypatch.setenv("CAI_MOCK_REPLY", "json-ok")
    (tmp_path / "ws").mkdir()
    assert main(["run", "--json", "hello"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["reply"] == "json-ok"
    assert data["architecture"] == "layered-pi+harness-ui"
