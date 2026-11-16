"""Database access. Services open one transaction per state change with `transaction()`."""

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Connection, Engine, create_engine

DEFAULT_DATABASE_URL = "postgresql+psycopg://itk:itk@localhost:5432/itk"

_engine: Engine | None = None


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(database_url(), pool_pre_ping=True)
    return _engine


def reset_engine() -> None:
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None


@contextmanager
def transaction() -> Iterator[Connection]:
    """Commit on success, roll back everything (state change and audit rows) on any error."""
    with engine().begin() as conn:
        yield conn


@contextmanager
def connect() -> Iterator[Connection]:
    """Read-only work. Nothing is committed."""
    with engine().connect() as conn:
        yield conn


def execute_script(conn: Connection, sql: str) -> None:
    """Run a multi-statement SQL script verbatim (no parameter processing)."""
    cursor = conn.connection.cursor()
    try:
        cursor.execute(sql)
    finally:
        cursor.close()
