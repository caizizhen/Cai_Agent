from __future__ import annotations

import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from cai_agent.config import Settings
from cai_agent.hook_runtime import (
    enabled_hook_ids,
    resolve_hooks_json_path,
    run_project_hooks,
)


def _write_hooks(root: Path, hooks: list[dict]) -> None:
    d = root / "hooks"
    d.mkdir(parents=True, exist_ok=True)
    (d / "hooks.json").write_text(
        json.dumps({"version": 1, "hooks": hooks}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _settings_for_root(root: Path, **kwargs: object) -> Settings:
    cfg = root / "cai-agent.toml"
    cfg.write_text("[llm]\nbase_url = \"http://x/v1\"\nmodel = \"m\"\napi_key = \"k\"\n", encoding="utf-8")
    s = Settings.from_env(config_path=str(cfg))
    for k, v in kwargs.items():
        s = replace(s, **{str(k): v})
    return s


class HookRuntimeTests(unittest.TestCase):
    def test_resolve_hooks_prefers_hooks_over_dot_cai(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            d1 = root / "hooks"
            d1.mkdir(parents=True, exist_ok=True)
            d2 = root / ".cai" / "hooks"
            d2.mkdir(parents=True, exist_ok=True)
            (d2 / "hooks.json").write_text(
                json.dumps({"version": 1, "hooks": []}, ensure_ascii=False),
                encoding="utf-8",
            )
            (d1 / "hooks.json").write_text(
                json.dumps({"version": 1, "hooks": []}, ensure_ascii=False),
                encoding="utf-8",
            )
            cfg = root / "cai-agent.toml"
            cfg.write_text("[llm]\nbase_url = \"http://x/v1\"\nmodel = \"m\"\napi_key = \"k\"\n", encoding="utf-8")
            s = Settings.from_env(config_path=str(cfg))
            p = resolve_hooks_json_path(s)
            self.assertIsNotNone(p)
            assert p is not None
            self.assertEqual(p.resolve(), (d1 / "hooks.json").resolve())

    def test_disabled_id_removed_from_enabled_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_hooks(
                root,
                [
                    {
                        "id": "a",
                        "event": "workflow_start",
                        "enabled": True,
                    },
                    {
                        "id": "b",
                        "event": "workflow_start",
                        "enabled": True,
                    },
                ],
            )
            s = _settings_for_root(root, hooks_disabled_ids=("b",))
            ids = enabled_hook_ids(s, "workflow_start")
            self.assertEqual(ids, ["a"])

    def test_minimal_profile_skips_command_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_hooks(
                root,
                [
                    {
                        "id": "run-echo",
                        "event": "observe_start",
                        "enabled": True,
                        "command": [sys.executable, "-c", "print(1)"],
                    },
                ],
            )
            s = _settings_for_root(root, hooks_profile="minimal")
            out = run_project_hooks(s, "observe_start", {})
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0].get("status"), "skipped")

    def test_standard_runs_echo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_hooks(
                root,
                [
                    {
                        "id": "run-echo",
                        "event": "observe_start",
                        "enabled": True,
                        "command": [sys.executable, "-c", "print(1)"],
                    },
                ],
            )
            s = _settings_for_root(root, hooks_profile="standard", hooks_timeout_sec=10.0)
            out = run_project_hooks(s, "observe_start", {"x": 1})
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0].get("status"), "ok")

    def test_blocks_rm_rf_pattern(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_hooks(
                root,
                [
                    {
                        "id": "bad",
                        "event": "observe_start",
                        "enabled": True,
                        "command": [sys.executable, "-c", "rm -rf /"],
                    },
                ],
            )
            s = _settings_for_root(root, hooks_profile="standard")
            out = run_project_hooks(s, "observe_start", {})
            self.assertEqual(out[0].get("status"), "blocked")


if __name__ == "__main__":
    unittest.main()
