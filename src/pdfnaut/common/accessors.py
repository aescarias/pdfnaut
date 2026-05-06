from __future__ import annotations

import datetime
from types import UnionType
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Literal,
    Protocol,
    TypeVar,
    Union,
    cast,
    get_args,
    get_origin,
)

from pdfnaut.common.utils import is_null

from ..common.dates import encode_iso8824, parse_iso8824
from ..cos.objects.base import (
    PdfHexString,
    PdfName,
    PdfObject,
    encode_text_string,
    parse_text_string,
)
from ..cos.objects.containers import PdfDictionary

if TYPE_CHECKING:
    from .dictmodels import Field


class _MISSING_TYPE:
    pass


MISSING = _MISSING_TYPE()


class Accessor(Protocol):
    field: Field

    def __init__(self, field: Field) -> None: ...
    def __get__(self, obj: PdfDictionary, objtype: Any | None = None) -> Any: ...
    def __set__(self, obj: PdfDictionary, value: Any) -> None: ...
    def __delete__(self, obj: PdfDictionary) -> None: ...


class StandardAccessor:
    """An accessor defining a key whose value is a type that does not require
    a complex mapping such as booleans, numbers, and certain name objects.

    Text strings and dates have special handling and are better served by the
    :class:`.TextStringAccessor` and :class:`.DateAccessor` classes respectively.
    """

    def __init__(self, field: Field) -> None:
        self.field = field

    def __get__(self, obj: PdfDictionary, objtype: Any | None = None) -> PdfObject:
        assert (ty := self.field.type_) is not None

        if not callable(ty):
            ty = lambda x: x  # noqa: E731 -- shorter

        if self.field.default is MISSING:
            return ty(obj[self.field.key])

        return ty(obj.get(self.field.key, self.field.default))

    def __set__(self, obj: PdfDictionary, value: PdfObject | None) -> None:
        if value is None:
            return self.__delete__(obj)

        obj[self.field.key] = value

    def __delete__(self, obj: PdfDictionary) -> None:
        obj.pop(self.field.key, None)


class NameAccessor:
    """An accessor defining a key whose value may be any of a set of names."""

    def __init__(self, field: Field) -> None:
        self.field = field

    def __get__(self, obj: PdfDictionary, objtype: Any | None = None) -> str | None:
        if self.field.default is MISSING:
            return cast(PdfName, obj[self.field.key]).value.decode()

        if self.field.default is None:
            default = None
        else:
            default = PdfName(self.field.default.encode())

        name = obj.get(self.field.key, default)
        if isinstance(name, PdfName):
            return name.value.decode()

    def __set__(self, obj: PdfDictionary, value: str | None) -> None:
        if value is None:
            return self.__delete__(obj)

        obj[self.field.key] = PdfName(value.encode())

    def __delete__(self, obj: PdfDictionary) -> None:
        obj.pop(self.field.key, None)


class TextStringAccessor:
    """An accessor defining a key whose value is a text string.

    See ISO 32000-2:2020 § 7.9.2.2 "Text string type" for details.
    """

    def __init__(self, field: Field) -> None:
        self.field = field

    def __get__(self, obj: PdfDictionary, objtype: Any | None = None) -> str | None:
        value = obj.get(self.field.key)
        if not is_null(value):
            value = cast("PdfHexString | bytes", value)
            return parse_text_string(value)

        return self.field.default

    def __set__(self, obj: PdfDictionary, value: str | None) -> None:
        if value is None:
            return self.__delete__(obj)

        obj[self.field.key] = encode_text_string(value)

    def __delete__(self, obj: PdfDictionary) -> None:
        obj.pop(self.field.key, None)


class DateAccessor:
    """An accessor defining a key whose value is a date (see ISO 32000-2:2020 § 7.9.4 "Dates")."""

    def __init__(self, field: Field) -> None:
        self.field = field

    def __get__(self, obj: PdfDictionary, objtype: Any | None = None) -> datetime.datetime | None:
        text = TextStringAccessor(self.field).__get__(obj)

        if text is not None:
            return parse_iso8824(text)

        return self.field.default

    def __set__(self, obj: PdfDictionary, value: datetime.datetime | None) -> None:
        if value is None:
            return self.__delete__(obj)

        TextStringAccessor(self.field).__set__(obj, encode_iso8824(value))

    def __delete__(self, obj: PdfDictionary) -> None:
        obj.pop(self.field.key, None)


