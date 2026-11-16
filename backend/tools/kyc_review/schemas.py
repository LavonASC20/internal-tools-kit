from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, StringConstraints

from core.masking import PiiModel, pii_field
from tools.kyc_review.permissions import PII_READ

CaseStatus = Literal["open", "pending_approval", "cleared", "rejected"]
Decision = Literal["clear", "reject"]


class KycCase(PiiModel):
    pii_action: ClassVar[str] = PII_READ

    id: int
    subject_name: str
    national_id: str = pii_field()
    date_of_birth: str = pii_field(description="ISO date")
    risk_flag: str
    status: CaseStatus


class ProposeDecision(BaseModel):
    decision: Decision
    rationale: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
    ]


class Proposal(BaseModel):
    case: KycCase
    approval_request_id: int
