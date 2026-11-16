"""G4: UPDATE and DELETE on audit_events fail. A change that fails midway leaves no state change
and no audit row."""

import dataclasses
from typing import Any

import pytest
from fastapi import FastAPI
from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError

import main
from core import approvals, audit, db, policy
from core.approvals import ApprovalKind, ApprovalRequest
from core.auth import User
from tests import discover
from tests.conftest import ToolMaker, add_user, audit_count, login, snapshot_tables

PROBE_USER = User(id="g4_actor", name="g4_actor", roles=frozenset({"g4_role"}))


def _write_audit_row() -> int:
    add_user(PROBE_USER.roles, PROBE_USER.id)
    with db.transaction() as conn:
        return audit.record(
            conn, PROBE_USER, tool="g4", action="g4.row.write", entity="g4:1", detail={"n": 1}
        )


def _audit_row(event_id: int) -> Any:
    with db.connect() as conn:
        return conn.execute(
            text("SELECT * FROM audit_events WHERE id = :id"), {"id": event_id}
        ).one()


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE audit_events SET actor = 'someone_else' WHERE id = :id",
        "UPDATE audit_events SET detail = '{}'::jsonb WHERE id = :id",
        "DELETE FROM audit_events WHERE id = :id",
        "TRUNCATE audit_events",
    ],
    ids=["update-actor", "update-detail", "delete", "truncate"],
)
def test_audit_rows_cannot_be_changed_or_removed(statement: str, seeded_db: str) -> None:
    event_id = _write_audit_row()
    before = _audit_row(event_id)
    with pytest.raises(DBAPIError), db.transaction() as conn:
        conn.execute(text(statement), {"id": event_id})
    assert _audit_row(event_id) == before


class Midway(Exception):
    pass


def _fail_after(handler: Any) -> Any:
    def wrapped(conn: Connection, request: ApprovalRequest, user: User) -> None:
        if handler is not None:
            handler(conn, request, user)
        raise Midway("failed after the handler ran")

    return wrapped


def _open_request(kind: ApprovalKind, payload: dict[str, Any]) -> tuple[int, str]:
    proposer = add_user(policy.declared_roles_for(kind.propose_action), "g4_proposer")
    decider = add_user(policy.declared_roles_for(kind.action), "g4_decider")
    user = User(
        id=proposer,
        name=proposer,
        roles=frozenset(policy.declared_roles_for(kind.propose_action)),
    )
    with db.transaction() as conn:
        request = approvals.create(
            conn, user=user, action=kind.action, entity="g4:probe", payload=payload
        )
    return request.id, decider


def _assert_failed_without_trace(app: FastAPI, request_id: int, decider: str, path: str) -> None:
    before_audit, before = audit_count(), snapshot_tables()
    response = login(app, decider).post(f"/api/approvals/{request_id}/{path}", json={})
    assert response.status_code == 500, response.text
    assert audit_count() == before_audit, "a failed change left audit rows"
    assert snapshot_tables() == before, "a failed change left a state change"


KINDS = discover.approval_kinds()


@pytest.mark.parametrize("path", ["approve", "reject"])
@pytest.mark.parametrize("kind", KINDS, ids=[k.action for k in KINDS])
def test_a_decision_that_fails_midway_leaves_nothing(
    kind: ApprovalKind, path: str, app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Core marks the request decided and audits it, the tool's handler runs, then it fails."""
    request_id, decider = _open_request(kind, {})
    failing = dataclasses.replace(
        kind, on_approve=_fail_after(kind.on_approve), on_reject=_fail_after(kind.on_reject)
    )
    monkeypatch.setitem(approvals._kinds, kind.action, failing)
    _assert_failed_without_trace(app, request_id, decider, path)


PROBE_PERMISSIONS = """
NAMESPACE = "g4probe"
PERMISSIONS = {
    "g4probe.change.propose": {"g4_proposer_role"},
    "g4probe.change.approve": {"g4_approver_role"},
}
"""

PROBE_ROUTES = """
from sqlalchemy import text

from core import approvals, audit
from core.approvals import ApprovalKind
from core.policy import PolicyRouter

router = PolicyRouter()


def apply(conn, request, user):
    conn.execute(text("UPDATE users SET name = 'changed by g4probe'"))
    audit.record(conn, user, tool="g4probe", action="g4probe.change.apply", entity=request.entity)
    raise RuntimeError("g4probe fails after its state change and audit row")


approvals.register(
    ApprovalKind(
        tool="g4probe",
        action="g4probe.change.approve",
        propose_action="g4probe.change.propose",
        on_approve=apply,
        on_reject=apply,
    )
)
"""


@pytest.mark.parametrize("path", ["approve", "reject"])
def test_a_tool_change_that_fails_after_writing_leaves_nothing(
    path: str, seeded_db: str, throwaway_tool: ToolMaker
) -> None:
    """A throwaway tool whose handler changes state and audits before failing."""
    throwaway_tool("g4probe", permissions=PROBE_PERMISSIONS, routes=PROBE_ROUTES)
    app = main.create_app()
    kind = next(k for k in approvals.kinds() if k.tool == "g4probe")
    request_id, decider = _open_request(kind, {"n": 1})
    _assert_failed_without_trace(app, request_id, decider, path)


def test_a_failed_transaction_writes_no_audit_row(seeded_db: str) -> None:
    add_user(PROBE_USER.roles, PROBE_USER.id)
    before = audit_count()
    with pytest.raises(Midway), db.transaction() as conn:
        audit.record(conn, PROBE_USER, tool="g4", action="g4.row.write", entity="g4:2")
        raise Midway
    assert audit_count() == before
