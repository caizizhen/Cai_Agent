from __future__ import annotations

from starlette.testclient import TestClient

from cai_agent.surfaces.web import SessionHub, build_app
from cai_agent.surfaces import web_api


def test_runtime_get_put(tmp_path, monkeypatch):
    monkeypatch.setenv("CAI_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CAI_WORKSPACE", str(tmp_path / "ws"))
    (tmp_path / "ws").mkdir()

    hub = SessionHub()
    client = TestClient(build_app(hub))

    got = client.get("/api/runtime").json()
    assert "model" in got
    assert "base_url" in got
    assert "api_key" in got

    put = client.put(
        "/api/runtime",
        json={
            "model": "desk-model",
            "base_url": "http://127.0.0.1:9999/v1",
            "api_key": "secret-key-xyz",
            "max_steps": 7,
            "theme": "light",
            "approval": "confirm",
        },
    )
    assert put.status_code == 200
    body = put.json()
    assert body["model"] == "desk-model"
    assert body["max_steps"] == 7
    assert body["theme"] == "light"
    assert "secret" not in body["api_key"]
    assert hub.settings.model == "desk-model"
    assert hub.settings.max_iterations == 7
    assert web_api.load_settings()["theme"] == "light"

    # blank / masked key keeps previous
    put2 = client.put("/api/runtime", json={"api_key": "********", "model": "desk-model-2"})
    assert put2.status_code == 200
    assert hub.settings.api_key == "secret-key-xyz"
    assert hub.settings.model == "desk-model-2"


def test_info_includes_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("CAI_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CAI_WORKSPACE", str(tmp_path / "ws"))
    (tmp_path / "ws").mkdir()
    client = TestClient(build_app(SessionHub()))
    info = client.get("/api/info").json()
    assert "runtime" in info
    html = client.get("/").text
    assert "set-model" in html
    assert "set-base-url" in html
    assert "btn-fetch-models" in html
    assert "workspace-tree" in html
