from __future__ import annotations

from cai_agent.model_routing import (
    ModelsProfileRoute,
    build_models_route_wizard_v1,
    first_matching_profile_route,
)


def test_route_match_phase_filters() -> None:
    routes = (
        ModelsProfileRoute(
            use_profile="explore-p",
            match_task_kind=None,
            match_tokens_gt=None,
            match_phase="explore",
        ),
        ModelsProfileRoute(
            use_profile="impl-p",
            match_task_kind=None,
            match_tokens_gt=None,
            match_phase="implement|review",
        ),
    )
    assert (
        first_matching_profile_route(
            routes,
            goal="x",
            last_prompt_tokens=0,
            conversation_phase="explore",
        ).use_profile
        == "explore-p"
    )
    hit = first_matching_profile_route(
        routes,
        goal="x",
        last_prompt_tokens=0,
        conversation_phase="implement",
    )
    assert hit is not None and hit.use_profile == "impl-p"


def test_route_wizard_snippet() -> None:
    doc = build_models_route_wizard_v1(
        use_profile="local",
        match_phase="explore",
        match_task_kind="refactor",
        match_tokens_gt=1000,
    )
    assert "match_phase" in doc.get("toml_append", "")
    assert doc.get("schema_version") == "models_route_wizard_v1"
