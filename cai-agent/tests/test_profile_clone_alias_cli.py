"""HM-N01: models clone / clone-all / alias 与 doctor profile_home_migration 机读字段。"""
from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from cai_agent.__main__ import main


class ProfileCloneAliasCli(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cfg = self.root / "cai-agent.toml"
        ws_toml = str(self.root.resolve()).replace("\\", "\\\\")
        self.cfg.write_text(
            f'[agent]\nworkspace = "{ws_toml}"\n\n'
            '[llm]\nbase_url = "http://localhost:1234/v1"\nmodel = "legacy"\napi_key = "lm-studio"\n',
            encoding="utf-8",
        )
        self._prev: dict[str, str | None] = {}
        for var in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "LM_API_KEY", "CAI_ACTIVE_MODEL"):
            self._prev[var] = os.environ.get(var)
            os.environ.pop(var, None)

    def tearDown(self) -> None:
        for k, v in self._prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _run(self, *argv: str) -> tuple[int, str]:
        out_b = io.StringIO()
        err_b = io.StringIO()
        with redirect_stdout(out_b), redirect_stderr(err_b):
            rc = main(list(argv))
        return rc, out_b.getvalue() + err_b.getvalue()

    def test_clone_dry_run_json(self) -> None:
        rc, _ = self._run(
            "models",
            "--config",
            str(self.cfg),
            "add",
            "--id",
            "p1",
            "--preset",
            "lmstudio",
            "--model",
            "m1",
            "--set-active",
        )
        self.assertEqual(rc, 0)
        home = self.root / ".cai" / "profiles" / "p1" / "sessions"
        home.mkdir(parents=True)
        (home / "x.txt").write_text("a", encoding="utf-8")
        rc, out = self._run(
            "models",
            "--config",
            str(self.cfg),
            "clone",
            "p1",
            "p1copy",
            "--dry-run",
            "--json",
        )
        self.assertEqual(rc, 0)
        doc = json.loads(out.strip())
        self.assertEqual(doc.get("schema_version"), "models_clone_plan_v1")
        self.assertEqual(doc.get("source_profile_id"), "p1")
        self.assertEqual(doc.get("dest_profile_id"), "p1copy")
        ph = doc.get("profile_home") or {}
        self.assertEqual(ph.get("schema_version"), "profile_home_clone_result_v1")
        self.assertTrue(ph.get("would_copytree"))

    def test_clone_conflict_dest_profile_exists(self) -> None:
        rc, _ = self._run(
            "models",
            "--config",
            str(self.cfg),
            "add",
            "--id",
            "a1",
            "--preset",
            "lmstudio",
            "--model",
            "m1",
        )
        self.assertEqual(rc, 0)
        rc, _ = self._run(
            "models",
            "--config",
            str(self.cfg),
            "add",
            "--id",
            "a2",
            "--preset",
            "lmstudio",
            "--model",
            "m2",
        )
        self.assertEqual(rc, 0)
        rc, combined = self._run(
            "models",
            "--config",
            str(self.cfg),
            "clone",
            "a1",
            "a2",
            "--dry-run",
        )
        self.assertEqual(rc, 2)
        self.assertIn("已存在", combined)

    def test_clone_then_home_copied(self) -> None:
        rc, _ = self._run(
            "models",
            "--config",
            str(self.cfg),
            "add",
            "--id",
            "srcp",
            "--preset",
            "lmstudio",
            "--model",
            "m1",
        )
        self.assertEqual(rc, 0)
        src_sessions = self.root / ".cai" / "profiles" / "srcp" / "memory"
        src_sessions.mkdir(parents=True)
        marker = src_sessions / "marker.txt"
        marker.write_text("ok", encoding="utf-8")
        rc, out = self._run(
            "models",
            "--config",
            str(self.cfg),
            "clone",
            "srcp",
            "dstp",
        )
        self.assertEqual(rc, 0)
        self.assertIn("profile_home:", out)
        dst_marker = self.root / ".cai" / "profiles" / "dstp" / "memory" / "marker.txt"
        self.assertTrue(dst_marker.is_file())
        self.assertEqual(dst_marker.read_text(encoding="utf-8"), "ok")

    def test_clone_all_suffix_dry_run(self) -> None:
        rc, _ = self._run(
            "models",
            "--config",
            str(self.cfg),
            "add",
            "--id",
            "x1",
            "--preset",
            "lmstudio",
            "--model",
            "m1",
        )
        self.assertEqual(rc, 0)
        rc, _ = self._run(
            "models",
            "--config",
            str(self.cfg),
            "add",
            "--id",
            "x2",
            "--preset",
            "lmstudio",
            "--model",
            "m2",
        )
        self.assertEqual(rc, 0)
        rc, out = self._run(
            "models",
            "--config",
            str(self.cfg),
            "clone-all",
            "--suffix=-bak",
            "--dry-run",
            "--json",
        )
        self.assertEqual(rc, 0)
        doc = json.loads(out.strip())
        self.assertEqual(doc.get("schema_version"), "models_clone_all_plan_v1")
        self.assertEqual(sorted(doc.get("would_add_profiles") or []), ["x1-bak", "x2-bak"])

    def test_alias_json(self) -> None:
        rc, _ = self._run(
            "models",
            "--config",
            str(self.cfg),
            "add",
            "--id",
            "ap",
            "--preset",
            "lmstudio",
            "--model",
            "m1",
        )
        self.assertEqual(rc, 0)
        rc, out = self._run(
            "models",
            "--config",
            str(self.cfg),
            "alias",
            "ap",
            "--json",
        )
        self.assertEqual(rc, 0)
        doc = json.loads(out.strip())
        self.assertEqual(doc.get("schema_version"), "models_alias_v1")
        self.assertEqual(doc.get("profile_id"), "ap")
        pos = doc.get("posix_shell") or {}
        self.assertIn("models use", pos.get("cd_models_use", ""))
        self.assertIn("cd ", pos.get("cd_models_use", ""))

    def test_doctor_json_has_profile_home_migration(self) -> None:
        (self.root / ".cai" / "profiles" / "orphan").mkdir(parents=True)
        rc, out = self._run(
            "doctor",
            "--config",
            str(self.cfg),
            "--json",
        )
        self.assertEqual(rc, 0)
        pl = json.loads(out.strip())
        mig = pl.get("profile_home_migration") or {}
        self.assertEqual(mig.get("schema_version"), "profile_home_migration_diag_v1")
        orphans = mig.get("orphan_profile_dirs") or []
        self.assertIn("orphan", orphans)
