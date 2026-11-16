"""PII fields are marked once on a response model. Core masks them whenever the model is
serialized, unless the caller holds the model's `pii_action`. Tools never call masking by hand.

`core.policy` reveals the authorized caller's actions for the duration of a request. With nothing
revealed (outside a request, or on a route with no action) every PII field is masked.
"""

import types
from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, ClassVar, Union, get_args, get_origin

from pydantic import BaseModel, Field, SerializerFunctionWrapHandler, model_serializer

MASK = "***"

_pii_field_names: set[str] = set()
_revealed_actions: ContextVar[frozenset[str]] = ContextVar("revealed_actions", default=frozenset())


@contextmanager
def revealing(actions: Iterable[str]) -> Iterator[None]:
    """Serialize PII in full only for models whose `pii_action` is in `actions`."""
    token = _revealed_actions.set(frozenset(actions))
    try:
        yield
    finally:
        _revealed_actions.reset(token)


def pii_field(**kwargs: Any) -> Any:
    """Mark a field of a `PiiModel` as PII. PII fields must be typed `str` (or `str | None`)."""
    extra = dict(kwargs.pop("json_schema_extra", None) or {})
    extra["pii"] = True
    return Field(json_schema_extra=extra, **kwargs)


def _is_pii(field: Any) -> bool:
    extra = field.json_schema_extra
    return isinstance(extra, dict) and extra.get("pii") is True


class PiiModel(BaseModel):
    """Base for models that carry PII. Subclasses set `pii_action`."""

    pii_action: ClassVar[str]

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        own = PiiModel.__pydantic_decorators__.model_serializers["_mask_pii"].func
        if any(d.func is not own for d in cls.__pydantic_decorators__.model_serializers.values()):
            raise TypeError(
                f"{cls.__name__} must not define a model_serializer: it disables masking"
            )
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

    # No return annotation: an annotated wrap serializer would replace the model's OpenAPI schema.
    @model_serializer(mode="wrap")
    def _mask_pii(self, handler: SerializerFunctionWrapHandler):
        data = handler(self)
        names = self.pii_fields()
        if not names or not isinstance(data, dict) or self.pii_action in _revealed_actions.get():
            return data
        for name in names:
            field = type(self).model_fields[name]
            for key in {name, field.alias, field.serialization_alias} - {None}:
                if data.get(key) is not None:
                    data[key] = MASK
        return data


def check_response_type(annotation: Any, where: str) -> None:
    """Refuse a response type that marks PII outside a `PiiModel`: it would never be masked."""
    seen: set[type] = set()

    def walk(tp: Any) -> None:
        if isinstance(tp, type) and issubclass(tp, BaseModel) and tp not in seen:
            seen.add(tp)
            fields = tp.model_fields.values()
            if not issubclass(tp, PiiModel) and any(_is_pii(f) for f in fields):
                raise TypeError(f"{where}: {tp.__name__} marks PII but is not a PiiModel")
            for field in fields:
                walk(field.annotation)
        for arg in get_args(tp):
            walk(arg)

    walk(annotation)


def is_model_response(annotation: Any) -> bool:
    """True for a pydantic model, or a list/sequence/optional of models: shapes core can mask."""
    origin, args = get_origin(annotation), get_args(annotation)
    if origin is None:
        return isinstance(annotation, type) and issubclass(annotation, BaseModel)
    if origin in (Union, types.UnionType):
        models = [a for a in args if a is not type(None)]
        return bool(models) and all(is_model_response(a) for a in models)
    if isinstance(origin, type) and issubclass(origin, Sequence) and not issubclass(origin, str):
        return bool(args) and all(is_model_response(a) for a in args if a is not Ellipsis)
    return False


def pii_field_names() -> frozenset[str]:
    """Every field name marked PII on any loaded model."""
    return frozenset(_pii_field_names)


def pii_keys(value: Any) -> set[str]:
    """Keys anywhere in a JSON-like value that are PII field names. Stored JSON must have none."""
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in _pii_field_names:
                found.add(str(key))
            found |= pii_keys(item)
    elif isinstance(value, list | tuple):
        for item in value:
            found |= pii_keys(item)
    return found
