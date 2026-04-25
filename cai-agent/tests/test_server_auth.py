from __future__ import annotations

import os

from cai_agent.server_auth import resolve_bearer_token


def test_resolve_bearer_token_prefers_first_non_empty() -> None:
    prev_api = os.environ.get("CAI_API_TOKEN")
    prev_ops = os.environ.get("CAI_OPS_API_TOKEN")
    try:
        os.environ["CAI_API_TOKEN"] = "api-token"
        os.environ["CAI_OPS_API_TOKEN"] = "ops-token"
        assert resolve_bearer_token("CAI_OPS_API_TOKEN", "CAI_API_TOKEN") == "ops-token"
        assert resolve_bearer_token("CAI_API_TOKEN", "CAI_OPS_API_TOKEN") == "api-token"
    finally:
        if prev_api is None:
            os.environ.pop("CAI_API_TOKEN", None)
        else:
            os.environ["CAI_API_TOKEN"] = prev_api
        if prev_ops is None:
            os.environ.pop("CAI_OPS_API_TOKEN", None)
        else:
            os.environ["CAI_OPS_API_TOKEN"] = prev_ops


def test_resolve_bearer_token_returns_none_when_all_empty() -> None:
    prev_api = os.environ.get("CAI_API_TOKEN")
    prev_ops = os.environ.get("CAI_OPS_API_TOKEN")
    try:
        os.environ["CAI_API_TOKEN"] = "   "
        os.environ["CAI_OPS_API_TOKEN"] = ""
        assert resolve_bearer_token("CAI_OPS_API_TOKEN", "CAI_API_TOKEN") is None
    finally:
        if prev_api is None:
            os.environ.pop("CAI_API_TOKEN", None)
        else:
            os.environ["CAI_API_TOKEN"] = prev_api
        if prev_ops is None:
            os.environ.pop("CAI_OPS_API_TOKEN", None)
        else:
            os.environ["CAI_OPS_API_TOKEN"] = prev_ops
