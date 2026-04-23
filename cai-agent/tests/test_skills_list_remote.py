from __future__ import annotations

from pathlib import Path

from cai_agent.skills import list_remote_skills_registry_index


def test_list_remote_skills_registry_index(monkeypatch, tmp_path: Path) -> None:
    def fake(url: str, *, timeout_sec: float = 30.0) -> dict:
        return {
            "schema_version": "skills_hub_manifest_v2",
            "entries": [{"name": "a", "path": "skills/a.md", "size_bytes": 3}],
        }

    monkeypatch.setattr("cai_agent.skills.fetch_remote_skills_manifest", fake)
    doc = list_remote_skills_registry_index("https://example.invalid/manifest.json")
    assert doc.get("schema_version") == "skills_hub_list_remote_v1"
    assert doc.get("count") == 1
    assert (doc.get("entries") or [{}])[0].get("name") == "a"

    doc2 = list_remote_skills_registry_index(
        "https://example.invalid/m2.json",
        sync_mirror=True,
        mirror_cwd=tmp_path,
    )
    assert "mirror_path" in doc2
    mp = Path(doc2["mirror_path"])
    assert mp.is_file()
