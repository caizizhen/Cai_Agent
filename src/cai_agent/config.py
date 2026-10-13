"""Configuration: YAML file + environment overrides + CLI flags."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.lower() in ("1", "true", "yes", "on")


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML/JSON config; return {} on missing or invalid files."""
    if not path.is_file():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    if path.suffix.lower() == ".json":
        import json

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}
    try:
        import yaml  # type: ignore
    except ImportError:
        return {}
    try:
        data = yaml.safe_load(text) or {}
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def normalize_base_url(base_url: str, provider: str) -> str:
    """Normalize provider base URL (OpenAI keeps /v1; Anthropic root host)."""
    url = (base_url or "").strip().rstrip("/")
    # Fix common typos like http://host:1111//v1
    while "//" in url.replace("://", ""):
        url = url.replace("://", "\0").replace("//", "/").replace("\0", "://")
    prov = (provider or "openai").lower()
    if prov in ("anthropic", "anthropic-messages", "claude"):
        if not url:
            url = "https://api.anthropic.com"
        if url.endswith("/v1"):
            url = url[:-3].rstrip("/")
        return url
    if not url:
        url = "http://localhost:1234/v1"
    if not url.endswith("/v1"):
        url = url + "/v1"
    return url


@dataclass(frozen=True)
class Settings:
    """Runtime settings for the Pi engine and surfaces."""

    workspace: str
    base_url: str
    model: str
    api_key: str
    http_trust_env: bool
    max_iterations: int
    command_timeout_sec: float
    mock: bool
    stream: bool = True
    debug: bool = False
    provider: str = "openai"

    @classmethod
    def from_env(cls, config_path: str | Path | None = None) -> Settings:
        """
        Load settings.

        Precedence (highest last): defaults → YAML/JSON file → environment.
        """
        file_cfg: dict[str, Any] = {}
        candidates: list[Path] = []
        if config_path:
            candidates.append(Path(config_path))
        env_cfg = os.getenv("CAI_CONFIG")
        if env_cfg:
            candidates.append(Path(env_cfg))
        candidates.extend(
            [
                Path.cwd() / "cai.config.yaml",
                Path.cwd() / "cai.config.yml",
                Path.cwd() / "config.yaml",
            ],
        )
        for p in candidates:
            file_cfg = _load_yaml(p)
            if file_cfg:
                break

        workspace = os.path.abspath(
            os.getenv("CAI_WORKSPACE")
            or str(file_cfg.get("workspace") or os.getcwd()),
        )
        provider_raw = (
            os.getenv("CAI_PROVIDER")
            or str(file_cfg.get("provider") or "openai")
        ).lower()
        provider = (
            "anthropic"
            if provider_raw in ("anthropic", "anthropic-messages", "claude")
            else "openai"
        )
        default_base = (
            "https://api.anthropic.com"
            if provider == "anthropic"
            else "http://localhost:1234/v1"
        )
        base = normalize_base_url(
            os.getenv("LM_BASE_URL") or str(file_cfg.get("base_url") or default_base),
            provider,
        )

        max_iter = int(
            os.getenv("CAI_MAX_ITER")
            or file_cfg.get("max_steps")
            or file_cfg.get("max_iterations")
            or 16,
        )
        stream = _env_bool("CAI_STREAM", bool(file_cfg.get("stream", True)))
        debug = _env_bool("CAI_DEBUG", bool(file_cfg.get("debug", False)))
        mock = _env_bool("CAI_MOCK", bool(file_cfg.get("mock", False)))
        default_model = "claude-sonnet-4-5" if provider == "anthropic" else "google/gemma-4-31b"

        return cls(
            workspace=workspace,
            base_url=base,
            model=os.getenv("LM_MODEL") or str(file_cfg.get("model") or default_model),
            api_key=os.getenv("LM_API_KEY") or str(file_cfg.get("api_key") or "lm-studio"),
            http_trust_env=_env_bool("LM_HTTP_TRUST_ENV", bool(file_cfg.get("http_trust_env", False))),
            max_iterations=max_iter,
            command_timeout_sec=float(
                os.getenv("CAI_CMD_TIMEOUT") or file_cfg.get("command_timeout_sec") or 120,
            ),
            mock=mock,
            stream=stream,
            debug=debug,
            provider=provider,
        )

    def with_overrides(
        self,
        *,
        model: str | None = None,
        max_steps: int | None = None,
        stream: bool | None = None,
        debug: bool | None = None,
        workspace: str | None = None,
        mock: bool | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        provider: str | None = None,
    ) -> Settings:
        """Return a copy with CLI-flag / runtime overrides applied."""
        prov = (provider or self.provider or "openai").lower()
        if prov not in ("openai", "anthropic"):
            prov = "openai"
        url = normalize_base_url(base_url or self.base_url, prov)
        return replace(
            self,
            model=model or self.model,
            max_iterations=max_steps if max_steps is not None else self.max_iterations,
            stream=self.stream if stream is None else stream,
            debug=self.debug if debug is None else debug,
            workspace=os.path.abspath(workspace) if workspace else self.workspace,
            mock=self.mock if mock is None else mock,
            base_url=url,
            api_key=api_key if api_key is not None else self.api_key,
            provider=prov,
        )
