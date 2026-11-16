"""Stub login behind an interface where OIDC would go, plus the signed session cookie."""

import hashlib
import hmac
import logging
import os
import secrets
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from fastapi import Request, Response
from sqlalchemy import Connection, text

from core import db
from core.errors import unauthenticated

logger = logging.getLogger(__name__)

COOKIE_NAME = "itk_session"
SESSION_TTL_SECONDS = 12 * 60 * 60


@dataclass(frozen=True)
class User:
    id: str
    name: str
    roles: frozenset[str]


class IdentityProvider(Protocol):
    """Turns login credentials into a user id, or None. An OIDC provider would implement this."""

    def authenticate(self, credentials: Mapping[str, Any]) -> str | None: ...


class StubIdentityProvider:
    """Prototype only: anyone may log in as any seeded user by id."""

    def authenticate(self, credentials: Mapping[str, Any]) -> str | None:
        user_id = credentials.get("user_id")
        if not isinstance(user_id, str):
            return None
        with db.connect() as conn:
            return user_id if load_user(conn, user_id) else None


identity_provider: IdentityProvider = StubIdentityProvider()

_process_secret = secrets.token_bytes(32)


def _secret() -> bytes:
    configured = os.environ.get("SESSION_SECRET")
    if configured:
        return configured.encode()
    return _process_secret


def _sign(payload: str) -> str:
    return hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()


def issue_session(user_id: str, now: float | None = None) -> str:
    expires = int((now if now is not None else time.time()) + SESSION_TTL_SECONDS)
    payload = f"{user_id}:{expires}"
    return f"{payload}:{_sign(payload)}"


def read_session(value: str, now: float | None = None) -> str | None:
    try:
        user_id, expires, signature = value.rsplit(":", 2)
        expires_at = int(expires)
    except ValueError:
        return None
    if not hmac.compare_digest(signature, _sign(f"{user_id}:{expires}")):
        return None
    if expires_at < (now if now is not None else time.time()):
        return None
    return user_id


def set_session_cookie(response: Response, user_id: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        issue_session(user_id),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


def _row_to_user(row: Any) -> User:
    return User(id=row.id, name=row.name, roles=frozenset(row.roles))


def load_user(conn: Connection, user_id: str) -> User | None:
    row = conn.execute(
        text("SELECT id, name, roles FROM users WHERE id = :id"), {"id": user_id}
    ).first()
    return _row_to_user(row) if row else None


def list_users() -> list[User]:
    with db.connect() as conn:
        rows = conn.execute(text("SELECT id, name, roles FROM users ORDER BY name")).all()
    return [_row_to_user(r) for r in rows]


def current_user(request: Request) -> User:
    """The logged-in user, or a 401."""
    cookie = request.cookies.get(COOKIE_NAME)
    user_id = read_session(cookie) if cookie else None
    if user_id is None:
        raise unauthenticated()
    with db.connect() as conn:
        user = load_user(conn, user_id)
    if user is None:
        raise unauthenticated()
    return user
