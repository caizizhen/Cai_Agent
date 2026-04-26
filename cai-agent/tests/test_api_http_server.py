"""HM-02b：``api_http_server`` 最小只读 HTTP API。"""

from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from cai_agent.api_http_server import AgentApiRequestHandler, AgentApiThreadingServer

_SCHEMAS = Path(__file__).resolve().parents[1] / "src" / "cai_agent" / "schemas"


def _start(ws: Path, token: str | None, *, config_path: str | None = None) -> AgentApiThreadingServer:
    httpd = AgentApiThreadingServer(("127.0.0.1", 0), AgentApiRequestHandler)
    httpd.workspace = ws
    httpd.api_token = token
    httpd.api_config_path = config_path
    th = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    th.start()
    return httpd


def _url(httpd: AgentApiThreadingServer, path: str) -> str:
    host, port = httpd.server_address
    return f"http://{host}:{port}{path}"


def test_api_profiles_use_server_config_path_and_workspace(tmp_path: Path) -> None:
    """HM-N01-D03：HTTP API 使用显式 ``api_config_path`` 与 CLI ``--config`` 对齐，且 workspace 与 ``-w`` 一致。"""
    ws = (tmp_path / "proj").resolve()
    ws.mkdir()
    cfg = tmp_path / "custom.toml"
    cfg.write_text(
        "\n".join(
            [
                "[llm]",
                'provider = "openai_compatible"',
                'base_url = "http://127.0.0.1:9/v1"',
                'model = "m"',
                'api_key = "k"',
                "",
                "[agent]",
                "mock = true",
                "",
                "[models]",
                'active = "api2"',
                "",
                "[[models.profile]]",
                'id = "api1"',
                'provider = "openai_compatible"',
                'base_url = "http://127.0.0.1:9/v1"',
                'model = "m1"',
                'api_key = "k"',
                "",
                "[[models.profile]]",
                'id = "api2"',
                'provider = "openai_compatible"',
                'base_url = "http://127.0.0.1:9/v1"',
                'model = "m2"',
                'api_key = "k"',
                "",
            ],
        ),
        encoding="utf-8",
    )
    httpd = _start(ws, None, config_path=str(cfg))
    try:
        with urllib.request.urlopen(_url(httpd, "/v1/profiles"), timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        assert data.get("schema_version") == "api_profiles_v1"
        assert data.get("active_profile_id") == "api2"
        pc = data.get("profile_contract") or {}
        assert pc.get("workspace_root") == str(ws)
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_api_healthz_without_bearer_when_token_set(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    httpd = _start(root, "tok")
    try:
        url = _url(httpd, "/healthz")
        with urllib.request.urlopen(url, timeout=5) as resp:
            assert resp.status == 200
            assert (resp.headers.get("X-Cai-Agent-Api-Version") or "") == "0"
            body = json.loads(resp.read().decode("utf-8"))
        assert body.get("ok") is True
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_api_health_alias_without_bearer_when_token_set(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    httpd = _start(root, "tok")
    try:
        with urllib.request.urlopen(_url(httpd, "/health"), timeout=5) as resp:
            assert resp.status == 200
            body = json.loads(resp.read().decode("utf-8"))
        assert body.get("ok") is True
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_api_status_unauthorized_without_bearer(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    httpd = _start(root, "secret")
    try:
        url = _url(httpd, "/v1/status")
        with pytest.raises(urllib.error.HTTPError) as ei:
            urllib.request.urlopen(url, timeout=5)
        assert ei.value.code == 401
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_api_status_ok_with_bearer(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    httpd = _start(root, "abc")
    try:
        req = urllib.request.Request(_url(httpd, "/v1/status"))
        req.add_header("Authorization", "Bearer abc")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        assert data.get("schema_version") == "api_status_v1"
        assert data.get("workspace") == str(root)
        gs = data.get("gateway_summary") or {}
        assert gs.get("schema_version") == "gateway_summary_v1"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_api_doctor_summary_no_base_url(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    cfg = root / "cai-agent.toml"
    cfg.write_text(
        '[llm]\nprovider = "openai_compatible"\nbase_url = "http://127.0.0.1:9/v1"\n'
        'model = "m"\napi_key = "k"\n\n[agent]\nmock = true\n\n[models]\nactive = "default"\n',
        encoding="utf-8",
    )
    prev = __import__("os").environ.get("CAI_CONFIG")
    try:
        __import__("os").environ["CAI_CONFIG"] = str(cfg)
        httpd = _start(root, None)
        try:
            with urllib.request.urlopen(_url(httpd, "/v1/doctor/summary"), timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            assert data.get("schema_version") == "api_doctor_summary_v1"
            assert "base_url" not in data
            assert "model" not in data
            assert data.get("mock") is True
            mp = data.get("memory_provider") or {}
            assert mp.get("schema_version") == "memory_active_provider_v1"
            assert mp.get("active_provider") == "local_entries_jsonl"
            tp = data.get("tool_provider") or {}
            assert tp.get("schema_version") == "tool_provider_contract_v1"
            assert isinstance(data.get("ecc_home_sync_drift_targets"), (list, type(None)))
        finally:
            httpd.shutdown()
            httpd.server_close()
    finally:
        import os

        if prev is None:
            os.environ.pop("CAI_CONFIG", None)
        else:
            os.environ["CAI_CONFIG"] = prev


def test_api_run_due_dry_run_and_execute_forbidden(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    httpd = _start(root, None)
    try:
        base = _url(httpd, "/v1/tasks/run-due")
        req = urllib.request.Request(base, data=json.dumps({}).encode("utf-8"), method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=5) as resp:
            d1 = json.loads(resp.read().decode("utf-8"))
        assert d1.get("schema_version") == "api_tasks_run_due_v1"
        assert d1.get("mode") == "dry-run"

        req2 = urllib.request.Request(
            base,
            data=json.dumps({"dry_run": False}).encode("utf-8"),
            method="POST",
        )
        req2.add_header("Content-Type", "application/json")
        with pytest.raises(urllib.error.HTTPError) as ei:
            urllib.request.urlopen(req2, timeout=5)
        assert ei.value.code == 403
    finally:
        httpd.shutdown()
        httpd.server_close()


def _prepare_workspace_with_profile(root: Path) -> str:
    cfg = root / "cai-agent.toml"
    cfg.write_text(
        "\n".join(
            [
                "[llm]",
                'provider = "openai_compatible"',
                'base_url = "http://127.0.0.1:9/v1"',
                'model = "m"',
                'api_key = "k"',
                "",
                "[agent]",
                "mock = true",
                "",
                "[models]",
                'active = "p1"',
                "",
                "[[models.profile]]",
                'id = "p1"',
                'provider = "openai_compatible"',
                'base_url = "http://127.0.0.1:9/v1"',
                'model = "m"',
                'api_key = "k"',
                "",
            ],
        ),
        encoding="utf-8",
    )
    return str(cfg)


def test_api_models_summary_whitelist(tmp_path: Path) -> None:
    import os as _os

    root = tmp_path.resolve()
    cfg = _prepare_workspace_with_profile(root)
    prev = _os.environ.get("CAI_CONFIG")
    try:
        _os.environ["CAI_CONFIG"] = cfg
        httpd = _start(root, None)
        try:
            with urllib.request.urlopen(_url(httpd, "/v1/models/summary"), timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            assert data.get("schema_version") == "api_models_summary_v1"
            assert data.get("active_profile_id") == "p1"
            assert data.get("profiles_count") == 1
            assert data.get("profile_ids") == ["p1"]
            contract = data.get("profile_contract") or {}
            assert contract.get("schema_version") == "profile_contract_v1"
            assert "base_url" not in data
            assert "api_key" not in data
        finally:
            httpd.shutdown()
            httpd.server_close()
    finally:
        if prev is None:
            _os.environ.pop("CAI_CONFIG", None)
        else:
            _os.environ["CAI_CONFIG"] = prev


def test_api_profiles_route_contains_profile_contract(tmp_path: Path) -> None:
    import os as _os

    root = tmp_path.resolve()
    cfg = _prepare_workspace_with_profile(root)
    prev = _os.environ.get("CAI_CONFIG")
    try:
        _os.environ["CAI_CONFIG"] = cfg
        httpd = _start(root, None)
        try:
            with urllib.request.urlopen(_url(httpd, "/v1/profiles"), timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            assert data.get("schema_version") == "api_profiles_v1"
            assert data.get("active_profile_id") == "p1"
            assert data.get("profiles_count") == 1
            rows = data.get("profiles") or []
            assert rows and rows[0].get("id") == "p1"
            assert rows[0].get("api_key_present") is True
            contract = data.get("profile_contract") or {}
            assert contract.get("schema_version") == "profile_contract_v1"
        finally:
            httpd.shutdown()
            httpd.server_close()
    finally:
        if prev is None:
            _os.environ.pop("CAI_CONFIG", None)
        else:
            _os.environ["CAI_CONFIG"] = prev


def test_api_models_capabilities_whitelist(tmp_path: Path) -> None:
    import os as _os

    root = tmp_path.resolve()
    cfg = _prepare_workspace_with_profile(root)
    prev = _os.environ.get("CAI_CONFIG")
    try:
        _os.environ["CAI_CONFIG"] = cfg
        httpd = _start(root, None)
        try:
            with urllib.request.urlopen(
                _url(httpd, "/v1/models/capabilities"),
                timeout=5,
            ) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            assert data.get("schema_version") == "api_models_capabilities_v1"
            caps = data.get("model_capabilities") or {}
            assert caps.get("schema_version") == "model_capabilities_list_v1"
            assert caps.get("active_profile_id") == "p1"
            row = caps.get("profiles", [])[0]
            assert row.get("profile_id") == "p1"
            assert "api_key" not in row
            assert "base_url" not in row
            assert "capabilities" in row
        finally:
            httpd.shutdown()
            httpd.server_close()
    finally:
        if prev is None:
            _os.environ.pop("CAI_CONFIG", None)
        else:
            _os.environ["CAI_CONFIG"] = prev


def test_api_openai_models_list(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    cfg = _prepare_workspace_with_profile(root)
    prev = os.environ.get("CAI_CONFIG")
    try:
        os.environ["CAI_CONFIG"] = cfg
        httpd = _start(root, None)
        try:
            with urllib.request.urlopen(_url(httpd, "/v1/models"), timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            assert data.get("schema_version") == "api_openai_models_v1"
            assert data.get("object") == "list"
            rows = data.get("data") or []
            assert rows[0].get("id") == "m"
            assert rows[0].get("object") == "model"
            assert rows[0].get("cai_profile_id") == "p1"
            assert "api_key" not in rows[0]
            assert "base_url" not in rows[0]
        finally:
            httpd.shutdown()
            httpd.server_close()
    finally:
        if prev is None:
            os.environ.pop("CAI_CONFIG", None)
        else:
            os.environ["CAI_CONFIG"] = prev


def test_api_openai_chat_completions_non_streaming(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    cfg = _prepare_workspace_with_profile(root)
    metrics_path = root / ".cai" / "metrics.jsonl"
    prev_cfg = os.environ.get("CAI_CONFIG")
    prev_metrics = os.environ.get("CAI_METRICS_JSONL")
    try:
        os.environ["CAI_CONFIG"] = cfg
        os.environ["CAI_METRICS_JSONL"] = str(metrics_path)
        httpd = _start(root, None)
        try:
            req = urllib.request.Request(
                _url(httpd, "/v1/chat/completions"),
                data=json.dumps(
                    {
                        "model": "p1",
                        "messages": [{"role": "user", "content": "hello"}],
                        "stream": False,
                    },
                ).encode("utf-8"),
                method="POST",
            )
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            assert data.get("schema_version") == "api_openai_chat_completion_v1"
            assert data.get("object") == "chat.completion"
            assert data.get("model") == "m"
            choice = data.get("choices", [])[0]
            assert choice.get("message", {}).get("role") == "assistant"
            assert "CAI_MOCK" in choice.get("message", {}).get("content", "")
            cai = data.get("cai_model_response") or {}
            assert cai.get("schema_version") == "model_response_v1"
            assert cai.get("profile_id") == "p1"
            assert cai.get("provider") == "openai_compatible"
        finally:
            httpd.shutdown()
            httpd.server_close()

        row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
        assert row.get("module") == "api"
        assert row.get("event") == "api.chat_completions"
        assert row.get("provider") == "openai_compatible"
        assert row.get("model") == "m"
        assert row.get("profile_id") == "p1"
    finally:
        if prev_cfg is None:
            os.environ.pop("CAI_CONFIG", None)
        else:
            os.environ["CAI_CONFIG"] = prev_cfg
        if prev_metrics is None:
            os.environ.pop("CAI_METRICS_JSONL", None)
        else:
            os.environ["CAI_METRICS_JSONL"] = prev_metrics


def test_api_openai_chat_completions_streaming_sse(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    cfg = _prepare_workspace_with_profile(root)
    prev = os.environ.get("CAI_CONFIG")
    try:
        os.environ["CAI_CONFIG"] = cfg
        httpd = _start(root, None)
        try:
            req = urllib.request.Request(
                _url(httpd, "/v1/chat/completions"),
                data=json.dumps({"model": "m", "messages": [], "stream": True}).encode("utf-8"),
                method="POST",
            )
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=5) as resp:
                assert resp.status == 200
                assert (resp.headers.get("Content-Type") or "").startswith("text/event-stream")
                raw = resp.read().decode("utf-8")
            assert "data: [DONE]" in raw
            payload_lines = [
                line.removeprefix("data: ").strip()
                for line in raw.splitlines()
                if line.startswith("data: {")
            ]
            assert len(payload_lines) >= 2
            first = json.loads(payload_lines[0])
            assert first.get("schema_version") == "api_openai_chat_completion_chunk_v1"
            assert first.get("object") == "chat.completion.chunk"
            assert first.get("choices", [])[0].get("delta", {}).get("role") == "assistant"
            assert "CAI_MOCK" in first.get("choices", [])[0].get("delta", {}).get("content", "")
            assert first.get("cai_model_response", {}).get("schema_version") == "model_response_v1"
            final = json.loads(payload_lines[-1])
            assert final.get("choices", [])[0].get("finish_reason") == "stop"
        finally:
            httpd.shutdown()
            httpd.server_close()
    finally:
        if prev is None:
            os.environ.pop("CAI_CONFIG", None)
        else:
            os.environ["CAI_CONFIG"] = prev


def test_api_plugins_surface_whitelist_and_compat(tmp_path: Path) -> None:
    import os as _os

    root = tmp_path.resolve()
    cfg = _prepare_workspace_with_profile(root)
    prev = _os.environ.get("CAI_CONFIG")
    try:
        _os.environ["CAI_CONFIG"] = cfg
        httpd = _start(root, None)
        try:
            with urllib.request.urlopen(_url(httpd, "/v1/plugins/surface"), timeout=5) as resp:
                base_payload = json.loads(resp.read().decode("utf-8"))
            assert base_payload.get("schema_version") == "api_plugins_surface_v1"
            assert "components" in base_payload
            assert "project_root" not in base_payload
            assert "compat_matrix" not in base_payload

            with urllib.request.urlopen(
                _url(httpd, "/v1/plugins/surface?compat=1"),
                timeout=5,
            ) as resp:
                with_compat = json.loads(resp.read().decode("utf-8"))
            cm = with_compat.get("compat_matrix") or {}
            assert cm.get("schema_version") == "plugin_compat_matrix_v1"
        finally:
            httpd.shutdown()
            httpd.server_close()
    finally:
        if prev is None:
            _os.environ.pop("CAI_CONFIG", None)
        else:
            _os.environ["CAI_CONFIG"] = prev


def test_api_release_runbook_summary(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    httpd = _start(root, None)
    try:
        with urllib.request.urlopen(_url(httpd, "/v1/release/runbook"), timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        assert data.get("schema_version") == "api_release_runbook_v1"
        rb = data.get("release_runbook") or {}
        assert isinstance(rb.get("runbook_steps"), list)
        assert "workspace" not in rb
        assert "repo_root" not in rb
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_api_gateway_federation_summary(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    httpd = _start(root, None)
    try:
        with urllib.request.urlopen(_url(httpd, "/v1/gateway/federation-summary"), timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        assert data.get("schema_version") == "gateway_federation_summary_v1"
        assert isinstance(data.get("platforms"), list)
        assert isinstance(data.get("federation"), dict)
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_api_new_routes_require_bearer(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    httpd = _start(root, "abc")
    try:
        for path in (
            "/v1/models",
            "/v1/models/summary",
            "/v1/models/capabilities",
            "/v1/plugins/surface",
            "/v1/release/runbook",
            "/v1/gateway/federation-summary",
        ):
            with pytest.raises(urllib.error.HTTPError) as ei:
                urllib.request.urlopen(_url(httpd, path), timeout=5)
            assert ei.value.code == 401
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_api_gateway_route_preview_dry_run_only(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    httpd = _start(root, None)
    try:
        url = _url(httpd, "/v1/gateway/route-preview")
        req = urllib.request.Request(
            url,
            data=json.dumps({"platform": "telegram", "channel_id": "42:7", "dry_run": True}).encode("utf-8"),
            method="POST",
        )
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        assert data.get("schema_version") == "gateway_proxy_route_v1"
        assert data.get("dry_run") is True
        assert (data.get("source") or {}).get("platform") == "telegram"

        req2 = urllib.request.Request(
            url,
            data=json.dumps({"platform": "telegram", "dry_run": False}).encode("utf-8"),
            method="POST",
        )
        req2.add_header("Content-Type", "application/json")
        with pytest.raises(urllib.error.HTTPError) as ei:
            urllib.request.urlopen(req2, timeout=5)
        assert ei.value.code == 403
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_api_openai_chat_completions_requires_bearer(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    httpd = _start(root, "abc")
    try:
        req = urllib.request.Request(
            _url(httpd, "/v1/chat/completions"),
            data=json.dumps({"messages": [{"role": "user", "content": "hi"}]}).encode("utf-8"),
            method="POST",
        )
        req.add_header("Content-Type", "application/json")
        with pytest.raises(urllib.error.HTTPError) as ei:
            urllib.request.urlopen(req, timeout=5)
        assert ei.value.code == 401
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_api_models_capabilities_v1_schema_file() -> None:
    doc = json.loads((_SCHEMAS / "api_models_capabilities_v1.schema.json").read_text(encoding="utf-8"))
    assert doc["properties"]["schema_version"]["const"] == "api_models_capabilities_v1"
    assert doc["properties"]["model_capabilities"]["properties"]["schema_version"]["const"] == "model_capabilities_list_v1"


def test_api_openai_models_v1_schema_file() -> None:
    doc = json.loads((_SCHEMAS / "api_openai_models_v1.schema.json").read_text(encoding="utf-8"))
    assert doc["properties"]["schema_version"]["const"] == "api_openai_models_v1"
    assert doc["properties"]["object"]["const"] == "list"


def test_api_openai_chat_completion_v1_schema_file() -> None:
    doc = json.loads((_SCHEMAS / "api_openai_chat_completion_v1.schema.json").read_text(encoding="utf-8"))
    assert doc["properties"]["schema_version"]["const"] == "api_openai_chat_completion_v1"
    assert doc["properties"]["cai_model_response"]["properties"]["schema_version"]["const"] == "model_response_v1"


def test_api_openai_chat_completion_chunk_v1_schema_file() -> None:
    doc = json.loads((_SCHEMAS / "api_openai_chat_completion_chunk_v1.schema.json").read_text(encoding="utf-8"))
    assert doc["properties"]["schema_version"]["const"] == "api_openai_chat_completion_chunk_v1"
    assert doc["properties"]["object"]["const"] == "chat.completion.chunk"


def test_api_profiles_v1_schema_file() -> None:
    doc = json.loads((_SCHEMAS / "api_profiles_v1.schema.json").read_text(encoding="utf-8"))
    assert doc["properties"]["schema_version"]["const"] == "api_profiles_v1"
    assert doc["properties"]["profile_contract"]["properties"]["schema_version"]["const"] == "profile_contract_v1"
