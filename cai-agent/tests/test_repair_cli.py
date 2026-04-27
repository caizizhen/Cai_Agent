from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cai_agent.__main__ import main


def test_repair_dry_run_json_reports_needed_actions(tmp_path: Path) -> None:
    buf = io.StringIO()
    with patch("cai_agent.__main__.os.getcwd", return_value=str(tmp_path)):
        with redirect_stdout(buf):
            rc = main(["repair", "--workspace", str(tmp_path), "--dry-run", "--json"])
    assert rc == 0
    payload = json.loads(buf.getvalue().strip())
    assert payload.get("schema_version") == "repair_plan_v1"
    summary = payload.get("summary") or {}
    assert int(summary.get("actions_needed") or 0) >= 3
    actions = payload.get("actions") or []
    assert any(a.get("id") == "create_config_from_template" for a in actions)
    assert any(a.get("id") == "create_commands_dir" for a in actions)
    assert any(a.get("id") == "create_hooks_json_minimal" for a in actions)
    assert isinstance(payload.get("ecc_sync_commands"), list)
    assert payload.get("ecc_sync_commands")
    assert isinstance(payload.get("plugins_sync_home_preview_commands"), list)
    assert payload.get("plugins_sync_home_preview_commands")
    assert isinstance(payload.get("ecc_pack_repair_ok"), bool)
    assert isinstance(payload.get("ecc_pack_repair_suggestions"), list)
    assert not (tmp_path / "cai-agent.toml").exists()


def test_repair_apply_json_creates_minimal_install_surface(tmp_path: Path) -> None:
    buf = io.StringIO()
    with patch("cai_agent.__main__.os.getcwd", return_value=str(tmp_path)):
        with redirect_stdout(buf):
            rc = main(["repair", "--workspace", str(tmp_path), "--apply", "--json"])
    assert rc == 0
    payload = json.loads(buf.getvalue().strip())
    assert payload.get("schema_version") == "repair_result_v1"
    assert payload.get("ok") is True
    assert (tmp_path / ".cai").is_dir()
    assert (tmp_path / ".cai" / "gateway").is_dir()
    assert (tmp_path / "commands").is_dir()
    assert (tmp_path / "skills").is_dir()
    assert (tmp_path / "rules" / "common").is_dir()
    assert (tmp_path / "rules" / "python").is_dir()
    assert (tmp_path / "hooks").is_dir()
    assert (tmp_path / "hooks" / "hooks.json").is_file()
    assert (tmp_path / "cai-agent.toml").is_file()
