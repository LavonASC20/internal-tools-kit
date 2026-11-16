"""Shared test fixtures: a dedicated test database, reseeded per test, and logged-in clients."""

import importlib.util
import os
from collections.abc import Callable, Iterator
from pathlib import Path
from types import ModuleType

import pytest

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://itk:itk@localhost:5432/itk_test"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("SESSION_SECRET", "test-only-not-a-secret")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, make_url, text  # noqa: E402

from core import db  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def _load_seed_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("itk_seed", ROOT / "db" / "seed.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


seed_module = _load_seed_module()


def _ensure_database(url: str) -> None:
    target = make_url(url)
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": target.database},
            ).first()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    finally:
        admin.dispose()


@pytest.fixture(scope="session")
def database() -> Iterator[str]:
    _ensure_database(TEST_DATABASE_URL)
    db.reset_engine()
    yield TEST_DATABASE_URL
    db.reset_engine()


@pytest.fixture
def seeded_db(database: str) -> str:
    """Fresh schema and seed data for each test."""
    seed_module.run()
    return database


@pytest.fixture
def app(seeded_db: str) -> FastAPI:
    from main import create_app

    return create_app()


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Anonymous client."""
    return TestClient(app)


@pytest.fixture
def client_for(app: FastAPI) -> Callable[[str], TestClient]:
    """`client_for("ana")` returns a client logged in as that seeded user."""

    def make(user_id: str) -> TestClient:
        c = TestClient(app)
        response = c.post("/api/auth/login", json={"user_id": user_id})
        assert response.status_code == 200, response.text
        return c

    return make
