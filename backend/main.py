"""Composition root. Discovers every package under tools/ and mounts it next to the core routes.

A tool package provides:
  permissions.py  NAMESPACE = "<ns>"; PERMISSIONS = {"<ns>.<entity>.<verb>": {roles}}
  routes.py       router = core.policy.PolicyRouter(prefix="/<tool>")
  schema.sql      its tables (applied by db/seed.py)
  seed.py         optional seed(conn, rng) hook (called by db/seed.py)
"""

import importlib
import pkgutil
from dataclasses import dataclass

from fastapi import FastAPI

import tools
from core import errors, policy
from core.api import router as core_router
from core.policy import PolicyRouter

API_PREFIX = "/api"


@dataclass(frozen=True)
class Tool:
    name: str
    router: PolicyRouter


def tool_names() -> list[str]:
    return sorted(m.name for m in pkgutil.iter_modules(tools.__path__) if m.ispkg)


def load_tool(name: str) -> Tool:
    permissions = importlib.import_module(f"tools.{name}.permissions")
    policy.register_permissions(f"tools.{name}", permissions.NAMESPACE, permissions.PERMISSIONS)
    routes = importlib.import_module(f"tools.{name}.routes")
    router = getattr(routes, "router", None)
    if not isinstance(router, PolicyRouter):
        raise RuntimeError(f"tools.{name}.routes.router must be a core.policy.PolicyRouter")
    return Tool(name=name, router=router)


def discover_tools() -> list[Tool]:
    return [load_tool(name) for name in tool_names()]


def create_app() -> FastAPI:
    app = FastAPI(title="Internal Tools Kit", version="0.1.0")
    errors.install(app)
    app.include_router(core_router)
    for tool in discover_tools():
        app.include_router(tool.router, prefix=API_PREFIX)
    return app


app = create_app()
