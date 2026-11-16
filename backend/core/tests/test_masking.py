from typing import Any, ClassVar

import pytest
from pydantic import model_serializer

from core import masking
from core.masking import MASK, PiiModel, pii_field


class Subject(PiiModel):
    pii_action: ClassVar[str] = "probe.pii.read"
    name: str
    probe_ssn: str = pii_field()


def test_pii_is_masked_unless_the_action_is_revealed() -> None:
    subject = Subject(name="Test", probe_ssn="FAKE-1")
    assert subject.model_dump() == {"name": "Test", "probe_ssn": MASK}
    with masking.revealing({"probe.other"}):
        assert subject.model_dump()["probe_ssn"] == MASK
    with masking.revealing({"probe.pii.read"}):
        assert subject.model_dump()["probe_ssn"] == "FAKE-1"


def test_subclass_cannot_replace_the_masking_serializer() -> None:
    with pytest.raises(TypeError, match="model_serializer"):

        class Leaky(Subject):
            @model_serializer(mode="wrap")
            def _own(self, handler: Any) -> Any:
                return handler(self)
