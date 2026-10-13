from __future__ import annotations

import json

import httpx
from starlette.testclient import TestClient

from cai_agent.surfaces.web import SessionHub, build_app
from cai_agent.surfaces import web_api


def test_workspaces_add_activate(tmp_path, monkeypatch):
    monkeypatch.setenv("CAI_HOME", str(tmp_path / "home"))
    ws1 = tmp_path / "ws1"
    ws2 = tmp_path / "ws2"
    ws1.mkdir()
    ws2.mkdir()
    monkeypatch.setenv("CAI_WORKSPACE", str(ws1))

    hub = SessionHub()
    client = TestClient(build_app(hub))

    listed = client.get("/api/workspaces").json()
    assert str(ws1.resolve()) in listed["items"] or listed["current"]

    added = client.post("/api/workspaces", json={"path": str(ws2), "activate": True})
    assert added.status_code == 200
    body = added.json()
    assert any(str(ws2.resolve()) in p or p.endswith("ws2") for p in body["items"])

    act = client.post("/api/workspaces/activate", json={"path": str(ws1)})
    assert act.status_code == 200
    assert "ws1" in act.json()["workspace"].replace("\\", "/")


def test_discover_models_mock(tmp_path, monkeypatch):
    monkeypatch.setenv("CAI_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CAI_WORKSPACE", str(tmp_path / "ws"))
    (tmp_path / "ws").mkdir()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/models")
        return httpx.Response(
            200,
            json={"data": [{"id": "alpha"}, {"id": "beta", "name": "Beta"}]},
        )

    transport = httpx.MockTransport(handler)

    async def fake_discover(base_url, api_key="", *, trust_env=False, provider="openai"):
        url = base_url.rstrip("/")
        if not url.endswith("/v1"):
            url += "/v1"
        async with httpx.AsyncClient(transport=transport) as client:
            r = await client.get(f"{url}/models", headers={"Authorization": f"Bearer {api_key}"})
        data = r.json()["data"]
        return [{"id": x["id"], "name": x.get("name") or x["id"]} for x in data]

    monkeypatch.setattr(web_api, "discover_models", fake_discover)
    hub = SessionHub()
    client = TestClient(build_app(hub))
    res = client.post(
        "/api/models/discover",
        json={"base_url": "http://example.test/v1", "api_key": "k"},
    )
    assert res.status_code == 200
    ids = [m["id"] for m in res.json()["models"]]
    assert ids == ["alpha", "beta"]


def test_ui_has_workspace_and_fetch_models(tmp_path, monkeypatch):
    monkeypatch.setenv("CAI_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CAI_WORKSPACE", str(tmp_path / "ws"))
    (tmp_path / "ws").mkdir()
    html = TestClient(build_app(SessionHub())).get("/").text
    assert "workspace-tree" in html
    assert "btn-ws-add" in html
    assert "btn-fetch-models" in html
    assert "set-model-select" in html


def test_sessions_carry_workspace_meta(tmp_path, monkeypatch):
    monkeypatch.setenv("CAI_HOME", str(tmp_path / "home"))
    ws = tmp_path / "proj"
    ws.mkdir()
    monkeypatch.setenv("CAI_WORKSPACE", str(ws))
    hub = SessionHub()
    client = TestClient(build_app(hub))
    created = client.post("/api/session/new").json()
    assert created["session_id"]
    listed = client.get("/api/sessions").json()["sessions"]
    assert listed
    row = next(s for s in listed if s["id"] == created["session_id"])
    assert "proj" in row["workspace"].replace("\\", "/")
    assert row.get("updated_at")


def test_session_delete(tmp_path, monkeypatch):
    monkeypatch.setenv("CAI_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CAI_WORKSPACE", str(tmp_path / "ws"))
    (tmp_path / "ws").mkdir()
    client = TestClient(build_app(SessionHub()))
    sid = client.post("/api/session/new").json()["session_id"]
    assert client.get("/api/sessions").json()["sessions"]
    deleted = client.delete(f"/api/session/{sid}")
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True
    assert client.get("/api/sessions").json()["sessions"] == []


def test_model_profiles_crud(tmp_path, monkeypatch):
    monkeypatch.setenv("CAI_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CAI_WORKSPACE", str(tmp_path / "ws"))
    (tmp_path / "ws").mkdir()
    client = TestClient(build_app(SessionHub()))

    a = client.post(
        "/api/models/profiles",
        json={
            "name": "Local",
            "provider": "openai",
            "base_url": "http://127.0.0.1:1234/v1",
            "model": "local-a",
            "api_key": "k1",
        },
    )
    assert a.status_code == 200
    assert a.json()["model"] == "local-a"
    assert len(a.json()["models"]) >= 1

    b = client.post(
        "/api/models/profiles",
        json={
            "name": "Claude",
            "provider": "anthropic",
            "base_url": "https://api.anthropic.com",
            "model": "claude-sonnet-4-5",
            "api_key": "sk-ant",
            "activate": False,
        },
    )
    assert b.status_code == 200
    models = b.json()["models"]
    assert len(models) >= 2
    claude = next(m for m in models if m["model"] == "claude-sonnet-4-5")
    act = client.post(f"/api/models/profiles/{claude['id']}/activate")
    assert act.status_code == 200
    assert act.json()["provider"] == "anthropic"
    assert act.json()["model"] == "claude-sonnet-4-5"

    # Re-activate must refresh top-level endpoint (no "toggle twice" lag).
    hub = SessionHub()
    client2 = TestClient(build_app(hub))
    local = next(m for m in client2.get("/api/runtime").json()["models"] if m["model"] == "local-a")
    client2.post(
        "/api/models/profiles",
        json={
            "id": "strata",
            "name": "Strata",
            "provider": "openai",
            "base_url": "http://127.0.0.1:1111//v1",
            "model": "qwen3.8-flash-next-iq3_s",
            "activate": True,
        },
    )
    view = client2.post("/api/models/profiles/strata/activate").json()
    assert view["model"] == "qwen3.8-flash-next-iq3_s"
    assert "1111" in view["base_url"]
    assert "//v1" not in view["base_url"].replace("://", "")
    hub.reload_settings()
    assert hub.settings.model == "qwen3.8-flash-next-iq3_s"
    assert "1111" in hub.settings.base_url

    # Switching back updates engine settings without keeping stale handle URL.
    client2.post(f"/api/models/profiles/{local['id']}/activate")
    hub.reload_settings()
    assert hub.settings.model == "local-a"
    assert "1234" in hub.settings.base_url

    html = client.get("/").text
    assert "model-profile-list" in html
    assert "btn-model-add" in html
