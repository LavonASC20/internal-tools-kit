"""HTTP routes owned by core: health, auth, approvals, audit."""

from typing import Annotated, Literal

from fastapi import Depends, Query, Response
from pydantic import BaseModel, Field

from core import approvals, audit, auth, db, policy
from core.approvals import APPROVALS_DECIDE, APPROVALS_READ, ApprovalRequest
from core.audit import AUDIT_READ, AuditEvent
from core.auth import User
from core.errors import unauthenticated
from core.policy import PolicyRouter, require

router = PolicyRouter(prefix="/api")


class LoginRequest(BaseModel):
    user_id: str


class UserOut(BaseModel):
    id: str
    name: str
    roles: list[str]


class MeOut(UserOut):
    actions: list[str]


class ApprovalOut(ApprovalRequest):
    can_decide: bool


class DecisionRequest(BaseModel):
    comment: str | None = Field(default=None, max_length=2000)


def _me(user: User) -> MeOut:
    return MeOut(
        id=user.id,
        name=user.name,
        roles=sorted(user.roles),
        actions=sorted(policy.actions_for(user)),
    )


@router.get("/health", tags=["core"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/auth/login", tags=["auth"])
def login(body: LoginRequest, response: Response) -> MeOut:
    user_id = auth.identity_provider.authenticate(body.model_dump())
    if user_id is None:
        raise unauthenticated("Unknown user")
    with db.connect() as conn:
        user = auth.load_user(conn, user_id)
    if user is None:
        raise unauthenticated("Unknown user")
    auth.set_session_cookie(response, user.id)
    return _me(user)


@router.post("/auth/logout", tags=["auth"], status_code=204)
def logout(response: Response) -> None:
    auth.clear_session_cookie(response)


@router.get("/me", tags=["auth"])
def me(user: Annotated[User, Depends(auth.current_user)]) -> MeOut:
    return _me(user)


@router.get("/users", tags=["auth"])
def users() -> list[UserOut]:
    return [UserOut(id=u.id, name=u.name, roles=sorted(u.roles)) for u in auth.list_users()]


def _approval_out(user: User, request: ApprovalRequest) -> ApprovalOut:
    return ApprovalOut(**request.model_dump(), can_decide=approvals.can_decide(user, request))


@router.get("/approvals", tags=["approvals"])
def list_approvals(
    user: Annotated[User, require(APPROVALS_READ)],
    status: Literal["pending", "approved", "rejected"] | None = None,
) -> list[ApprovalOut]:
    with db.connect() as conn:
        return [_approval_out(user, r) for r in approvals.list_for(conn, user, status)]


@router.post("/approvals/{request_id}/approve", tags=["approvals"])
def approve(
    request_id: int,
    user: Annotated[User, require(APPROVALS_DECIDE)],
    body: DecisionRequest | None = None,
) -> ApprovalOut:
    with db.transaction() as conn:
        decided = approvals.approve(conn, user, request_id, body.comment if body else None)
    return _approval_out(user, decided)


@router.post("/approvals/{request_id}/reject", tags=["approvals"])
def reject(
    request_id: int,
    user: Annotated[User, require(APPROVALS_DECIDE)],
    body: DecisionRequest | None = None,
) -> ApprovalOut:
    with db.transaction() as conn:
        decided = approvals.reject(conn, user, request_id, body.comment if body else None)
    return _approval_out(user, decided)


@router.get("/audit", tags=["audit"])
def list_audit(
    user: Annotated[User, require(AUDIT_READ)],
    tool: str | None = None,
    entity: str | None = None,
    actor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[AuditEvent]:
    with db.connect() as conn:
        return audit.list_events(conn, tool=tool, entity=entity, actor=actor, limit=limit)
