from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"


def _cli(*args: str, cwd: Path | None = None, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_SRC)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "cai_agent", *args],
        cwd=str(cwd or Path.cwd()),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_voice_config_json_schema(tmp_path: Path) -> None:
    p = _cli("voice", "config", "--json", cwd=tmp_path)
    assert p.returncode == 0, p.stderr
    o = json.loads((p.stdout or "").strip())
    assert o.get("schema_version") == "voice_provider_contract_v1"
    assert "stt" in o and "tts" in o and "health" in o


def test_voice_check_json_exit_2_when_not_configured(tmp_path: Path) -> None:
    p = _cli("voice", "check", "--json", cwd=tmp_path)
    assert p.returncode == 2, p.stderr
    o = json.loads((p.stdout or "").strip())
    assert o.get("schema_version") == "voice_check_v1"
    assert o.get("ok") is False


def test_voice_check_json_exit_0_when_configured(tmp_path: Path) -> None:
    p = _cli(
        "voice",
        "check",
        "--json",
        cwd=tmp_path,
        env_extra={
            "CAI_VOICE_PROVIDER": "mock-voice",
            "CAI_VOICE_ENDPOINT": "http://127.0.0.1:9999",
            "CAI_VOICE_API_KEY": "k",
            "CAI_VOICE_STT_MODEL": "stt-mini",
            "CAI_VOICE_TTS_MODEL": "tts-mini",
        },
    )
    assert p.returncode == 0, p.stderr
    o = json.loads((p.stdout or "").strip())
    assert o.get("ok") is True
    assert (o.get("voice") or {}).get("schema_version") == "voice_provider_contract_v1"
