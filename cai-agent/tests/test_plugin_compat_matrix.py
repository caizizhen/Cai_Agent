"""plugin_compat_matrix_v1 与 plugins --with-compat-matrix。"""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cai_agent.__main__ import main
from cai_agent.plugin_registry import build_plugin_compat_matrix


class PluginCompatMatrixTests(unittest.TestCase):
    def test_build_matrix_schema(self) -> None:
        m = build_plugin_compat_matrix()
        self.assertEqual(m.get("schema_version"), "plugin_compat_matrix_v1")
        self.assertEqual(m.get("detail_doc_en"), "docs/PLUGIN_COMPAT_MATRIX.md")
        self.assertEqual(m.get("doc_anchor_en"), "docs/CROSS_HARNESS_COMPATIBILITY.md")
        self.assertGreaterEqual(len(m.get("targets") or []), 3)
        rows = m.get("components_vs_targets")
        self.assertIsInstance(rows, list)
        names = {r.get("component") for r in rows if isinstance(r, dict)}
        self.assertIn("hooks", names)

    def test_plugins_json_with_compat_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "cai-agent.toml").write_text(
                '\n'.join(
                    [
                        '[llm]',
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
                    ]
                ),
                encoding="utf-8",
            )
            cfg = str(root / "cai-agent.toml")
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["plugins", "--config", cfg, "--json", "--with-compat-matrix"])
            self.assertEqual(rc, 0)
            pl = json.loads(buf.getvalue().strip())
            self.assertEqual(pl.get("schema_version"), "plugins_surface_v1")
            cm = pl.get("compat_matrix")
            self.assertIsInstance(cm, dict)
            self.assertEqual(cm.get("schema_version"), "plugin_compat_matrix_v1")
