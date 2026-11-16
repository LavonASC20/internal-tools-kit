from typing import Annotated, Any, ClassVar

import pytest
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from core.auth import User
from core.masking import PiiModel, pii_field
from core.policy import PolicyRouter, require

Reader = Annotated[User, require("probe.item.read")]


class Item(PiiModel):
    pii_action: ClassVar[str] = "probe.pii.read"
    probe_dob: str = pii_field()


class PlainWithPii(BaseModel):
    probe_dob: str = pii_field()


def test_model_responses_are_accepted() -> None:
    router = PolicyRouter()

    @router.get("/one")
    def one(user: Reader) -> Item:
        raise NotImplementedError

    @router.get("/many")
    def many(user: Reader) -> list[Item]:
        raise NotImplementedError

    @router.get("/maybe")
    def maybe(user: Reader) -> Item | None:
        raise NotImplementedError


def test_pii_outside_a_pii_model_is_refused() -> None:
    router = PolicyRouter()
    with pytest.raises(TypeError, match="not a PiiModel"):

        @router.get("/plain")
        def plain(user: Reader) -> PlainWithPii:
            raise NotImplementedError


@pytest.mark.parametrize("annotation", [dict[str, Any], list[dict[str, Any]], Any, str])
def test_route_with_an_action_must_return_a_model(annotation: Any) -> None:
    router = PolicyRouter()

    def handler(user: Reader) -> Any:
        raise NotImplementedError

    handler.__annotations__["return"] = annotation
    with pytest.raises(TypeError, match="must return a pydantic model"):
        router.get("/raw")(handler)


def test_route_with_an_action_and_no_response_model_is_refused() -> None:
    router = PolicyRouter()
    with pytest.raises(TypeError, match="must return a pydantic model"):

        @router.get("/none", response_model=None)
        def none(user: Reader) -> JSONResponse:
            raise NotImplementedError


def test_route_without_an_action_may_return_anything() -> None:
    router = PolicyRouter()

    @router.get("/health")
    def health() -> dict[str, str]:
        raise NotImplementedError
