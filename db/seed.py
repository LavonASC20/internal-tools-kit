"""Reset the database: drop everything, apply db/schema.sql and each tool's schema.sql, then load
synthetic seed data (core users plus each tool's optional seed.py hook).

Usage: python db/seed.py   (uses DATABASE_URL)
"""

import importlib
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import Connection, text  # noqa: E402

from core import db  # noqa: E402

RANDOM_SEED = 20261116

USERS: list[tuple[str, str, list[str]]] = [
    ("ana", "Ana", ["analyst"]),
    ("sam", "Sam", ["senior_reviewer"]),
    ("dana", "Dana", ["analyst", "senior_reviewer"]),
    ("audrey", "Audrey", ["auditor"]),
    ("eli", "Eli", ["engineer"]),
    ("lee", "Lee", ["engineer", "eng_lead"]),
]


def tool_dirs() -> list[Path]:
    tools = BACKEND / "tools"
    return sorted(p for p in tools.iterdir() if (p / "__init__.py").is_file())


def reset(conn: Connection) -> None:
    db.execute_script(
        conn, "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"
    )


def apply_schema(conn: Connection) -> None:
    db.execute_script(conn, (ROOT / "db" / "schema.sql").read_text())
    for tool in tool_dirs():
        schema = tool / "schema.sql"
        if schema.is_file():
            db.execute_script(conn, schema.read_text())


def seed_users(conn: Connection) -> None:
    for user_id, name, roles in USERS:
        conn.execute(
            text("INSERT INTO users (id, name, roles) VALUES (:id, :name, :roles)"),
            {"id": user_id, "name": name, "roles": roles},
        )


def seed_tools(conn: Connection) -> None:
    for tool in tool_dirs():
        if (tool / "seed.py").is_file():
            module = importlib.import_module(f"tools.{tool.name}.seed")
            module.seed(conn, random.Random(f"{RANDOM_SEED}:{tool.name}"))


def run() -> None:
    with db.transaction() as conn:
        reset(conn)
        apply_schema(conn)
        seed_users(conn)
        seed_tools(conn)


if __name__ == "__main__":
    run()
    print(f"Seeded {db.engine().url.render_as_string(hide_password=True)}")
