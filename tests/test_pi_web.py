from __future__ import annotations

from starlette.testclient import TestClient

from cai_agent.surfaces.web import SessionHub, build_app
from cai_agent.surfaces import web_api


def test_info_and_ui_shell(tmp_path, monkeypatch):
    monkeypatch.setenv("CAI_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CAI_WORKSPACE", str(tmp_path / "ws"))
    (tmp_path / "ws").mkdir()
    hub = SessionHub()
    client = TestClient(build_app(hub))
    info = client.get("/api/info").json()
    assert info["architecture"] == "layered-pi+harness-ui"
    assert info["layers"] == ["ui", "adapter", "engine"]
    assert "read" in info["tools"]
    html = client.get("/").text
    assert "workspace-tree" in html
    assert "settings-drawer" in html
    assert "HARNESS" in html
    css = client.get("/static/app.css").text
    assert "--dsw-brand" in css
    js = client.get("/static/app.js").text
    assert "highlightCode" in js


def test_workspace_apis(tmp_path, monkeypatch):
    monkeypatch.setenv("CAI_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CAI_WORKSPACE", str(tmp_path / "ws"))
    ws = tmp_path / "ws"
    ws.mkdir()
    hub = SessionHub()
    client = TestClient(build_app(hub))
    created = client.post(
        "/api/workspace/create",
        json={"path": "n.md", "kind": "file", "content": "# x\n"},
    )
    assert created.status_code == 200
    tree = client.get("/api/workspace/tree").json()
    assert any(e["name"] == "n.md" for e in tree["entries"])
    got = client.get("/api/workspace/file?path=n.md").json()
    assert got["content"].replace("\r\n", "\n") == "# x\n"
    put = client.put("/api/workspace/file", json={"path": "n.md", "content": "y\n"})
    assert put.status_code == 200
    assert (ws / "n.md").read_text(encoding="utf-8").replace("\r\n", "\n") == "y\n"


def test_chat_rpc_mock(tmp_path, monkeypatch):
    monkeypatch.setenv("CAI_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CAI_WORKSPACE", str(tmp_path / "ws"))
    monkeypatch.setenv("CAI_MOCK", "1")
    monkeypatch.setenv("CAI_MOCK_REPLY", "rpc-hi")
    (tmp_path / "ws").mkdir()
    # Force settings reload
    from cai_agent.config import Settings

    hub = SessionHub()
    hub.settings = Settings.from_env()
    client = TestClient(build_app(hub))
    res = client.post(
        "/rpc",
        json={"jsonrpc": "2.0", "id": 1, "method": "chat", "params": {"message": "hi"}},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["result"]["reply"] == "rpc-hi"
    sid = body["result"]["session_id"]
    listed = client.get("/api/sessions").json()
    assert any(s["id"] == sid for s in listed["sessions"])


def test_web_api_helpers(tmp_path, monkeypatch):
    monkeypatch.setenv("CAI_HOME", str(tmp_path / "home"))
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "f.txt").write_text("z", encoding="utf-8")
    entries = web_api.list_workspace_tree(str(ws), ".", depth=1)
    assert any(e["name"] == "f.txt" for e in entries)
    web_api.save_settings({"theme": "light"})
    assert web_api.load_settings()["theme"] == "light"
