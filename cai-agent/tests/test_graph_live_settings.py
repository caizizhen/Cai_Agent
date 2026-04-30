"""build_app(settings_supplier=...) feeds fresh Settings into tools_node."""

from __future__ import annotations

import os
import textwrap
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


def _settings(ws: Path, *, unrestricted: bool) -> object:
    import tempfile as tf

    from cai_agent.config import Settings

    body = textwrap.dedent(
        f"""
        [llm]
        base_url = "http://localhost/v1"
        model = "m"
        api_key = "k"
        [agent]
        workspace = "{ws.as_posix()}"
        [permissions]
        read_file = "allow"
        list_dir = "allow"
        [safety]
        unrestricted_mode = {str(unrestricted).lower()}
        dangerous_confirmation_required = false
        """,
    )
    f = tf.NamedTemporaryFile("w", suffix=".toml", delete=False, encoding="utf-8")
    f.write(body)
    p = f.name
    f.close()
    try:
        return Settings.from_env(config_path=p)
    finally:
        os.unlink(p)


class SettingsSupplierTests(unittest.TestCase):
    def test_tools_node_dispatch_sees_updated_settings(self) -> None:
        from cai_agent.graph import build_app

        captured: list[bool] = []

        def fake_dispatch(settings_obj: object, name: str, args: dict) -> str:
            captured.append(bool(getattr(settings_obj, "unrestricted_mode", False)))
            return "ok"

        with TemporaryDirectory() as td:
            ws = Path(td).resolve()
            s_off = _settings(ws, unrestricted=False)
            holder = [s_off]

            state = {
                "messages": [{"role": "user", "content": "{}"}],
                "iteration": 1,
                "pending": {"name": "list_dir", "args": {"path": "."}},
                "finished": False,
                "answer": "",
                "tool_call_count": 0,
            }

            with patch("cai_agent.graph.dispatch", side_effect=fake_dispatch):
                app = build_app(s_off, settings_supplier=lambda: holder[0])
                tools = app.nodes["tools"]
                tools.invoke(state)
                holder[0] = replace(s_off, unrestricted_mode=True)
                tools.invoke(state)

            self.assertEqual(captured, [False, True])

