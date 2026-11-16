"""Feature flag use cases. Each state change is one transaction with its audit rows.

Dev and staging flags are toggled directly. A prod flag changes only through an approval request
decided by someone other than the proposer.
"""

from typing import Any

from sqlalchemy import Connection, text

from core import approvals, audit, db
from core.approvals import ApprovalKind, ApprovalRequest
from core.auth import User
from core.errors import invalid_state, not_found
from tools.feature_flags.permissions import FLAG_TOGGLE, PROD_APPROVE, PROD_PROPOSE
from tools.feature_flags.schemas import Environment, Flag, ProdProposal

TOOL = "feature_flags"

PROD: Environment = "prod"

_COLUMNS = "id, key, environment, description, enabled, pending_request_id, updated_by, updated_at"


def entity(flag_id: int) -> str:
    return f"feature_flag:{flag_id}"


def _to_flag(row: Any) -> Flag:
    return Flag.model_validate(row._asdict())


def list_flags(environment: Environment | None = None) -> list[Flag]:
    with db.connect() as conn:
        rows = conn.execute(
            text(
                f"SELECT {_COLUMNS} FROM feature_flags "
                "WHERE CAST(:environment AS text) IS NULL OR environment = :environment "
                "ORDER BY key, array_position(ARRAY['dev', 'staging', 'prod'], environment)"
            ),
            {"environment": environment},
        ).all()
    return [_to_flag(r) for r in rows]


def get_flag(flag_id: int) -> Flag:
    with db.connect() as conn:
        row = conn.execute(
            text(f"SELECT {_COLUMNS} FROM feature_flags WHERE id = :id"), {"id": flag_id}
        ).first()
    if row is None:
        raise not_found("Feature flag not found")
    return _to_flag(row)


def _lock(conn: Connection, flag_id: int) -> Flag:
    row = conn.execute(
        text(f"SELECT {_COLUMNS} FROM feature_flags WHERE id = :id FOR UPDATE"), {"id": flag_id}
    ).first()
    if row is None:
        raise not_found("Feature flag not found")
    return _to_flag(row)


def _require_change(flag: Flag, enabled: bool) -> None:
    if flag.enabled == enabled:
        state = "enabled" if enabled else "disabled"
        raise invalid_state(f"Flag {flag.key} is already {state} in {flag.environment}")


def toggle(user: User, flag_id: int, enabled: bool) -> Flag:
    """Set a dev or staging flag. Prod flags need an approved request instead."""
    with db.transaction() as conn:
        flag = _lock(conn, flag_id)
        if flag.environment == PROD:
            raise invalid_state("Prod flags change only through an approved request")
        _require_change(flag, enabled)
        updated = _set_enabled(conn, flag_id, enabled, user)
        audit.record(
            conn,
            user,
            tool=TOOL,
            action=FLAG_TOGGLE,
            entity=entity(flag_id),
            detail=_detail(flag, enabled),
        )
    return updated


def propose_prod_toggle(user: User, flag_id: int, enabled: bool, reason: str) -> ProdProposal:
    """Open an approval request to set a prod flag. The flag is unchanged until approval."""
    with db.transaction() as conn:
        flag = _lock(conn, flag_id)
        if flag.environment != PROD:
            raise invalid_state("Only prod flags need approval; toggle this one directly")
        if flag.pending_request_id is not None:
            raise invalid_state(f"Flag {flag.key} already has a pending request")
        _require_change(flag, enabled)
        request = approvals.create(
            conn,
            user=user,
            action=PROD_APPROVE,
            entity=entity(flag_id),
            payload={
                "flag_id": flag_id,
                "key": flag.key,
                "environment": flag.environment,
                "enabled": enabled,
                "reason": reason,
            },
        )
        row = conn.execute(
            text(
                "UPDATE feature_flags SET pending_request_id = :request_id "
                f"WHERE id = :id RETURNING {_COLUMNS}"
            ),
            {"request_id": request.id, "id": flag_id},
        ).one()
        audit.record(
            conn,
            user,
            tool=TOOL,
            action=PROD_PROPOSE,
            entity=entity(flag_id),
            detail={**_detail(flag, enabled), "approval_request_id": request.id},
        )
    return ProdProposal(flag=_to_flag(row), approval_request_id=request.id)


def _detail(flag: Flag, enabled: bool) -> dict[str, Any]:
    return {
        "key": flag.key,
        "environment": flag.environment,
        "from": flag.enabled,
        "to": enabled,
    }


def _set_enabled(conn: Connection, flag_id: int, enabled: bool, user: User) -> Flag:
    row = conn.execute(
        text(
            "UPDATE feature_flags SET enabled = :enabled, pending_request_id = NULL, "
            "updated_by = :user_id, updated_at = now() "
            f"WHERE id = :id RETURNING {_COLUMNS}"
        ),
        {"enabled": enabled, "user_id": user.id, "id": flag_id},
    ).one()
    return _to_flag(row)


def _pending_flag(conn: Connection, request: ApprovalRequest) -> Flag:
    flag = _lock(conn, int(request.payload["flag_id"]))
    if flag.pending_request_id != request.id:
        raise invalid_state("Flag is not waiting on this request")
    return flag


def _apply_prod_toggle(conn: Connection, request: ApprovalRequest, decider: User) -> None:
    flag = _pending_flag(conn, request)
    enabled = bool(request.payload["enabled"])
    _set_enabled(conn, flag.id, enabled, decider)
    audit.record(
        conn,
        decider,
        tool=TOOL,
        action="flags.prod.apply",
        entity=entity(flag.id),
        detail={**_detail(flag, enabled), "approval_request_id": request.id},
        authorized_by=request.action,
    )


def _release_prod_flag(conn: Connection, request: ApprovalRequest, decider: User) -> None:
    flag = _pending_flag(conn, request)
    conn.execute(
        text("UPDATE feature_flags SET pending_request_id = NULL WHERE id = :id"), {"id": flag.id}
    )
    audit.record(
        conn,
        decider,
        tool=TOOL,
        action="flags.prod.return",
        entity=entity(flag.id),
        detail={
            "key": flag.key,
            "environment": flag.environment,
            "approval_request_id": request.id,
        },
        authorized_by=request.action,
    )


approvals.register(
    ApprovalKind(
        tool=TOOL,
        action=PROD_APPROVE,
        propose_action=PROD_PROPOSE,
        on_approve=_apply_prod_toggle,
        on_reject=_release_prod_flag,
    )
)
