from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any


def build_voice_provider_contract_payload() -> dict[str, Any]:
    """HM-N08-D01: voice provider contract (STT/TTS/health)."""
    provider = str(os.environ.get("CAI_VOICE_PROVIDER", "") or "").strip() or "none"
    stt_model = str(os.environ.get("CAI_VOICE_STT_MODEL", "") or "").strip() or None
    tts_model = str(os.environ.get("CAI_VOICE_TTS_MODEL", "") or "").strip() or None
    endpoint = str(os.environ.get("CAI_VOICE_ENDPOINT", "") or "").strip() or None
    api_key_present = bool(str(os.environ.get("CAI_VOICE_API_KEY", "") or "").strip())
    configured = provider != "none" and bool(endpoint) and api_key_present
    return {
        "schema_version": "voice_provider_contract_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "provider": provider,
        "stt": {
            "enabled": bool(stt_model),
            "model": stt_model,
            "input_formats": ["wav", "mp3", "ogg"],
        },
        "tts": {
            "enabled": bool(tts_model),
            "model": tts_model,
            "output_formats": ["wav", "mp3"],
        },
        "health": {
            "configured": configured,
            "endpoint_configured": bool(endpoint),
            "api_key_present": api_key_present,
            "status": "configured" if configured else "not_configured",
        },
    }


__all__ = ["build_voice_provider_contract_payload"]
