"""Deny-by-default authorization. Every route declares exactly one action with `require`.

Actions are namespaced: `<namespace>.<entity>.<verb>`. Each namespace has one owner (a tool, or
core for `audit` and `approvals`), and only the owner may declare or grant actions in it. A tool
declares its namespace and grants in its permissions.py.
"""

import re
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from fastapi import Depends, Request
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, APIRouter
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from core import auth, masking
from core.auth import User
from core.errors import forbidden

Grants = Mapping[str, Iterable[str]]

CORE = "core"

_NAMESPACE = re.compile(r"[a-z][a-z0-9_]*")

_grants: dict[str, set[str]] = {}
_derived: list[Callable[[], Grants]] = []
_namespace_owners: dict[str, str] = {}


def claim_namespace(owner: str, namespace: str) -> None:
    """Reserve an action namespace for `owner`. Claiming another owner's namespace fails."""
    if not _NAMESPACE.fullmatch(namespace):
        raise RuntimeError(f"{owner}: invalid action namespace {namespace!r}")
    current = _namespace_owners.setdefault(namespace, owner)
    if current != owner:
        raise RuntimeError(f"{owner}: action namespace {namespace!r} belongs to {current}")


def register_permissions(owner: str, namespace: str, permissions: Grants) -> None:
    """Merge `owner`'s {action: roles} grants. Every action must be in `owner`'s namespace.

    Nothing is registered unless every action passes. Re-registering the same grants is a no-op.
    """
    claim_namespace(owner, namespace)
    foreign = sorted(a for a in permissions if not a.startswith(f"{namespace}."))
    if foreign:
        raise RuntimeError(f"{owner} may only grant {namespace}.* actions, not {foreign}")
    for action, roles in permissions.items():
        _grants.setdefault(action, set()).update(roles)


def register_derived(provider: Callable[[], Grants]) -> None:
    """Grants computed at lookup time from declared grants (used by core.approvals).

    Providers must read `declared_roles_for`, not `roles_for`, to avoid recursion.
    """
    if provider not in _derived:
        _derived.append(provider)


def declared_roles_for(action: str) -> frozenset[str]:
    """Roles granted `action` by a tool's permissions.py, ignoring derived grants."""
    return frozenset(_grants.get(action, ()))


def grants() -> dict[str, frozenset[str]]:
    merged: dict[str, set[str]] = {a: set(r) for a, r in _grants.items()}
    for provider in _derived:
        for action, roles in provider().items():
            merged.setdefault(action, set()).update(roles)
    return {a: frozenset(r) for a, r in merged.items()}


def all_actions() -> frozenset[str]:
    return frozenset(grants())


def all_roles() -> frozenset[str]:
    return frozenset(role for roles in grants().values() for role in roles)


def roles_for(action: str) -> frozenset[str]:
    return grants().get(action, frozenset())


def actions_for_roles(roles: Iterable[str]) -> frozenset[str]:
    held = set(roles)
    return frozenset(a for a, r in grants().items() if held & r)


def actions_for(user: User) -> frozenset[str]:
    return actions_for_roles(user.roles)


def allows(user: User, action: str) -> bool:
    return bool(user.roles & roles_for(action))


def granting_roles(user: User, action: str) -> list[str]:
    return sorted(user.roles & roles_for(action))


def authorize(request: Request, action: str) -> User:
    """Authenticate (401) then check the action (403). Caches the result on the request."""
    if getattr(request.state, "authorized_action", None) == action:
        return request.state.user
    user = auth.current_user(request)
    if not allows(user, action):
        raise forbidden(f"You do not have permission for {action}")
    request.state.user = user
    request.state.authorized_action = action
    return user


class ActionCheck:
    """The dependency behind `require`. Its `action` attribute is how routes are introspected."""

    def __init__(self, action: str) -> None:
        self.action = action

    def __call__(self, request: Request) -> User:
        return authorize(request, self.action)

    def __repr__(self) -> str:
        return f"ActionCheck({self.action!r})"


def require(action: str) -> Any:
    """Declare a route's action: `user: Annotated[User, require("kyc.case.read")]`."""
    return Depends(ActionCheck(action))


def _collect_actions(dependant: Dependant) -> list[str]:
    found: list[str] = []
    for dep in dependant.dependencies:
        if isinstance(dep.call, ActionCheck):
            found.append(dep.call.action)
        found.extend(_collect_actions(dep))
    return found


def route_action(route: APIRoute) -> str | None:
    """The single action a route declares, or None. More than one is a programming error."""
    actions = sorted(set(_collect_actions(route.dependant)))
    if len(actions) > 1:
        raise RuntimeError(f"{route.path} declares more than one action: {actions}")
    return actions[0] if actions else None


class PolicyRoute(APIRoute):
    """Runs the declared action's check before FastAPI reads or validates the request body, then
    serializes the response with PII revealed only for the PII actions the caller holds."""

    def __init__(self, path: str, endpoint: Callable[..., Any], **kwargs: Any) -> None:
        super().__init__(path, endpoint, **kwargs)
        masking.check_response_type(self.response_model, f"{', '.join(self.methods)} {path}")

    def get_route_handler(self) -> Callable[[Request], Any]:
        handler = super().get_route_handler()
        action = route_action(self)
        if action is None:
            return handler

        async def guarded(request: Request) -> Response:
            user = await run_in_threadpool(authorize, request, action)
            with masking.revealing(actions_for(user)):
                return await handler(request)

        return guarded


class PolicyRouter(APIRouter):
    """The router every tool uses. main.py refuses tool routers of any other type."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("route_class", PolicyRoute)
        super().__init__(**kwargs)
