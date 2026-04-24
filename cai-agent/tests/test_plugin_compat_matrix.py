"""plugin_compat_matrix_v1 与 plugins --with-compat-matrix / --compat-check。"""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cai_agent.__main__ import main
from cai_agent.plugin_registry import (
    build_plugin_compat_matrix,
    build_plugin_compat_matrix_check_v1,
)


def _write_min_config(root: Path) -> str:
    (root / "cai-agent.toml").write_text(
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
    return str(root / "cai-agent.toml")


class PluginCompatMatrixTests(unittest.TestCase):
    def test_build_matrix_schema(self) -> None:
        m = build_plugin_compat_matrix()
        self.assertEqual(m.get("schema_version"), "plugin_compat_matrix_v1")
        self.assertEqual(m.get("detail_doc_en"), "docs/PLUGIN_COMPAT_MATRIX.md")
        self.assertEqual(m.get("doc_anchor_en"), "docs/CROSS_HARNESS_COMPATIBILITY.md")
        self.assertEqual(
            m.get("governance_rfc"),
            "docs/rfc/ECC_03A_PLUGIN_VERSION_GOVERNANCE.zh-CN.md",
        )
        checklist = m.get("maintenance_checklist")
        self.assertIsInstance(checklist, list)
        self.assertGreater(len(checklist), 0)
        self.assertGreaterEqual(len(m.get("targets") or []), 3)
        rows = m.get("components_vs_targets")
        self.assertIsInstance(rows, list)
        names = {r.get("component") for r in rows if isinstance(r, dict)}
        self.assertIn("hooks", names)

    def test_plugins_json_with_compat_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = _write_min_config(root)
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
            self.assertIn("maintenance_checklist", cm)


class PluginCompatMatrixCheckTests(unittest.TestCase):
    def test_build_check_default_ok(self) -> None:
        report = build_plugin_compat_matrix_check_v1()
        self.assertEqual(report.get("schema_version"), "plugin_compat_matrix_check_v1")
        self.assertTrue(report.get("ok"))
        self.assertEqual(report.get("missing_components"), [])
        self.assertEqual(report.get("missing_targets"), [])
        self.assertEqual(report.get("row_mismatches"), [])
        self.assertEqual(
            report.get("matrix_schema_version"),
            "plugin_compat_matrix_v1",
        )

    def test_build_check_flags_missing_components(self) -> None:
        report = build_plugin_compat_matrix_check_v1(
            expected_components=("skills", "commands", "nonexistent_component"),
        )
        self.assertFalse(report.get("ok"))
        self.assertIn("nonexistent_component", report.get("missing_components") or [])

    def test_build_check_flags_missing_targets(self) -> None:
        report = build_plugin_compat_matrix_check_v1(
            expected_targets=("cursor", "codex", "opencode", "nonexistent_harness"),
        )
        self.assertFalse(report.get("ok"))
        self.assertIn("nonexistent_harness", report.get("missing_targets") or [])

    def test_plugins_compat_check_json_exit_0(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = _write_min_config(root)
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["plugins", "--config", cfg, "--json", "--compat-check"])
            self.assertEqual(rc, 0)
            pl = json.loads(buf.getvalue().strip())
            self.assertEqual(pl.get("schema_version"), "plugins_surface_v1")
            cc = pl.get("compat_check")
            self.assertIsInstance(cc, dict)
            self.assertEqual(cc.get("schema_version"), "plugin_compat_matrix_check_v1")
            self.assertTrue(cc.get("ok"))

    def test_plugins_compat_check_text_prints_summary(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = _write_min_config(root)
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["plugins", "--config", cfg, "--compat-check"])
            self.assertEqual(rc, 0)
            text = buf.getvalue()
            self.assertIn("compat_check=ok", text)
