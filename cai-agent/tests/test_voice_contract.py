from __future__ import annotations

import os

from cai_agent.voice import build_voice_provider_contract_payload


def test_voice_contract_defaults() -> None:
    prev = {k: os.environ.get(k) for k in (
        "CAI_VOICE_PROVIDER",
        "CAI_VOICE_STT_MODEL",
        "CAI_VOICE_TTS_MODEL",
        "CAI_VOICE_ENDPOINT",
        "CAI_VOICE_API_KEY",
    )}
    try:
        for k in prev:
            os.environ.pop(k, None)
        p = build_voice_provider_contract_payload()
        assert p.get("schema_version") == "voice_provider_contract_v1"
        assert p.get("provider") == "none"
        assert (p.get("health") or {}).get("configured") is False
    finally:
        for k, v in prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_voice_contract_configured() -> None:
    prev = {k: os.environ.get(k) for k in (
        "CAI_VOICE_PROVIDER",
        "CAI_VOICE_STT_MODEL",
        "CAI_VOICE_TTS_MODEL",
        "CAI_VOICE_ENDPOINT",
        "CAI_VOICE_API_KEY",
    )}
    try:
        os.environ["CAI_VOICE_PROVIDER"] = "mock-voice"
        os.environ["CAI_VOICE_STT_MODEL"] = "stt-mini"
        os.environ["CAI_VOICE_TTS_MODEL"] = "tts-mini"
        os.environ["CAI_VOICE_ENDPOINT"] = "http://127.0.0.1:9999"
        os.environ["CAI_VOICE_API_KEY"] = "k"
        p = build_voice_provider_contract_payload()
        assert p.get("provider") == "mock-voice"
        assert (p.get("stt") or {}).get("enabled") is True
        assert (p.get("tts") or {}).get("enabled") is True
        assert (p.get("health") or {}).get("configured") is True
    finally:
        for k, v in prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
