from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
RUNBOOK = DOCS / "MODEL_ONBOARDING_RUNBOOK.zh-CN.md"


def test_model_onboarding_runbook_is_discoverable_from_docs_entrypoints() -> None:
    assert RUNBOOK.is_file()
    for rel in ("README.zh-CN.md", "README.md", "ONBOARDING.zh-CN.md", "ONBOARDING.md"):
        text = (DOCS / rel).read_text(encoding="utf-8")
        assert "MODEL_ONBOARDING_RUNBOOK.zh-CN.md" in text


def test_model_onboarding_runbook_covers_model_p0_command_chain() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    for required in (
        "cai-agent models onboarding",
        "models list --providers --json",
        "models capabilities",
        "models ping",
        "--chat-smoke",
        "models use",
        "models routing-test",
        "auto_switch=false",
    ):
        assert required in text
