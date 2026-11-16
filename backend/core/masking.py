"""PII fields are marked once on a response model and masked unless the caller holds the
model's PII action."""

from typing import Any, ClassVar, TypeVar, get_args

from pydantic import BaseModel, Field

from core import policy
from core.auth import User

MASK = "***"

_pii_field_names: set[str] = set()


def pii_field(**kwargs: Any) -> Any:
    """Mark a response field as PII. PII fields must be typed `str` (or `str | None`)."""
    extra = dict(kwargs.pop("json_schema_extra", None) or {})
    extra["pii"] = True
    return Field(json_schema_extra=extra, **kwargs)


def _is_pii(field: Any) -> bool:
    extra = field.json_schema_extra
    return isinstance(extra, dict) and extra.get("pii") is True


class PiiModel(BaseModel):
    """Base for response models that carry PII. Subclasses set `pii_action`."""

    pii_action: ClassVar[str]

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        names = cls.pii_fields()
        if not names:
            return
        if not getattr(cls, "pii_action", None):
            raise TypeError(f"{cls.__name__} has PII fields but no pii_action")
        for name in names:
            annotation = cls.model_fields[name].annotation
            if annotation is not str and set(get_args(annotation)) - {str, type(None)}:
                raise TypeError(f"PII field {cls.__name__}.{name} must be typed str")
        _pii_field_names.update(names)

    @classmethod
    def pii_fields(cls) -> frozenset[str]:
        return frozenset(n for n, f in cls.model_fields.items() if _is_pii(f))


M = TypeVar("M", bound=PiiModel)


def mask(user: User, obj: M) -> M:
    """Return `obj` unchanged if `user` may read its PII, otherwise a copy with PII masked."""
    if policy.allows(user, obj.pii_action):
        return obj
    update = {name: MASK for name in obj.pii_fields() if getattr(obj, name) is not None}
    return obj.model_copy(update=update)


def mask_all(user: User, objs: list[M]) -> list[M]:
    return [mask(user, o) for o in objs]


def pii_field_names() -> frozenset[str]:
    """Every field name marked PII on any loaded model."""
    return frozenset(_pii_field_names)
