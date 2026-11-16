from typing import Annotated

from core.auth import User
from core.policy import PolicyRouter, require
from tools.kyc_review import service
from tools.kyc_review.permissions import CASE_READ, DECISION_PROPOSE
from tools.kyc_review.schemas import CaseStatus, KycCase, Proposal, ProposeDecision

router = PolicyRouter(prefix="/kyc", tags=["kyc_review"])


@router.get("/cases")
def list_cases(
    user: Annotated[User, require(CASE_READ)], status: CaseStatus | None = None
) -> list[KycCase]:
    return service.list_cases(user, status)


@router.get("/cases/{case_id}")
def get_case(case_id: int, user: Annotated[User, require(CASE_READ)]) -> KycCase:
    return service.get_case(user, case_id)


@router.post("/cases/{case_id}/propose")
def propose(
    case_id: int, body: ProposeDecision, user: Annotated[User, require(DECISION_PROPOSE)]
) -> Proposal:
    return service.propose(user, case_id, body.decision, body.rationale)
