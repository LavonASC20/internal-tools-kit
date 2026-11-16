from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

Environment = Literal["dev", "staging", "prod"]


class Flag(BaseModel):
    id: int
    key: str
    environment: Environment
    description: str
    enabled: bool
    pending_request_id: int | None
    updated_by: str | None
    updated_at: datetime


class Toggle(BaseModel):
    enabled: bool


class ProposeProdToggle(BaseModel):
    enabled: bool
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class ProdProposal(BaseModel):
    flag: Flag
    approval_request_id: int
