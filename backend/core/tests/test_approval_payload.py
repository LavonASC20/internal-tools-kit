from typing import ClassVar, cast

import pytest
from sqlalchemy import Connection

from core import approvals, policy
from core.approvals import ApprovalKind, ApprovalRequest
from core.auth import User
from core.masking import PiiModel, pii_field


class Subject(PiiModel):
    pii_action: ClassVar[str] = "probe.pii.read"
    probe_tax_id: str = pii_field()


def _noop(conn: Connection, request: ApprovalRequest, user: User) -> None:
    return None


def test_approval_payload_with_pii_keys_is_refused() -> None:
    policy.register_permissions(
        "tools.probe", "probe", {"probe.change.propose": {"a"}, "probe.change.approve": {"b"}}
    )
    approvals.register(ApprovalKind("probe", "probe.change.approve", "probe.change.propose", _noop))
    user = User(id="u", name="U", roles=frozenset({"a"}))
    with pytest.raises(ValueError, match="probe_tax_id"):
        approvals.create(
            cast(Connection, None),
            user=user,
            action="probe.change.approve",
            entity="probe:1",
            payload={"subject": {"probe_tax_id": "FAKE-1"}},
        )
