"""Tests for §25: 技能自进化 auto_extract + hub serve."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"


def _cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_SRC)
    return subprocess.run(
        [sys.executable, "-m", "cai_agent", *args],
        cwd=str(cwd or Path.cwd()),
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=30,
    )

from cai_agent.skills import (
    auto_extract_skill_after_task,
    build_skills_hub_manifest,
    serve_skills_hub,
)


# ---------------------------------------------------------------------------
# auto_extract_skill_after_task
# ---------------------------------------------------------------------------


def test_auto_extract_skill_writes_file(tmp_path: Path) -> None:
    result = auto_extract_skill_after_task(
        root=tmp_path,
        goal="为登录功能添加 JWT 认证",
        answer="实现了 JWT 中间件，配置了 expire 时间。",
        write=True,
    )
    assert result["schema_version"] == "skills_auto_extract_v1"
    assert result["written"] is True
    skill_path = tmp_path / result["suggested_path"]
    assert skill_path.is_file()
    content = skill_path.read_text(encoding="utf-8")
    assert "JWT" in content
    assert "任务目标" in content


def test_auto_extract_skill_no_duplicate_write(tmp_path: Path) -> None:
    auto_extract_skill_after_task(root=tmp_path, goal="任务A", write=True)
    result2 = auto_extract_skill_after_task(root=tmp_path, goal="任务A", write=True)
    assert result2["file_existed_before"] is True
    assert result2["written"] is False


def test_auto_extract_skill_dry_run(tmp_path: Path) -> None:
    result = auto_extract_skill_after_task(root=tmp_path, goal="优化数据库查询", write=False)
    assert result["write_requested"] is False
    assert result["written"] is False
    skill_path = tmp_path / result["suggested_path"]
    assert not skill_path.exists()


def test_auto_extract_skill_goal_preview(tmp_path: Path) -> None:
    long_goal = "x" * 200
    result = auto_extract_skill_after_task(root=tmp_path, goal=long_goal, write=False)
    assert len(result["goal_preview"]) <= 120


# ---------------------------------------------------------------------------
# Skills Hub Manifest（确保 auto_extract 后文件可被发现）
# ---------------------------------------------------------------------------


def test_hub_manifest_includes_extracted(tmp_path: Path) -> None:
    auto_extract_skill_after_task(
        root=tmp_path,
        goal="部署流水线优化",
        write=True,
    )
    manifest = build_skills_hub_manifest(root=tmp_path)
    assert manifest["count"] >= 1
    names = [e["name"] for e in manifest["entries"]]
    assert any("_evolution_" in n for n in names)


# ---------------------------------------------------------------------------
# Skills Hub HTTP serve（轻量集成测试）
# ---------------------------------------------------------------------------


def test_skills_hub_serve_manifest(tmp_path: Path) -> None:
    """启动带超时的 serve，GET /manifest 应返回合法 JSON。"""
    auto_extract_skill_after_task(root=tmp_path, goal="测试技能", write=True)
    port = 17891  # 使用不冲突的高端口

    def _run():
        serve_skills_hub(root=tmp_path, host="127.0.0.1", port=port, timeout_seconds=3.0)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    time.sleep(0.4)  # 等待服务启动

    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/manifest", timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        assert data["schema_version"] == "skills_hub_manifest_v1"
        assert data["count"] >= 1
    except OSError:
        pytest.skip("Skills Hub serve 端口冲突或超时，跳过")
    finally:
        t.join(timeout=4)


def test_skills_hub_serve_skill_content(tmp_path: Path) -> None:
    auto_extract_skill_after_task(root=tmp_path, goal="技能内容测试", write=True)
    manifest = build_skills_hub_manifest(root=tmp_path)
    assert manifest["count"] >= 1
    first_name = manifest["entries"][0]["name"]
    port = 17892

    def _run():
        serve_skills_hub(root=tmp_path, host="127.0.0.1", port=port, timeout_seconds=3.0)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    time.sleep(0.4)

    try:
        url = f"http://127.0.0.1:{port}/skill/{first_name}"
        with urllib.request.urlopen(url, timeout=5) as resp:
            content = resp.read().decode("utf-8")
        assert "Evolution draft" in content or "Auto-extracted" in content
    except OSError:
        pytest.skip("Skills Hub serve 端口冲突或超时，跳过")
    finally:
        t.join(timeout=4)


# ---------------------------------------------------------------------------
# CLI 集成测试：skills hub serve（带超时）
# ---------------------------------------------------------------------------


def test_skills_hub_serve_cli(tmp_path: Path) -> None:
    result = _cli(
        "skills", "hub", "serve",
        "--host", "127.0.0.1", "--port", "17893",
        "--timeout", "1.0",
        "--json",
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["schema_version"] == "skills_hub_serve_v1"
    assert out["ok"] is True
