"""KYC-specific behavior. Generic guardrails (G1 to G6) live in backend/tests/."""

from collections.abc import Callable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core import masking, policy
from core.masking import MASK
from tools.kyc_review.permissions import PII_READ
from tools.kyc_review.schemas import KycCase, Proposal

Login = Callable[[str], TestClient]


def _propose(client: TestClient, case_id: int, decision: str = "clear") -> dict:
    response = client.post(
        f"/api/kyc/cases/{case_id}/propose",
        json={"decision": decision, "rationale": "Documents verified against registry."},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_seed_has_about_twenty_open_cases_with_fake_ids(client_for: Login) -> None:
    cases = client_for("ana").get("/api/kyc/cases").json()
    assert len(cases) == 20
    assert all(c["status"] == "open" for c in cases)
    assert all(c["national_id"].startswith("FAKE-") for c in cases)


def test_kyc_marks_national_id_and_date_of_birth_as_pii() -> None:
    assert KycCase.pii_fields() == {"national_id", "date_of_birth"}
    assert KycCase.pii_action == "kyc.pii.read"


def test_auditor_sees_cases_with_pii_masked(client_for: Login) -> None:
    case = client_for("audrey").get("/api/kyc/cases/1").json()
    assert case["national_id"] == MASK
    assert case["date_of_birth"] == MASK
    assert case["subject_name"].endswith("01")


def test_propose_moves_case_to_pending_and_opens_approval(client_for: Login) -> None:
    ana = client_for("ana")
    result = _propose(ana, 3, "reject")
    assert result["case"]["status"] == "pending_approval"

    request = next(
        r for r in ana.get("/api/approvals").json() if r["id"] == result["approval_request_id"]
    )
    assert request["tool"] == "kyc_review"
    assert request["action"] == "kyc.decision.approve"
    assert request["entity"] == "kyc_case:3"
    assert request["payload"]["decision"] == "reject"
    assert request["proposed_by"] == "ana"
    assert request["status"] == "pending"
    assert request["can_decide"] is False


def test_only_open_cases_accept_a_proposal(client_for: Login) -> None:
    ana = client_for("ana")
    _propose(ana, 4)
    response = ana.post(
        "/api/kyc/cases/4/propose", json={"decision": "clear", "rationale": "Again."}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_state"


def test_propose_validates_decision_and_rationale(client_for: Login) -> None:
    ana = client_for("ana")
    bad_decision = ana.post(
        "/api/kyc/cases/1/propose", json={"decision": "maybe", "rationale": "x"}
    )
    blank_rationale = ana.post(
        "/api/kyc/cases/1/propose", json={"decision": "clear", "rationale": "   "}
    )
    assert bad_decision.status_code == 422
    assert blank_rationale.status_code == 422
    assert ana.get("/api/kyc/cases/1").json()["status"] == "open"


def test_unknown_case_is_404(client_for: Login) -> None:
    ana = client_for("ana")
    assert ana.get("/api/kyc/cases/999").status_code == 404
    missing = ana.post("/api/kyc/cases/999/propose", json={"decision": "clear", "rationale": "x"})
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"


def test_approving_a_clear_decision_clears_the_case(client_for: Login) -> None:
    request_id = _propose(client_for("ana"), 5, "clear")["approval_request_id"]
    response = client_for("sam").post(f"/api/approvals/{request_id}/approve", json={})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "approved"
    assert client_for("ana").get("/api/kyc/cases/5").json()["status"] == "cleared"


def test_approving_a_reject_decision_rejects_the_case(client_for: Login) -> None:
    request_id = _propose(client_for("ana"), 6, "reject")["approval_request_id"]
    assert client_for("sam").post(f"/api/approvals/{request_id}/approve").status_code == 200
    assert client_for("ana").get("/api/kyc/cases/6").json()["status"] == "rejected"


def test_rejecting_the_request_returns_the_case_to_open(client_for: Login) -> None:
    ana = client_for("ana")
    request_id = _propose(ana, 7)["approval_request_id"]
    response = client_for("sam").post(
        f"/api/approvals/{request_id}/reject", json={"comment": "Need proof of address."}
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "rejected"
    assert ana.get("/api/kyc/cases/7").json()["status"] == "open"
    _propose(ana, 7)  # can be proposed again


def test_case_list_filters_by_status(client_for: Login) -> None:
    ana = client_for("ana")
    _propose(ana, 8)
    pending = ana.get("/api/kyc/cases", params={"status": "pending_approval"}).json()
    assert [c["id"] for c in pending] == [8]


def test_spec_outcome_flow_with_audit_trail(client_for: Login) -> None:
    """SPEC section 2: Dana cannot approve her own proposal, Sam can, Audrey sees the trail."""
    dana, sam, audrey = client_for("dana"), client_for("sam"), client_for("audrey")
    request_id = _propose(dana, 2, "clear")["approval_request_id"]

    refused = dana.post(f"/api/approvals/{request_id}/approve")
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "self_approval"
    assert client_for("ana").get("/api/kyc/cases/2").json()["status"] == "pending_approval"

    assert sam.post(f"/api/approvals/{request_id}/approve").status_code == 200

    events = audrey.get("/api/audit", params={"entity": "kyc_case:2"}).json()
    trail = [(e["actor"], e["action"]) for e in reversed(events)]
    assert trail == [
        ("dana", "kyc.decision.propose"),
        ("sam", "approvals.approve"),
        ("sam", "kyc.decision.apply"),
    ]
    roles = {e["action"]: e["role"] for e in events}
    assert roles["kyc.decision.propose"] == "analyst"
    assert roles["kyc.decision.apply"] == "senior_reviewer"

    raw = client_for("ana").get("/api/kyc/cases/2").json()
    serialized = str(events)
    assert raw["national_id"] not in serialized
    assert raw["date_of_birth"] not in serialized
    assert "registry" not in serialized  # rationale stays in the approval payload


def test_kyc_grants_cannot_be_changed_after_registration(app: FastAPI) -> None:
    for owner in ("tools.kyc_review", "tools.feature_flags"):
        with pytest.raises(RuntimeError):
            policy.register_permissions(owner, "kyc", {PII_READ: {"engineer"}})
    assert policy.declared_roles_for(PII_READ) == {"analyst", "senior_reviewer"}


def test_kyc_case_pii_is_masked_on_serialization_unless_revealed() -> None:
    case = KycCase(
        id=1,
        subject_name="Test Subject",
        national_id="FAKE-1",
        date_of_birth="1990-01-01",
        risk_flag="low",
        status="open",
    )
    proposal = Proposal(case=case, approval_request_id=1)
    assert case.model_dump()["national_id"] == MASK
    assert proposal.model_dump()["case"]["date_of_birth"] == MASK
    with masking.revealing({"kyc.case.read"}):
        assert case.model_dump()["national_id"] == MASK
    with masking.revealing({PII_READ}):
        assert proposal.model_dump()["case"]["national_id"] == "FAKE-1"
