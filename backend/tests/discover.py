"""Runtime discovery for the guardrail tests (SPEC section 9).

Everything here is read from the running app and the core registries: routes, their declared
actions, roles, tools, approval kinds and PII fields. A tool added later is covered without
editing the guardrail tests.
"""

import importlib
import types
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from types import ModuleType
from typing import Any, Union, get_args, get_origin

from fastapi import FastAPI
from fastapi.routing import APIRoute
from pydantic import BaseModel, TypeAdapter
from starlette.routing import BaseRoute

import main
from core import approvals, policy
from core.api import router as core_router
from core.approvals import ApprovalKind
from core.masking import PiiModel

APP: FastAPI = main.app

# SPEC section 9, G1: the only routes that may omit an action. They must also be core's own.
UNGUARDED_PATHS = {"/api/health", "/api/me", "/api/users"}
UNGUARDED_PREFIXES = ("/api/auth/",)

BODY_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

NO_ROLE = "<no role>"


@dataclass(frozen=True)
class Endpoint:
    """One (method, route) pair of the app."""

    method: str
    route: APIRoute

    @property
    def path(self) -> str:
        return self.route.path

    @property
    def action(self) -> str | None:
        return policy.route_action(self.route)

    @property
    def id(self) -> str:
        return f"{self.method} {self.path}"


def api_routes(app: FastAPI = APP) -> list[APIRoute]:
    return [r for r in app.routes if isinstance(r, APIRoute)]


def other_routes(app: FastAPI = APP) -> list[BaseRoute]:
    return [r for r in app.routes if not isinstance(r, APIRoute)]


def framework_paths(app: FastAPI = APP) -> set[str]:
    """FastAPI's own OpenAPI and docs pages, which are not API routes."""
    urls = {app.openapi_url, app.docs_url, app.redoc_url, app.swagger_ui_oauth2_redirect_url}
    return {u for u in urls if u}


def endpoints(app: FastAPI = APP) -> list[Endpoint]:
    return [
        Endpoint(method, route)
        for route in api_routes(app)
        for method in sorted(route.methods or ())
        if method != "HEAD"
    ]


_core_endpoints = {r.endpoint for r in core_router.routes if isinstance(r, APIRoute)}


def is_core_route(route: APIRoute) -> bool:
    return route.endpoint in _core_endpoints


def is_unguarded_path(path: str) -> bool:
    return path in UNGUARDED_PATHS or path.startswith(UNGUARDED_PREFIXES)


def may_omit_action(route: APIRoute) -> bool:
    return is_core_route(route) and is_unguarded_path(route.path)


# Tools ---------------------------------------------------------------------------------------


def tool_names() -> list[str]:
    return main.tool_names()


def tool_permissions(name: str) -> ModuleType:
    return importlib.import_module(f"tools.{name}.permissions")


def tool_namespace(name: str) -> str:
    return str(tool_permissions(name).NAMESPACE)


def tool_grants(name: str) -> dict[str, frozenset[str]]:
    grants: Mapping[str, Any] = tool_permissions(name).PERMISSIONS
    return {action: frozenset(roles) for action, roles in grants.items()}


def tool_routes() -> dict[str, list[APIRoute]]:
    return {
        tool.name: [r for r in tool.router.routes if isinstance(r, APIRoute)]
        for tool in main.discover_tools()
    }


def namespace(action: str) -> str:
    return action.split(".", 1)[0]


def core_namespaces() -> set[str]:
    spaces = {namespace(a) for a in policy.all_actions()}
    return {ns for ns in spaces if policy.namespace_owner(ns) == policy.CORE}


def approval_kinds() -> list[ApprovalKind]:
    return sorted(approvals.kinds(), key=lambda k: k.action)


# Roles ---------------------------------------------------------------------------------------


def roles() -> list[str]:
    """Every role policy knows about, plus a user with no role at all."""
    return [*sorted(policy.all_roles()), NO_ROLE]


def role_set(role: str) -> set[str]:
    return set() if role == NO_ROLE else {role}


def holds(role: str, action: str) -> bool:
    return role != NO_ROLE and role in policy.roles_for(action)


# PII -----------------------------------------------------------------------------------------


def _type_args(tp: Any) -> tuple[Any, ...]:
    return get_args(tp)


