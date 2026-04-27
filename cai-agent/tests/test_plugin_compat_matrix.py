"""plugin_compat_matrix_v1 与 plugins --with-compat-matrix / --compat-check。"""
from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cai_agent.__main__ import main
from cai_agent.config import Settings
from cai_agent.exporter import build_ecc_home_sync_drift_v1
from cai_agent.plugin_registry import (
    build_plugin_compat_matrix,
    build_plugin_compat_matrix_check_v1,
    build_plugins_home_sync_drift_v1,
    build_plugins_sync_home_plan_v1,
    run_plugins_sync_home_v1,
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


class PluginsSyncHomeTests(unittest.TestCase):
    def test_build_plugins_sync_home_plan_cursor(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = _write_min_config(root)
            (root / "rules" / "common").mkdir(parents=True)
            (root / "rules" / "common" / "a.md").write_text("x", encoding="utf-8")
            s = Settings.from_env(config_path=cfg, workspace_hint=str(root))
            plan = build_plugins_sync_home_plan_v1(s, targets=("cursor",))
            self.assertEqual(plan.get("schema_version"), "plugins_sync_home_plan_v1")
            self.assertTrue(plan.get("ok"))
            rows = plan.get("targets") or []
            self.assertEqual(len(rows), 1)
            r0 = rows[0]
            self.assertIsInstance(r0, dict)
            self.assertEqual(r0.get("target"), "cursor")
            comps = r0.get("components") or []
            rules = next((c for c in comps if isinstance(c, dict) and c.get("component") == "rules"), None)
            self.assertIsInstance(rules, dict)
            self.assertTrue(rules.get("would_copy"))
            self.assertGreater(int(rules.get("source_file_count") or 0), 0)

    def test_build_plugins_sync_home_plan_codex_manifest_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = _write_min_config(root)
            (root / "skills").mkdir()
            (root / "skills" / "b.md").write_text("y", encoding="utf-8")
            s = Settings.from_env(config_path=cfg, workspace_hint=str(root))
            plan = build_plugins_sync_home_plan_v1(s, targets=("codex",))
            self.assertTrue(plan.get("ok"))
            r0 = (plan.get("targets") or [])[0]
            self.assertEqual(r0.get("mode"), "manifest")
            for c in r0.get("components") or []:
                if isinstance(c, dict):
                    self.assertFalse(bool(c.get("would_copy")))

    def test_build_plugins_home_sync_drift_parity_with_ecc(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "rules" / "common").mkdir(parents=True)
            (root / "rules" / "common" / "a.md").write_text("x", encoding="utf-8")
            cfg = _write_min_config(root)
            s = Settings.from_env(config_path=cfg, workspace_hint=str(root))
            ecc = build_ecc_home_sync_drift_v1(s)
            ph = build_plugins_home_sync_drift_v1(s)
            self.assertEqual(ph.get("schema_version"), "plugins_home_sync_drift_v1")
            self.assertEqual(ph.get("targets_with_drift"), ecc.get("targets_with_drift"))
            self.assertEqual(len(ph.get("diffs") or []), len(ecc.get("diffs") or []))
            prev = ph.get("preview_commands")
            self.assertIsInstance(prev, list)
            self.assertTrue(prev)

    def test_plugins_sync_home_cli_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = _write_min_config(root)
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(
                        ["plugins", "--config", cfg, "sync-home", "--target", "opencode", "--json"],
                    )
            self.assertEqual(rc, 0)
            doc = json.loads(buf.getvalue().strip())
            self.assertEqual(doc.get("schema_version"), "plugins_sync_home_plan_v1")
            self.assertTrue(doc.get("ok"))

    def test_plugins_sync_home_apply_blocks_divergent_dest_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = _write_min_config(root)
            (root / "rules").mkdir()
            (root / "rules" / "a.md").write_text("source", encoding="utf-8")
            dest = root / ".opencode" / "rules"
            dest.mkdir(parents=True)
            (dest / "a.md").write_text("user edit", encoding="utf-8")
            s = Settings.from_env(config_path=cfg, workspace_hint=str(root))

            result = run_plugins_sync_home_v1(s, targets=("opencode",), apply=True)

            self.assertEqual(result.get("schema_version"), "plugins_sync_home_result_v1")
            self.assertFalse(result.get("ok"))
            self.assertEqual((dest / "a.md").read_text(encoding="utf-8"), "user edit")
            conflicts = result.get("conflicts")
            self.assertIsInstance(conflicts, list)
            self.assertEqual(conflicts[0].get("component"), "rules")

    def test_plugins_sync_home_apply_force_backs_up_and_replaces(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = _write_min_config(root)
            (root / "commands").mkdir()
            (root / "commands" / "review.md").write_text("source", encoding="utf-8")
            dest = root / ".opencode" / "commands"
            dest.mkdir(parents=True)
            (dest / "review.md").write_text("old", encoding="utf-8")
            s = Settings.from_env(config_path=cfg, workspace_hint=str(root))

            result = run_plugins_sync_home_v1(
                s,
                targets=("opencode",),
                apply=True,
                force=True,
            )

            self.assertTrue(result.get("ok"))
            self.assertEqual((dest / "review.md").read_text(encoding="utf-8"), "source")
            backups = result.get("backups")
            self.assertIsInstance(backups, list)
            self.assertEqual(len(backups), 1)
            backup_path = Path(str(backups[0].get("backup_path")))
            self.assertTrue(backup_path.is_dir())
            self.assertEqual((backup_path / "review.md").read_text(encoding="utf-8"), "old")
            self.assertTrue((root / ".opencode" / "cai-export-manifest.json").is_file())

    def test_plugins_sync_home_apply_cli_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = _write_min_config(root)
            (root / "skills").mkdir()
            (root / "skills" / "s.md").write_text("skill", encoding="utf-8")
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "plugins",
                            "--config",
                            cfg,
                            "sync-home",
                            "--target",
                            "opencode",
                            "--apply",
                            "--json",
                        ],
                    )
            self.assertEqual(rc, 0)
            doc = json.loads(buf.getvalue().strip())
            self.assertEqual(doc.get("schema_version"), "plugins_sync_home_result_v1")
            self.assertFalse(doc.get("dry_run"))
            self.assertTrue((root / ".opencode" / "skills" / "s.md").is_file())


class PluginCompatMatrixSnapshotTests(unittest.TestCase):
    def test_checked_in_snapshot_matches_generator(self) -> None:
        root = Path(__file__).resolve().parents[2]
        snapshot = root / "docs" / "schema" / "plugin_compat_matrix_v1.snapshot.json"
        self.assertTrue(snapshot.is_file())
        doc = json.loads(snapshot.read_text(encoding="utf-8"))
        self.assertEqual(doc.get("schema_version"), "plugin_compat_matrix_snapshot_v1")
        self.assertEqual(doc.get("matrix_schema_version"), "plugin_compat_matrix_v1")
        self.assertEqual(doc.get("check_schema_version"), "plugin_compat_matrix_check_v1")
        self.assertTrue(doc.get("ok"))

        proc = subprocess.run(
            [sys.executable, "scripts/gen_plugin_compat_snapshot.py", "--check"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
