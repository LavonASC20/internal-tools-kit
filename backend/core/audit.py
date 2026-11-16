"""Append-only audit trail. `record` runs inside the caller's transaction."""

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Connection, text

from core import masking, policy
from core.auth import User

AUDIT_READ = "audit.read"

# SPEC section 6 grants audit.read to auditor. The route is core's, so the grant lives here and
# no tool can grant it.
policy.register_permissions(policy.CORE, "audit", {AUDIT_READ: {"auditor"}})


class AuditEvent(BaseModel):
    id: int
    at: datetime
    actor: str
    role: str
    tool: str
    action: str
    entity: str
    detail: dict[str, Any]


def _pii_keys(detail: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(detail, Mapping):
        for key, value in detail.items():
            if key in masking.pii_field_names():
                found.add(str(key))
            found |= _pii_keys(value)
    elif isinstance(detail, list):
        for item in detail:
            found |= _pii_keys(item)
    return found


def record(
    conn: Connection,
    actor: User,
    *,
    tool: str,
    action: str,
    entity: str,
    detail: Mapping[str, Any] | None = None,
    authorized_by: str | None = None,
) -> int:
    """Write one audit row in the caller's transaction.

    `role` is the actor's roles that grant `authorized_by` (default: `action`), or all of the
    actor's roles if none do. Detail must not contain PII fields.
    """
    payload = dict(detail or {})
    leaked = _pii_keys(payload)
    if leaked:
        raise ValueError(f"audit detail must not contain PII fields: {sorted(leaked)}")
    roles = policy.granting_roles(actor, authorized_by or action) or sorted(actor.roles)
    row = conn.execute(
        text(
            "INSERT INTO audit_events (actor, role, tool, action, entity, detail) "
            "VALUES (:actor, :role, :tool, :action, :entity, CAST(:detail AS jsonb)) "
            "RETURNING id"
        ),
        {
            "actor": actor.id,
            "role": ",".join(roles),
            "tool": tool,
            "action": action,
            "entity": entity,
            "detail": json.dumps(payload),
        },
    ).one()
    return int(row.id)


def list_events(
    conn: Connection,
    *,
    tool: str | None = None,
    entity: str | None = None,
    actor: str | None = None,
    limit: int = 100,
) -> list[AuditEvent]:
    rows = conn.execute(
        text(
            "SELECT id, at, actor, role, tool, action, entity, detail FROM audit_events "
            "WHERE (CAST(:tool AS text) IS NULL OR tool = :tool) "
            "AND (CAST(:entity AS text) IS NULL OR entity = :entity) "
            "AND (CAST(:actor AS text) IS NULL OR actor = :actor) "
            "ORDER BY id DESC LIMIT :limit"
        ),
        {"tool": tool, "entity": entity, "actor": actor, "limit": limit},
    ).all()
    return [AuditEvent.model_validate(r._asdict()) for r in rows]
