from typing import Annotated

from core.auth import User
from core.policy import PolicyRouter, require
from tools.feature_flags import service
from tools.feature_flags.permissions import FLAG_READ, FLAG_TOGGLE, PROD_PROPOSE
from tools.feature_flags.schemas import (
    Environment,
    Flag,
    ProdProposal,
    ProposeProdToggle,
    Toggle,
)

router = PolicyRouter(prefix="/flags", tags=["feature_flags"])


@router.get("")
def list_flags(
    user: Annotated[User, require(FLAG_READ)], environment: Environment | None = None
) -> list[Flag]:
    return service.list_flags(environment)


@router.get("/{flag_id}")
def get_flag(flag_id: int, user: Annotated[User, require(FLAG_READ)]) -> Flag:
    return service.get_flag(flag_id)


@router.post("/{flag_id}/toggle")
def toggle(flag_id: int, body: Toggle, user: Annotated[User, require(FLAG_TOGGLE)]) -> Flag:
    return service.toggle(user, flag_id, body.enabled)


@router.post("/{flag_id}/propose")
def propose(
    flag_id: int, body: ProposeProdToggle, user: Annotated[User, require(PROD_PROPOSE)]
) -> ProdProposal:
    return service.propose_prod_toggle(user, flag_id, body.enabled, body.reason)
