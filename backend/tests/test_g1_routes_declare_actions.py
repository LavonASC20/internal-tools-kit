"""G1: every route except health, /api/auth/*, /api/me and /api/users declares a policy action."""

import pytest
from fastapi.routing import APIRoute
from starlette.routing import BaseRoute

from core import policy
from tests import discover


@pytest.mark.parametrize("route", discover.api_routes(), ids=lambda r: r.path)
def test_route_declares_a_policy_action(route: APIRoute) -> None:
    if discover.may_omit_action(route):
        return
    action = policy.route_action(route)
    assert action is not None, f"{sorted(route.methods)} {route.path} declares no policy action"
    assert (
        action in policy.all_actions()
    ), f"{route.path} declares {action!r}, which no permissions.py or core module grants"


@pytest.mark.parametrize("route", discover.other_routes(), ids=lambda r: str(getattr(r, "path", r)))
def test_only_framework_docs_bypass_the_policy_router(route: BaseRoute) -> None:
    """A raw Starlette route or mount cannot declare an action, so only FastAPI's docs may exist."""
    path = getattr(route, "path", None)
    assert path in discover.framework_paths(), f"{route!r} is not an API route and has no action"


def test_the_exemption_covers_only_core_routes() -> None:
    """A tool route under /api/auth/ (or at /api/me, ...) is not exempt."""
    for route in discover.api_routes():
        if discover.is_unguarded_path(route.path) and not discover.is_core_route(route):
            assert policy.route_action(route) is not None, route.path


def test_every_discovered_tool_is_mounted() -> None:
    mounted = {r.endpoint for r in discover.api_routes()}
    for name, routes in discover.tool_routes().items():
        missing = [r.path for r in routes if r.endpoint not in mounted]
        assert not missing, f"tool {name} routes are not mounted: {missing}"
