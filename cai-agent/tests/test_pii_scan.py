"""Tests for §22: PII/敏感信息专项扫描 (run_pii_scan)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cai_agent.security_scan import run_pii_scan

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
    )


# ---------------------------------------------------------------------------
# 单元测试：run_pii_scan API
# ---------------------------------------------------------------------------


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_pii_scan_credit_card_detected(tmp_path: Path) -> None:
    _write(tmp_path, "session.json", '{"answer": "card 4111111111111111 used"}')
    result = run_pii_scan(tmp_path, rule_flags={"credit_card": True})
    assert result["schema_version"] == "pii_scan_result_v1"
    assert result["findings_count"] >= 1
    rules = [f["rule"] for f in result["findings"]]
    assert "credit_card" in rules


def test_pii_scan_cn_phone_detected(tmp_path: Path) -> None:
    _write(tmp_path, "log.txt", "用户联系人：13912345678，请处理")
    result = run_pii_scan(tmp_path, rule_flags={"cn_phone": True})
    assert result["findings_count"] >= 1
    assert any(f["rule"] == "cn_phone" for f in result["findings"])


def test_pii_scan_jwt_detected(tmp_path: Path) -> None:
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    _write(tmp_path, "prompt.json", f'{{"token": "{jwt}"}}')
    result = run_pii_scan(tmp_path, rule_flags={"jwt_token": True})
    assert result["findings_count"] >= 1
    assert any(f["rule"] == "jwt_token" for f in result["findings"])


def test_pii_scan_email_off_by_default(tmp_path: Path) -> None:
    _write(tmp_path, "notes.txt", "Contact: user@example.com for help")
    result = run_pii_scan(tmp_path)  # email off by default
    email_hits = [f for f in result["findings"] if f["rule"] == "email_address"]
    assert email_hits == []


def test_pii_scan_email_on_when_enabled(tmp_path: Path) -> None:
    _write(tmp_path, "notes.txt", "Contact: user@example.com for help")
    result = run_pii_scan(tmp_path, rule_flags={"email_address": True})
    assert any(f["rule"] == "email_address" for f in result["findings"])


def test_pii_scan_non_pii_ext_ignored(tmp_path: Path) -> None:
    """Python 源码文件不在 PII 扫描范围内。"""
    _write(tmp_path, "code.py", "card = '4111111111111111'")
    result = run_pii_scan(tmp_path, rule_flags={"credit_card": True})
    assert result["findings_count"] == 0


def test_pii_scan_ok_field(tmp_path: Path) -> None:
    _write(tmp_path, "clean.json", '{"status": "ok"}')
    result = run_pii_scan(tmp_path)
    assert result["ok"] is True
    assert result["high_count"] == 0


def test_pii_scan_single_file(tmp_path: Path) -> None:
    p = _write(tmp_path, "data.json", '{"cc": "4111111111111111"}')
    result = run_pii_scan(p, rule_flags={"credit_card": True})
    assert result["findings_count"] >= 1


# ---------------------------------------------------------------------------
# CLI 集成测试
# ---------------------------------------------------------------------------


def test_pii_scan_cli_json(tmp_path: Path) -> None:
    _write(tmp_path, "session.json", '{"card": "4111111111111111"}')
    result = _cli("pii-scan", str(tmp_path), "--json")
    assert result.returncode == 0
    out = json.loads(result.stdout)
    assert out["schema_version"] == "pii_scan_result_v1"
    assert out["findings_count"] >= 1


def test_pii_scan_cli_fail_on_high(tmp_path: Path) -> None:
    _write(tmp_path, "data.json", '{"cc": "4111111111111111"}')
    result = _cli("pii-scan", str(tmp_path), "--fail-on-high")
    assert result.returncode == 2


def test_pii_scan_cli_no_findings(tmp_path: Path) -> None:
    _write(tmp_path, "clean.json", '{"status": "pass"}')
    result = _cli("pii-scan", str(tmp_path), "--json")
    assert result.returncode == 0
    out = json.loads(result.stdout)
    assert out["ok"] is True
