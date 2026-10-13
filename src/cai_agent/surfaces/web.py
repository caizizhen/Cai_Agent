from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from starlette.routing import Route

import os

from cai_agent.adapter.events import AgentEvent, EventKind
from cai_agent.config import Settings
from cai_agent.engine.factory import EngineHandle, create_engine
from cai_agent.pi_session.store import SessionStore
from cai_agent.surfaces import web_api

STATIC_DIR = Path(__file__).resolve().parent / "web_static"


class SessionHub:
    """
    Web surface hub: many Pi sessions, each wired through :class:`EngineBridge`.

    SSE payloads are derived from unified adapter :class:`AgentEvent` kinds so
    the Web UI never binds to engine-internal event names.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or web_api.settings_with_runtime()
        self.store = SessionStore()
        self.handles: dict[str, EngineHandle] = {}
        self.active_session_id: str | None = None
        self._sse_queues: list[asyncio.Queue[dict[str, Any]]] = []

    def apply_runtime(self, patch: dict[str, Any]) -> dict[str, Any]:
        """Persist runtime overrides and hot-reload hub settings."""
        ui_keys = {"theme", "approval", "sidebar_tab"}
        ui_patch = {k: patch[k] for k in ui_keys if k in patch}
        rt_patch = {k: v for k, v in patch.items() if k not in ui_keys}
        if ui_patch:
            web_api.save_settings(ui_patch)
        if rt_patch:
            web_api.save_runtime_file(rt_patch)
        self.settings = web_api.settings_with_runtime()
        if "workspace" in patch and patch["workspace"]:
            os.environ["CAI_WORKSPACE"] = self.settings.workspace
            try:
                web_api.add_workspace(self.settings.workspace, make_current=False)
            except ValueError:
                pass
        self.handles.clear()
        self.active_session_id = None
        return web_api.runtime_public_view(self.settings)

    @property
    def sessions(self) -> dict[str, EngineHandle]:
        """Back-compat alias used by older tests."""
        return self.handles

    def workspace(self) -> str:
        return self.settings.workspace

    def get_or_create(self, session_id: str | None = None) -> EngineHandle:
        if session_id and session_id in self.handles:
            return self.handles[session_id]
        handle = create_engine(
            workspace=self.workspace(),
            session_id=session_id,
            settings=self.settings,
            store=self.store,
        )
        sid = handle.session.session_id
        self.handles[sid] = handle
        self.active_session_id = sid
        handle.bus.subscribe(lambda ev, s=sid: self._on_bus(s, ev))
        return handle

    def _on_bus(self, session_id: str, ev: AgentEvent) -> None:
        payload = self._map_sse(session_id, ev)
        if payload is None:
            return
        for q in list(self._sse_queues):
            try:
                q.put_nowait(payload)
            except Exception:
                pass

    def _map_sse(self, session_id: str, ev: AgentEvent) -> dict[str, Any] | None:
        """Map adapter EventKind → legacy web front-end SSE envelope."""
        if ev.kind == EventKind.MESSAGE_STREAM:
            return {
                "event": "agent/assistant-stream",
                "session_id": session_id,
                "kind": ev.kind.value,
                "delta": ev.delta,
            }
        if ev.kind == EventKind.TOOL_INVOKE:
            return {
                "event": "agent/phase",
                "session_id": session_id,
                "kind": ev.kind.value,
                "phase": "tool",
                "name": ev.tool_name,
                "summary": str((ev.data or {}).get("args") or "")[:200],
            }
        if ev.kind == EventKind.TOOL_RESULT:
            return {
                "event": "agent/phase",
                "session_id": session_id,
                "kind": ev.kind.value,
                "phase": "tool_done",
                "name": ev.tool_name,
                "ok": ev.ok,
                "summary": (ev.delta or "")[:200],
            }
        if ev.kind == EventKind.THINKING_STREAM:
            return {
                "event": "agent/thinking",
                "session_id": session_id,
                "kind": ev.kind.value,
                "delta": ev.delta,
            }
        if ev.kind == EventKind.FINISHED:
            return {
                "event": "agent/end",
                "session_id": session_id,
                "kind": ev.kind.value,
            }
        if ev.kind == EventKind.STEP_START:
            return {
                "event": "agent/step",
                "session_id": session_id,
                "kind": ev.kind.value,
                "step": ev.step,
            }
        return None

    def add_sse_queue(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._sse_queues.append(q)
        return q

    def remove_sse_queue(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        try:
            self._sse_queues.remove(q)
        except ValueError:
            pass


# Back-compat alias for tests that import WebRuntimeHub
WebRuntimeHub = SessionHub


def build_app(hub: SessionHub | None = None, **_kwargs: Any) -> Starlette:
    settings = _kwargs.get("settings")
    hub = hub or SessionHub(settings=settings if isinstance(settings, Settings) else None)

    async def index(_: Request) -> FileResponse | HTMLResponse:
        path = STATIC_DIR / "index.html"
        if path.is_file():
            return FileResponse(path)
        return HTMLResponse("<h1>CAI</h1>")

    async def static_file(request: Request) -> FileResponse | HTMLResponse:
        name = request.path_params.get("path", "")
        path = (STATIC_DIR / name).resolve()
        if not str(path).startswith(str(STATIC_DIR.resolve())) or not path.is_file():
            return HTMLResponse("not found", status_code=404)
        return FileResponse(path)

    async def info(_: Request) -> JSONResponse:
        ui = web_api.load_settings()
        return JSONResponse(
            {
                "architecture": "layered-pi+harness-ui",
                "layers": ["ui", "adapter", "engine"],
                "model": hub.settings.model,
                "workspace": hub.workspace(),
                "session_id": hub.active_session_id,
                "tools": ["read", "write", "edit", "bash"],
                "settings": ui,
                "runtime": web_api.runtime_public_view(hub.settings, ui),
            },
        )

    async def get_settings(_: Request) -> JSONResponse:
        return JSONResponse(web_api.load_settings())

    async def put_settings(request: Request) -> JSONResponse:
        body = await request.json()
        if not isinstance(body, dict):
            return JSONResponse({"error": "object required"}, status_code=400)
        return JSONResponse(web_api.save_settings(body))

    async def get_runtime(_: Request) -> JSONResponse:
        return JSONResponse(web_api.runtime_public_view(hub.settings))

    async def put_runtime(request: Request) -> JSONResponse:
        body = await request.json()
        if not isinstance(body, dict):
            return JSONResponse({"error": "object required"}, status_code=400)
        try:
            return JSONResponse(hub.apply_runtime(body))
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=400)

    async def workspaces_list(_: Request) -> JSONResponse:
        return JSONResponse(web_api.list_workspaces(hub.workspace()))

    async def workspaces_add(request: Request) -> JSONResponse:
        body = await request.json()
        if not isinstance(body, dict):
            return JSONResponse({"error": "object required"}, status_code=400)
        path = str(body.get("path") or "").strip()
        if not path:
            return JSONResponse({"error": "path required"}, status_code=400)
        activate = bool(body.get("activate", True))
        try:
            web_api.add_workspace(path, make_current=activate)
            if activate:
                hub.apply_runtime({"workspace": os.path.abspath(path)})
            return JSONResponse(web_api.list_workspaces(hub.workspace()))
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)

    async def workspaces_activate(request: Request) -> JSONResponse:
        body = await request.json()
        path = str((body or {}).get("path") or "").strip()
        if not path:
            return JSONResponse({"error": "path required"}, status_code=400)
        try:
            web_api.add_workspace(path, make_current=True)
            return JSONResponse(hub.apply_runtime({"workspace": os.path.abspath(path)}))
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)

    async def models_discover(request: Request) -> JSONResponse:
        body = await request.json()
        if not isinstance(body, dict):
            return JSONResponse({"error": "object required"}, status_code=400)
        base_url = str(body.get("base_url") or hub.settings.base_url)
        api_key = str(body.get("api_key") or "")
        provider = str(body.get("provider") or hub.settings.provider or "openai")
        if not api_key or api_key == "********":
            api_key = hub.settings.api_key
        try:
            models = await web_api.discover_models(
                base_url,
                api_key,
                trust_env=hub.settings.http_trust_env,
                provider=provider,
            )
            return JSONResponse({"models": models, "base_url": base_url, "provider": provider})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=400)

    async def workspace_tree(request: Request) -> JSONResponse:
        workspace = hub.workspace()
        path = str(request.query_params.get("path") or ".")
        depth = int(request.query_params.get("depth") or 2)
        try:
            entries = web_api.list_workspace_tree(workspace, path, depth=depth)
            return JSONResponse({"workspace": workspace, "path": path, "entries": entries})
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)

    async def workspace_file(request: Request) -> JSONResponse:
        workspace = hub.workspace()
        path = str(request.query_params.get("path") or "")
        if not path:
            return JSONResponse({"error": "path required"}, status_code=400)
        try:
            return JSONResponse(web_api.read_workspace_file(workspace, path))
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)

    async def workspace_file_write(request: Request) -> JSONResponse:
        workspace = hub.workspace()
        body = await request.json()
        if not isinstance(body, dict):
            return JSONResponse({"error": "object required"}, status_code=400)
        path = str(body.get("path") or "")
        if "content" not in body:
            return JSONResponse({"error": "content required"}, status_code=400)
        try:
            return JSONResponse(
                web_api.write_workspace_file(workspace, path, str(body.get("content") or "")),
            )
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)

    async def workspace_mkdir(request: Request) -> JSONResponse:
        workspace = hub.workspace()
        body = await request.json()
        if not isinstance(body, dict):
            return JSONResponse({"error": "object required"}, status_code=400)
        try:
            return JSONResponse(web_api.mkdir_workspace(workspace, str(body.get("path") or "")))
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)

    async def workspace_create(request: Request) -> JSONResponse:
        workspace = hub.workspace()
        body = await request.json()
        if not isinstance(body, dict):
            return JSONResponse({"error": "object required"}, status_code=400)
        try:
            return JSONResponse(
                web_api.create_workspace_entry(
                    workspace,
                    str(body.get("path") or ""),
                    kind=str(body.get("kind") or "file"),
                    content=str(body.get("content") or ""),
                ),
            )
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)

    async def list_sessions(_: Request) -> JSONResponse:
        return JSONResponse({"sessions": hub.store.list_sessions()})

    async def session_transcript(request: Request) -> JSONResponse:
        sid = request.path_params["session_id"]
        msgs = hub.store.load_messages(sid)
        transcript = []
        for m in msgs:
            if m.role == "user":
                transcript.append({"role": "user", "content": m.content})
            elif m.role == "assistant":
                transcript.append(
                    {
                        "role": "assistant",
                        "content": m.content,
                        "tool_calls": m.tool_calls,
                    },
                )
            elif m.role == "tool":
                transcript.append(
                    {
                        "role": "tool",
                        "name": m.name,
                        "content": m.content,
                        "tool_call_id": m.tool_call_id,
                    },
                )
        return JSONResponse({"session_id": sid, "messages": transcript})

    async def new_session(_: Request) -> JSONResponse:
        handle = hub.get_or_create(None)
        return JSONResponse(
            {
                "session_id": handle.session.session_id,
                "workspace": handle.session.workspace,
            },
        )

    async def cancel(request: Request) -> JSONResponse:
        body = {}
        try:
            body = await request.json()
        except Exception:
            pass
        sid = str(body.get("session_id") or hub.active_session_id or "")
        if sid and sid in hub.handles:
            await hub.handles[sid].abort()
            return JSONResponse({"ok": True, "session_id": sid})
        return JSONResponse({"ok": False, "error": "no session"}, status_code=404)

    async def chat(request: Request) -> JSONResponse:
        body = await request.json()
        text = str(body.get("message") or body.get("text") or "").strip()
        if not text:
            return JSONResponse({"error": "message required"}, status_code=400)
        sid = body.get("session_id")
        handle = hub.get_or_create(str(sid) if sid else None)
        hub.active_session_id = handle.session.session_id

        async def _run() -> None:
            try:
                await handle.prompt(text)
            except Exception as e:
                for q in list(hub._sse_queues):
                    await q.put(
                        {
                            "event": "agent/error",
                            "session_id": handle.session.session_id,
                            "error": str(e),
                        },
                    )

        asyncio.create_task(_run())
        return JSONResponse({"ok": True, "session_id": handle.session.session_id})

    async def events(_: Request) -> StreamingResponse:
        q = hub.add_sse_queue()

        async def gen():
            try:
                yield f"data: {json.dumps({'event': 'ready'})}\n\n"
                while True:
                    try:
                        item = await asyncio.wait_for(q.get(), timeout=25.0)
                        yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
                    except asyncio.TimeoutError:
                        yield f"data: {json.dumps({'event': 'ping'})}\n\n"
            finally:
                hub.remove_sse_queue(q)

        return StreamingResponse(gen(), media_type="text/event-stream")

    async def rpc(request: Request) -> JSONResponse:
        body = await request.json()
        method = body.get("method")
        req_id = body.get("id")
        params = body.get("params") or {}
        try:
            if method == "chat":
                text = str(params.get("message") or "")
                handle = hub.get_or_create(params.get("session_id"))
                produced = await handle.prompt(text)
                reply = next(
                    (m.content for m in reversed(produced) if m.role == "assistant" and m.content),
                    "",
                )
                result = {"session_id": handle.session.session_id, "reply": reply}
            elif method == "list_sessions":
                result = {"sessions": hub.store.list_sessions()}
            elif method == "dump_config":
                from cai_agent.runtime import dump_info

                result = dump_info(hub.settings)
            else:
                return JSONResponse(
                    {"jsonrpc": "2.0", "id": req_id, "error": {"message": f"unknown {method}"}},
                    status_code=400,
                )
            return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": result})
        except Exception as e:
            return JSONResponse(
                {"jsonrpc": "2.0", "id": req_id, "error": {"message": str(e)}},
                status_code=500,
            )

    return Starlette(
        routes=[
            Route("/", index),
            Route("/static/{path:path}", static_file),
            Route("/api/info", info),
            Route("/api/settings", get_settings),
            Route("/api/settings", put_settings, methods=["PUT", "POST"]),
            Route("/api/runtime", get_runtime),
            Route("/api/runtime", put_runtime, methods=["PUT", "POST"]),
            Route("/api/workspaces", workspaces_list),
            Route("/api/workspaces", workspaces_add, methods=["POST"]),
            Route("/api/workspaces/activate", workspaces_activate, methods=["POST"]),
            Route("/api/models/discover", models_discover, methods=["POST"]),
            Route("/api/workspace/tree", workspace_tree),
            Route("/api/workspace/file", workspace_file),
            Route("/api/workspace/file", workspace_file_write, methods=["PUT", "POST"]),
            Route("/api/workspace/mkdir", workspace_mkdir, methods=["POST"]),
            Route("/api/workspace/create", workspace_create, methods=["POST"]),
            Route("/api/sessions", list_sessions),
            Route("/api/session/{session_id}/transcript", session_transcript),
            Route("/api/session/new", new_session, methods=["POST"]),
            Route("/api/cancel", cancel, methods=["POST"]),
            Route("/api/chat", chat, methods=["POST"]),
            Route("/api/events", events),
            Route("/rpc", rpc, methods=["POST"]),
        ],
    )


def run_web(
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    settings: Settings | None = None,
    **_kwargs: Any,
) -> None:
    """Serve the DSH-style Web UI over the layered EventBus."""
    import uvicorn

    app = build_app(SessionHub(settings=settings))
    uvicorn.run(app, host=host, port=port, log_level="info")