class ModelAccessor:
    """An accessor defining a key whose value is a dictionary represented by
    a dictmodel."""

    def __init__(self, field: Field) -> None:
        self.field = field

    def __get__(self, obj: PdfDictionary, objtype: Any | None = None) -> PdfObject | None:
        metadata = self.field.metadata or {}

        model = metadata["model"]
        if self.field.default is MISSING:
            return model.from_dict(obj[self.field.key])

        value = obj.get(self.field.key, self.field.default)
        return model.from_dict(value) if value is not None else None

    def __set__(self, obj: PdfDictionary, value: PdfObject | None) -> None:
        if value is None:
            return self.__delete__(obj)

        value = cast(PdfDictionary, value)
        obj[self.field.key] = PdfDictionary(value.data)

    def __delete__(self, obj: PdfDictionary) -> None:
        obj.pop(self.field.key, None)


class TransformAccessor:
    """An accessor defining a key whose value is handled by user-provided encoder
    and decoder functions."""

    def __init__(self, field: Field) -> None:
        self.field = field

    def __get__(self, obj: PdfDictionary, objtype: Any | None = None) -> PdfObject:
        assert self.field.encoder is not None and self.field.decoder is not None

        if self.field.default is MISSING:
            return self.field.decoder(obj[self.field.key])

        return self.field.decoder(obj.get(self.field.key, self.field.default))

    def __set__(self, obj: PdfDictionary, value: PdfObject | None) -> None:
        if value is None:
            return self.__delete__(obj)

        assert self.field.encoder is not None
        obj[self.field.key] = self.field.encoder(value)

    def __delete__(self, obj: PdfDictionary) -> None:
        obj.pop(self.field.key, None)


def _is_string_type(value: Any) -> bool:
    # string handling
    if isinstance(value, type) and issubclass(value, str):
        return True

    # literal handling
    if get_origin(value) is not Literal:
        return False

    return all(isinstance(lit, str) for lit in get_args(value))


def _is_dictmodel(model: type[Any]) -> bool:
    return (
        hasattr(model, "__bases__")
        and PdfDictionary in model.__bases__
        and hasattr(model, "__accessors__")
        and hasattr(model, "from_dict")
    )


def lookup_accessor_by_field(field: Field) -> tuple[type[Accessor], dict[str, Any]]:
    if field.encoder is not None and field.decoder is not None:
        return TransformAccessor, {}

    if field.type_ is None:
        raise ValueError(f"field {field.name!r} must have a type")

    return lookup_accessor_by_type(field.type_)


def lookup_accessor_by_type(value_type: type) -> tuple[type[Accessor], dict[str, Any]]:
    if value_type is str:
        return TextStringAccessor, {}
    elif value_type is datetime.datetime:
        return DateAccessor, {}
    elif get_origin(value_type) is Annotated:
        type_, subtype, *_ = get_args(value_type)

        if isinstance(type_, TypeVar):
            bound = type_.__bound__
            if bound is None:
                raise TypeError(f"typevar {type_!r} requires a bound")

            type_ = bound

        if _is_string_type(type_):
            if subtype.lower() == "text":
                return TextStringAccessor, {}
            elif subtype.lower() == "name":
                return NameAccessor, {}
            else:
                raise TypeError(f"{subtype!r} not a valid subtype for a string accessor")

        raise NotImplementedError(f"accessor from annotated form {value_type!r} not implemented")
    elif (origin := get_origin(value_type)) is UnionType or origin is Union:
        args = get_args(value_type)
        assert len(args) >= 1

        if len(args) > 2:
            raise ValueError(f"cannot create accessor for type {value_type!r}")

        if not issubclass(args[-1], type(None)):
            raise NotImplementedError("only supported union form is T | None")

        return lookup_accessor_by_type(args[0])
    elif get_origin(value_type) is Literal:
        return NameAccessor, {}
    elif _is_dictmodel(value_type):
        return ModelAccessor, {"model": value_type}

    return StandardAccessor, {}
