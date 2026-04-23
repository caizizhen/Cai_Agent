"""Parse ``[[models.route]]`` tables."""

from __future__ import annotations

from cai_agent.model_routing import (
    ModelsProfileRoute,
    first_matching_profile_route,
    parse_models_profile_routes,
)


def test_parse_models_profile_routes() -> None:
    fd = {
        "models": {
            "route": [
                {"match_task_kind": "refactor", "use_profile": "p-a"},
                {"match_tokens_gt": 9000, "profile": "p-b"},
            ],
        },
    }
    rows = parse_models_profile_routes(fd)
    assert len(rows) == 2
    assert rows[0] == ModelsProfileRoute(
        use_profile="p-a",
        match_task_kind="refactor",
        match_tokens_gt=None,
    )
    assert rows[1].use_profile == "p-b"
    assert rows[1].match_tokens_gt == 9000


def test_first_matching_profile_route_order() -> None:
    routes = (
        ModelsProfileRoute("first", "abc", None),
        ModelsProfileRoute("second", "abc", None),
    )
    g = first_matching_profile_route(routes, goal="xx abc yy", last_prompt_tokens=0)
    assert g is not None and g.use_profile == "first"
