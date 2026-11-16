import pytest
from sqlalchemy import Connection

from core import approvals, policy
from core.approvals import ApprovalKind, ApprovalRequest
from core.auth import User


def _noop(conn: Connection, request: ApprovalRequest, user: User) -> None:
    return None


def _other(conn: Connection, request: ApprovalRequest, user: User) -> None:
    return None


@pytest.fixture(autouse=True)
def namespaces() -> None:
    policy.register_permissions(
        "tools.probe", "probe", {"probe.change.propose": {"a"}, "probe.change.approve": {"b"}}
    )
    policy.register_permissions("tools.other", "other", {"other.change.propose": {"a"}})


def _kind(**overrides: object) -> ApprovalKind:
    fields: dict = {
        "tool": "probe",
        "action": "probe.change.approve",
        "propose_action": "probe.change.propose",
        "on_approve": _noop,
    }
    fields.update(overrides)
    return ApprovalKind(**fields)


def test_kind_registers_once() -> None:
    approvals.register(_kind())
    approvals.register(_kind())
    with pytest.raises(RuntimeError, match="already has an approval kind"):
        approvals.register(_kind(on_approve=_other))


def test_kind_actions_must_be_in_the_tools_own_namespace() -> None:
    with pytest.raises(RuntimeError, match="own namespace"):
        approvals.register(_kind(tool="other"))
    with pytest.raises(RuntimeError, match="own namespace"):
        approvals.register(_kind(propose_action="other.change.propose"))


def test_kind_actions_must_be_declared() -> None:
    with pytest.raises(RuntimeError, match="not declared"):
        approvals.register(_kind(action="probe.change.undeclared"))


def test_frozen_policy_refuses_new_kinds() -> None:
    policy.freeze()
    with pytest.raises(RuntimeError, match="frozen"):
        approvals.register(_kind())
