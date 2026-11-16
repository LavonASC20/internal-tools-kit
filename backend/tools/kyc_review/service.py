"""KYC use cases. Each state change is one transaction with its audit rows."""

from typing import Any

from sqlalchemy import Connection, text

from core import approvals, audit, db
from core.approvals import ApprovalKind, ApprovalRequest
from core.auth import User
from core.errors import invalid_state, not_found
from tools.kyc_review.permissions import DECISION_APPROVE, DECISION_PROPOSE
from tools.kyc_review.schemas import CaseStatus, Decision, KycCase, Proposal

TOOL = "kyc_review"

_COLUMNS = "id, subject_name, national_id, date_of_birth, risk_flag, status"

_STATUS_FOR_DECISION: dict[str, CaseStatus] = {"clear": "cleared", "reject": "rejected"}


def entity(case_id: int) -> str:
    return f"kyc_case:{case_id}"


def _to_case(row: Any) -> KycCase:
    return KycCase(
        id=row.id,
        subject_name=row.subject_name,
        national_id=row.national_id,
        date_of_birth=row.date_of_birth.isoformat(),
        risk_flag=row.risk_flag,
        status=row.status,
    )


def list_cases(status: CaseStatus | None = None) -> list[KycCase]:
    with db.connect() as conn:
        rows = conn.execute(
            text(
                f"SELECT {_COLUMNS} FROM kyc_cases "
                "WHERE CAST(:status AS text) IS NULL OR status = :status ORDER BY id"
            ),
            {"status": status},
        ).all()
    return [_to_case(r) for r in rows]


def get_case(case_id: int) -> KycCase:
    with db.connect() as conn:
        row = conn.execute(
            text(f"SELECT {_COLUMNS} FROM kyc_cases WHERE id = :id"), {"id": case_id}
        ).first()
    if row is None:
        raise not_found("KYC case not found")
    return _to_case(row)


def propose(user: User, case_id: int, decision: Decision, rationale: str) -> Proposal:
    """Move an open case to pending_approval and open an approval request for the decision."""
    with db.transaction() as conn:
        row = conn.execute(
            text(f"SELECT {_COLUMNS} FROM kyc_cases WHERE id = :id FOR UPDATE"), {"id": case_id}
        ).first()
        if row is None:
            raise not_found("KYC case not found")
        if row.status != "open":
            raise invalid_state(f"Case is {row.status}; only open cases accept a proposal")
        request = approvals.create(
            conn,
            user=user,
            action=DECISION_APPROVE,
            entity=entity(case_id),
            payload={"case_id": case_id, "decision": decision, "rationale": rationale},
        )
        updated = _set_status(conn, case_id, "pending_approval")
        audit.record(
            conn,
            user,
            tool=TOOL,
            action=DECISION_PROPOSE,
            entity=entity(case_id),
            detail={"decision": decision, "approval_request_id": request.id},
        )
    return Proposal(case=updated, approval_request_id=request.id)


def _set_status(
    conn: Connection, case_id: int, status: CaseStatus, *, expect: CaseStatus | None = None
) -> KycCase:
    row = conn.execute(
        text(
            "UPDATE kyc_cases SET status = :status, updated_at = now() "
            "WHERE id = :id AND (CAST(:expect AS text) IS NULL OR status = :expect) "
            f"RETURNING {_COLUMNS}"
        ),
        {"status": status, "id": case_id, "expect": expect},
    ).first()
    if row is None:
        raise invalid_state("Case is not in the expected state")
    return _to_case(row)


def _apply_decision(conn: Connection, request: ApprovalRequest, decider: User) -> None:
    case_id = int(request.payload["case_id"])
    decision = str(request.payload["decision"])
    status = _STATUS_FOR_DECISION[decision]
    _set_status(conn, case_id, status, expect="pending_approval")
    audit.record(
        conn,
        decider,
        tool=TOOL,
        action="kyc.decision.apply",
        entity=entity(case_id),
        detail={"decision": decision, "status": status, "approval_request_id": request.id},
        authorized_by=request.action,
    )


def _return_to_open(conn: Connection, request: ApprovalRequest, decider: User) -> None:
    case_id = int(request.payload["case_id"])
    _set_status(conn, case_id, "open", expect="pending_approval")
    audit.record(
        conn,
        decider,
        tool=TOOL,
        action="kyc.decision.return",
        entity=entity(case_id),
        detail={"status": "open", "approval_request_id": request.id},
        authorized_by=request.action,
    )


approvals.register(
    ApprovalKind(
        tool=TOOL,
        action=DECISION_APPROVE,
        propose_action=DECISION_PROPOSE,
        on_approve=_apply_decision,
        on_reject=_return_to_open,
    )
)