def _is_model(tp: Any) -> bool:
    return get_origin(tp) is None and isinstance(tp, type) and issubclass(tp, BaseModel)


def models_in(tp: Any, seen: set[type] | None = None) -> Iterator[type[BaseModel]]:
    """Every pydantic model reachable from a type annotation."""
    seen = set() if seen is None else seen
    if _is_model(tp):
        if tp in seen:
            return
        seen.add(tp)
        yield tp
        for field in tp.model_fields.values():
            yield from models_in(field.annotation, seen)
    for arg in _type_args(tp):
        yield from models_in(arg, seen)


def pii_models(app: FastAPI = APP) -> set[type[PiiModel]]:
    """Every model with PII fields that some route can return."""
    found: set[type[PiiModel]] = set()
    for route in api_routes(app):
        for model in models_in(route.response_model):
            if issubclass(model, PiiModel) and model.pii_fields():
                found.add(model)
    return found


def pii_actions(app: FastAPI = APP) -> set[str]:
    return {m.pii_action for m in pii_models(app)}


def collect_pii(tp: Any, data: Any, out: dict[str, set[str]]) -> None:
    """Walk `data` along its response type and record each PII value under its PII action."""
    if data is None:
        return
    if _is_model(tp):
        if not isinstance(data, dict):
            return
        pii = tp.pii_fields() if issubclass(tp, PiiModel) else frozenset()
        for name, field in tp.model_fields.items():
            keys = [k for k in (field.serialization_alias, field.alias, name) if k]
            key = next((k for k in keys if k in data), None)
            if key is None:
                continue
            if name in pii:
                if isinstance(data[key], str):
                    out.setdefault(tp.pii_action, set()).add(data[key])
            else:
                collect_pii(field.annotation, data[key], out)
        return
    origin = get_origin(tp)
    if origin in (Union, types.UnionType):
        for arg in _type_args(tp):
            collect_pii(arg, data, out)
    elif isinstance(origin, type) and issubclass(origin, Sequence) and isinstance(data, list):
        for item in data:
            for arg in _type_args(tp):
                if arg is not Ellipsis:
                    collect_pii(arg, item, out)


def string_leaves(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key)
            yield from string_leaves(item)
    elif isinstance(value, list):
        for item in value:
            yield from string_leaves(item)


# Requests ------------------------------------------------------------------------------------


def sample_path(route: APIRoute) -> str:
    """The route's path with every path parameter set to 1."""
    return route.path_format.format(**{p.name: 1 for p in route.dependant.path_params})


def _sample(schema: Mapping[str, Any], defs: Mapping[str, Any]) -> Any:
    if "$ref" in schema:
        return _sample(defs[schema["$ref"].rsplit("/", 1)[-1]], defs)
    if "const" in schema:
        return schema["const"]
    if "enum" in schema:
        return schema["enum"][0]
    if "default" in schema:
        return schema["default"]
    for key in ("anyOf", "oneOf", "allOf"):
        if key in schema:
            options = [s for s in schema[key] if s.get("type") != "null"] or schema[key]
            return _sample(options[0], defs)
    kind = schema.get("type")
    if kind == "object":
        return {k: _sample(v, defs) for k, v in schema.get("properties", {}).items()}
    if kind == "array":
        return [_sample(schema.get("items", {}), defs)] * max(int(schema.get("minItems", 1)), 1)
    if kind == "integer":
        return max(int(schema.get("minimum", 1)), 1)
    if kind == "number":
        return float(schema.get("minimum", 1))
    if kind == "boolean":
        return True
    if kind == "null":
        return None
    if kind == "string":
        fmt = schema.get("format")
        if fmt == "date":
            return "2000-01-01"
        if fmt == "date-time":
            return "2000-01-01T00:00:00Z"
        text = "sample guardrail value"
        text = text.ljust(int(schema.get("minLength", 0)), "x")
        return text[: int(schema.get("maxLength", len(text)))]
    return None


def sample_body(route: APIRoute) -> Any:
    """A request body that satisfies the route's declared body schema, or None if it has none."""
    field = route.body_field
    if field is None:
        return None
    schema = TypeAdapter(field.field_info.annotation).json_schema()
    return _sample(schema, schema.get("$defs", {}))
