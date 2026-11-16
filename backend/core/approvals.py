"""One approval flow for every tool.

A tool registers an ApprovalKind with a handler. `create` opens a request; `approve` checks the
decider and runs the handler in the same transaction. The database CHECK constraint
`decided_by <> proposed_by` backs up the self-approval rule.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import Connection, text

from core import audit, policy
from core.auth import User
from core.errors import AppError, forbidden, invalid_state, not_found, self_approval

APPROVALS_READ = "approvals.read"
APPROVALS_DECIDE = "approvals.decide"

Status = Literal["pending", "approved", "rejected"]


class ApprovalRequest(BaseModel):
    id: int
    tool: str
    action: str
    entity: str
    payload: dict[str, Any]
    proposed_by: str
    status: Status
    decided_by: str | None
    comment: str | None
    created_at: datetime
    decided_at: datetime | None


Handler = Callable[[Connection, ApprovalRequest, User], None]


@dataclass(frozen=True)
class ApprovalKind:
    """`action` is what a decider must hold; `propose_action` is what a proposer must hold."""

    tool: str
    action: str
    propose_action: str
    on_approve: Handler
    on_reject: Handler | None = None


_kinds: dict[str, ApprovalKind] = {}


def register(kind: ApprovalKind) -> None:
    """Register a tool's approval kind. Both actions must be declared in one namespace owned by
    `tools.<kind.tool>`. An action has one kind: registering a different one fails."""
    owner = f"tools.{kind.tool}"
    namespaces = {a.split(".", 1)[0] for a in (kind.action, kind.propose_action)}
    if len(namespaces) != 1 or policy.namespace_owner(namespaces.pop()) != owner:
        raise RuntimeError(f"{owner}: approval actions must be in its own namespace")
    undeclared = [a for a in (kind.action, kind.propose_action) if not policy.is_declared(a)]
    if undeclared:
        raise RuntimeError(f"{owner}: approval actions {undeclared} are not declared")
    existing = _kinds.get(kind.action)
    if existing is not None:
        if existing != kind:
            raise RuntimeError(f"{kind.action} already has an approval kind ({existing.tool})")
        return
    if policy.is_frozen():
        raise RuntimeError(f"{owner}: policy is frozen; cannot register {kind.action}")
    _kinds[kind.action] = kind


def kinds() -> list[ApprovalKind]:
    return list(_kinds.values())


def _derived_grants() -> dict[str, set[str]]:
    read: set[str] = set()
    decide: set[str] = set()
    for kind in _kinds.values():
        approvers = policy.declared_roles_for(kind.action)
        read |= policy.declared_roles_for(kind.propose_action) | approvers
        decide |= approvers
    return {APPROVALS_READ: read, APPROVALS_DECIDE: decide}


policy.claim_namespace(policy.CORE, "approvals")
policy.register_derived(_derived_grants)

_COLUMNS = (
    "id, tool, action, entity, payload, proposed_by, status, decided_by, comment, "
    "created_at, decided_at"
)


def _to_request(row: Any) -> ApprovalRequest:
    return ApprovalRequest.model_validate(row._asdict())


def create(
    conn: Connection, *, user: User, action: str, entity: str, payload: dict[str, Any]
) -> ApprovalRequest:
    """Open a pending request in the caller's transaction. The caller audits the proposal."""
    kind = _kinds.get(action)
    if kind is None:
        raise RuntimeError(f"no approval kind registered for {action}")
    if not policy.allows(user, kind.propose_action):
        raise forbidden(f"You do not have permission for {kind.propose_action}")
    row = conn.execute(
        text(
            "INSERT INTO approval_requests (tool, action, entity, payload, proposed_by) "
            "VALUES (:tool, :action, :entity, CAST(:payload AS jsonb), :proposed_by) "
            f"RETURNING {_COLUMNS}"
        ),
        {
            "tool": kind.tool,
            "action": action,
            "entity": entity,
            "payload": json.dumps(payload),
            "proposed_by": user.id,
        },
    ).one()
    return _to_request(row)


def visible_actions(user: User) -> list[str]:
    return [
        k.action
        for k in _kinds.values()
        if policy.allows(user, k.action) or policy.allows(user, k.propose_action)
    ]


def list_for(conn: Connection, user: User, status: Status | None = None) -> list[ApprovalRequest]:
    """Requests of the kinds the user can propose or decide, newest first."""
    actions = visible_actions(user)
    if not actions:
        return []
    rows = conn.execute(
        text(
            f"SELECT {_COLUMNS} FROM approval_requests "
            "WHERE action = ANY(:actions) AND (CAST(:status AS text) IS NULL OR status = :status) "
            "ORDER BY id DESC"
        ),
        {"actions": actions, "status": status},
    ).all()
    return [_to_request(r) for r in rows]


def can_decide(user: User, request: ApprovalRequest) -> bool:
    return (
        request.status == "pending"
        and request.proposed_by != user.id
        and policy.allows(user, request.action)
    )


def approve(conn: Connection, user: User, request_id: int, comment: str | None) -> ApprovalRequest:
    return _decide(conn, user, request_id, comment, approved=True)


def reject(conn: Connection, user: User, request_id: int, comment: str | None) -> ApprovalRequest:
    return _decide(conn, user, request_id, comment, approved=False)


def _decide(
    conn: Connection, user: User, request_id: int, comment: str | None, *, approved: bool
) -> ApprovalRequest:
    row = conn.execute(
        text(f"SELECT {_COLUMNS} FROM approval_requests WHERE id = :id FOR UPDATE"),
        {"id": request_id},
    ).first()
    if row is None:
        raise not_found("Approval request not found")
    current = _to_request(row)
    if not policy.allows(user, current.action):
        raise forbidden(f"You do not have permission for {current.action}")
    if current.proposed_by == user.id:
        raise self_approval()
    if current.status != "pending":
        raise invalid_state(f"Approval request is already {current.status}")
    kind = _kinds.get(current.action)
    if kind is None:
        raise AppError(409, "invalid_state", "No handler is registered for this request")

    decided = _to_request(
        conn.execute(
            text(
                "UPDATE approval_requests SET status = :status, decided_by = :decided_by, "
                "comment = :comment, decided_at = now() "
                f"WHERE id = :id RETURNING {_COLUMNS}"
            ),
            {
                "status": "approved" if approved else "rejected",
                "decided_by": user.id,
                "comment": comment,
                "id": request_id,
            },
        ).one()
    )
    audit.record(
        conn,
        user,
        tool=decided.tool,
        action="approvals.approve" if approved else "approvals.reject",
        entity=decided.entity,
        detail={"approval_request_id": decided.id, "request_action": decided.action},
        authorized_by=decided.action,
    )
    handler = kind.on_approve if approved else kind.on_reject
    if handler is not None:
        handler(conn, decided, user)
    return decided
