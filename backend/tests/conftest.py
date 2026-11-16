"""Guardrail fixtures. The shared database and app fixtures are in backend/conftest.py."""

import copy
import sys
import textwrap
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

import tools
from core import approvals, db, policy

ClientFor = Callable[[Iterable[str]], TestClient]


def add_user(roles: Iterable[str], user_id: str | None = None) -> str:
    """Insert a synthetic user holding exactly `roles` and return its id."""
    held = sorted(roles)
    uid = user_id or "g_" + ("_".join(held) or "norole")
    with db.transaction() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, name, roles) VALUES (:id, :id, :roles) "
                "ON CONFLICT (id) DO UPDATE SET roles = EXCLUDED.roles"
            ),
            {"id": uid, "roles": held},
        )
    return uid


def login(app: FastAPI, user_id: str) -> TestClient:
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post("/api/auth/login", json={"user_id": user_id})
    assert response.status_code == 200, response.text
    return client


@pytest.fixture
def client_with_roles(app: FastAPI) -> ClientFor:
    """`client_with_roles({"auditor"})`: a client logged in as a new user with just those roles."""

    def make(roles: Iterable[str]) -> TestClient:
        return login(app, add_user(roles))

    return make


@pytest.fixture
def policy_sandbox() -> Iterator[None]:
    """Unfreeze policy so a throwaway tool can try to register, then restore every registry."""
    saved = (
        copy.deepcopy(policy._grants),
        dict(policy._namespace_owners),
        dict(policy._registered),
        policy._frozen,
        dict(approvals._kinds),
    )
    policy._frozen = False
    yield
    grants, owners, registered, frozen, kinds = saved
    policy._grants.clear()
    policy._grants.update(grants)
    policy._namespace_owners.clear()
    policy._namespace_owners.update(owners)
    policy._registered.clear()
    policy._registered.update(registered)
    policy._frozen = frozen
    approvals._kinds.clear()
    approvals._kinds.update(kinds)


ToolMaker = Callable[..., str]

EMPTY_ROUTES = "from core.policy import PolicyRouter\nrouter = PolicyRouter()\n"


@pytest.fixture
def throwaway_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, policy_sandbox: None
) -> Iterator[ToolMaker]:
    """Write a tool package outside the repo that `main` discovers like any other tool.

    `throwaway_tool("probe", permissions="...", routes="...")` returns the tool name. Files not
    given get a minimal valid default. The package and its registrations are removed afterwards.
    """
    monkeypatch.setattr(tools, "__path__", [*tools.__path__, str(tmp_path)])
    names: list[str] = []

    def make(name: str, **files: str) -> str:
        package = tmp_path / name
        package.mkdir()
        files.setdefault("__init__", "")
        files.setdefault(
            "permissions", f'NAMESPACE = "{name}"\nPERMISSIONS = {{"{name}.item.read": {{"r"}}}}\n'
        )
        files.setdefault("routes", EMPTY_ROUTES)
        for module, source in files.items():
            (package / f"{module}.py").write_text(textwrap.dedent(source))
        names.append(name)
        return name

    yield make
    for name in names:
        package_name = f"tools.{name}"
        for module in [m for m in sys.modules if m.split(".")[:2] == package_name.split(".")]:
            del sys.modules[module]


def snapshot_tables() -> dict[str, list[Any]]:
    """Every row of every table, for checking that nothing changed."""
    with db.connect() as conn:
        tables = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY table_name"
            )
        ).scalars()
        return {
            t: sorted(conn.execute(text(f'SELECT row_to_json(x)::text FROM "{t}" x')).scalars())
            for t in list(tables)
        }


def audit_count() -> int:
    with db.connect() as conn:
        return int(conn.execute(text("SELECT count(*) FROM audit_events")).scalar_one())
