"""gateway maps summarize 与绑定可选元数据。"""
from __future__ import annotations

import json
from pathlib import Path

from cai_agent.gateway_discord import discord_bind, discord_list_bindings
from cai_agent.gateway_maps import parse_workspace_roots, summarize_gateway_maps
from cai_agent.gateway_slack import slack_bind, slack_list_bindings
from cai_agent.gateway_teams import teams_bind


def test_parse_workspace_roots_dedupes(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    roots = parse_workspace_roots(
        append_roots=[str(a), str(b), str(a)],
        workspaces_file=None,
        single_workspace=None,
        fallback_workspace=tmp_path,
    )
    assert len(roots) == 2


def test_parse_workspace_roots_single_w() -> None:
    roots = parse_workspace_roots(
        append_roots=None,
        workspaces_file=None,
        single_workspace=".",
        fallback_workspace=Path("/nonexistent"),
    )
    assert len(roots) == 1
    assert roots[0] == Path(".").resolve()


def test_summarize_two_workspaces(tmp_path: Path) -> None:
    w1 = tmp_path / "w1"
    w2 = tmp_path / "w2"
    w1.mkdir()
    w2.mkdir()
    discord_bind(w1, "CH1", "s1.json", guild_id="G9", label="dev")
    teams_bind(w1, "CONV1", "t1.json", tenant_id="TENANT", label="triage")
    slack_bind(w2, "C01", "s2.json", team_id="T1", label="ops")

    out = summarize_gateway_maps([w1.resolve(), w2.resolve()])
    assert out["schema_version"] == "gateway_maps_summarize_v1"
    assert len(out["workspaces"]) == 2
    fed = out.get("federation") or {}
    assert fed.get("schema_version") == "gateway_workspace_federation_v1"
    assert fed.get("workspaces_count") == 2
    assert int((fed.get("summary") or {}).get("bindings_count") or 0) >= 3
    d0 = out["workspaces"][0]["discord"]["bindings"][0]
    assert d0.get("guild_id") == "G9"
    assert d0.get("label") == "dev"
    t0 = out["workspaces"][0]["teams"]["bindings"][0]
    assert t0.get("tenant_id") == "TENANT"
    assert t0.get("label") == "triage"
    s1 = out["workspaces"][1]["slack"]["bindings"][0]
    assert s1.get("team_id") == "T1"


def test_workspaces_file(tmp_path: Path) -> None:
    w1 = tmp_path / "a"
    w1.mkdir()
    lst = tmp_path / "roots.txt"
    lst.write_text(f"{w1}\n# skip\n", encoding="utf-8")
    roots = parse_workspace_roots(
        append_roots=None,
        workspaces_file=str(lst),
        single_workspace=None,
        fallback_workspace=tmp_path,
    )
    assert roots == [w1.resolve()]


def test_discord_bind_returns_binding_row(tmp_path: Path) -> None:
    r = discord_bind(tmp_path, "99", "x.json", label="L")
    assert r["binding"].get("label") == "L"
    lst = discord_list_bindings(tmp_path)
    assert lst["bindings"]["99"]["label"] == "L"
