"""G3: a proposer cannot decide their own request, through the API or by direct insert."""

import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from core import approvals, db, policy
from core.approvals import ApprovalKind
from core.auth import User
from tests import discover
from tests.conftest import add_user, audit_count, login, snapshot_tables

KINDS = discover.approval_kinds()


def _proposer_and_decider_roles(kind: ApprovalKind) -> set[str]:
    proposers = policy.declared_roles_for(kind.propose_action)
    deciders = policy.declared_roles_for(kind.action)
    if not proposers or not deciders:
        pytest.fail(f"{kind.action}: no role can propose or decide it")
    return {sorted(proposers)[0], sorted(deciders)[0]}


def _open_request(kind: ApprovalKind, user_id: str, roles: set[str]) -> int:
    proposer = User(id=user_id, name=user_id, roles=frozenset(roles))
    with db.transaction() as conn:
        request = approvals.create(
            conn, user=proposer, action=kind.action, entity="g3:probe", payload={}
        )
    return request.id


def _request_row(request_id: int) -> tuple[str, str | None]:
    with db.connect() as conn:
        row = conn.execute(
            text("SELECT status, decided_by FROM approval_requests WHERE id = :id"),
            {"id": request_id},
        ).one()
    return row.status, row.decided_by


@pytest.mark.parametrize("decision", ["approve", "reject"])
@pytest.mark.parametrize("kind", KINDS, ids=[k.action for k in KINDS])
def test_proposer_holding_both_actions_cannot_decide_via_api(
    kind: ApprovalKind, decision: str, app: FastAPI
) -> None:
    roles = _proposer_and_decider_roles(kind)
    user_id = add_user(roles, "g3_both")
    request_id = _open_request(kind, user_id, roles)
    before_audit, before = audit_count(), snapshot_tables()

    response = login(app, user_id).post(
        f"/api/approvals/{request_id}/{decision}", json={"comment": "my own"}
    )

    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "self_approval"
    assert _request_row(request_id) == ("pending", None)
    assert audit_count() == before_audit
    assert snapshot_tables() == before


@pytest.mark.parametrize("kind", KINDS, ids=[k.action for k in KINDS])
def test_direct_insert_of_a_self_decided_request_fails(kind: ApprovalKind, seeded_db: str) -> None:
    user_id = add_user(set(), "g3_direct")
    with pytest.raises(DBAPIError), db.transaction() as conn:
        conn.execute(
            text(
                "INSERT INTO approval_requests "
                "(tool, action, entity, payload, proposed_by, status, decided_by, decided_at) "
                "VALUES (:tool, :action, 'g3:direct', '{}', :u, 'approved', :u, now())"
            ),
            {"tool": kind.tool, "action": kind.action, "u": user_id},
        )
    with db.connect() as conn:
        rows = conn.execute(
            text("SELECT count(*) FROM approval_requests WHERE entity = 'g3:direct'")
        )
        assert rows.scalar_one() == 0


@pytest.mark.parametrize("kind", KINDS, ids=[k.action for k in KINDS])
def test_direct_update_to_self_decided_fails(kind: ApprovalKind, seeded_db: str) -> None:
    roles = _proposer_and_decider_roles(kind)
    user_id = add_user(roles, "g3_update")
    request_id = _open_request(kind, user_id, roles)
    with pytest.raises(DBAPIError), db.transaction() as conn:
        conn.execute(
            text(
                "UPDATE approval_requests SET status = 'approved', decided_by = proposed_by, "
                "decided_at = now() WHERE id = :id"
            ),
            {"id": request_id},
        )
    assert _request_row(request_id) == ("pending", None)


def test_the_check_holds_for_any_tool_value(seeded_db: str) -> None:
    """The database rule is not tied to a registered kind: a made-up tool is refused too."""
    user_id = add_user(set(), "g3_any")
    with pytest.raises(DBAPIError), db.transaction() as conn:
        conn.execute(
            text(
                "INSERT INTO approval_requests "
                "(tool, action, entity, payload, proposed_by, status, decided_by, decided_at) "
                "VALUES ('g3_unknown', 'g3_unknown.x.approve', 'g3:any', '{}', :u, "
                "'rejected', :u, now())"
            ),
            {"u": user_id},
        )
