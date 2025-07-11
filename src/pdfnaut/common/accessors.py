from __future__ import annotations

import datetime
import enum
from typing import TYPE_CHECKING, Any, Generic, Literal, Protocol, TypeVar, Union, cast, get_origin

from typing_extensions import get_args

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


MISSING = object()
"""Sentinel to mark a field as missing."""


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
        if self.field.default is MISSING:
            return obj[self.field.key]

        return obj.get(self.field.key, self.field.default)

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

    def __get__(self, obj: PdfDictionary, objtype: Any | None = None) -> str:
        if self.field.default is MISSING:
            return cast(PdfName, obj[self.field.key]).value.decode()

        return cast(PdfName, obj.get(self.field.key, self.field.default)).value.decode()

    def __set__(self, obj: PdfDictionary, value: str | None) -> None:
        if value is None:
            return self.__delete__(obj)

        obj[self.field.key] = PdfName(value.encode())

    def __delete__(self, obj: PdfDictionary) -> None:
        obj.pop(self.field.key, None)


class TextStringAccessor:
    """An accessor defining a key whose value is a text string (``§ 7.9.2.2 Text string type``)."""

    def __init__(self, field: Field) -> None:
        self.field = field

    def __get__(self, obj: PdfDictionary, objtype: Any | None = None) -> str | None:
        if (value := obj.get(self.field.key)) is not None:
            return parse_text_string(cast("PdfHexString | bytes", value))
        return self.field.default

    def __set__(self, obj: PdfDictionary, value: str | None) -> None:
        if value is None:
            return self.__delete__(obj)

        obj[self.field.key] = encode_text_string(value)

    def __delete__(self, obj: PdfDictionary) -> None:
        obj.pop(self.field.key, None)


class DateAccessor:
    """An accessor defining a key whose value is a date (see § 7.9.4. "Dates")."""

    def __init__(self, field: Field) -> None:
        self.field = field

    def __get__(self, obj: PdfDictionary, objtype: Any | None = None) -> datetime.datetime | None:
        text = TextStringAccessor(self.field).__get__(obj)

        if text is not None:
            return parse_iso8824(text)

    def __set__(self, obj: PdfDictionary, value: datetime.datetime | None) -> None:
        if value is None:
            return self.__delete__(obj)

        TextStringAccessor(self.field).__set__(obj, encode_iso8824(value))

    def __delete__(self, obj: PdfDictionary) -> None:
        obj.pop(self.field.key, None)


E = TypeVar("E", bound=enum.IntFlag)


class BitFlagAccessor(Generic[E]):
    """An accessor defining a key whose value is part of a set of bit flags."""

    def __init__(self, field: Field) -> None:
        self.field = field

    def __get__(self, obj: PdfDictionary, objtype: Any | None = None) -> E | None:
        assert self.field.metadata and "enum_cls" in self.field.metadata

        value = obj.get(self.field.key, self.field.default)
        if value is not None:
            return self.field.metadata["enum_cls"](value)

    def __set__(self, obj: PdfDictionary, value: E | None) -> None:
        if value is None:
            return self.__delete__(obj)

        obj[self.field.key] = int(value)

    def __delete__(self, obj: PdfDictionary) -> None:
        obj.pop(self.field.key, None)


def lookup_accessor(value_type: type) -> tuple[type[Accessor], dict[str, Any]]:
    if value_type is str:
        return TextStringAccessor, {}
    elif value_type is datetime.datetime:
        return DateAccessor, {}
    elif get_origin(value_type) is Union:
        args = get_args(value_type)
        assert len(args) >= 1

        if len(args) > 2:
            raise ValueError(f"cannot create accessor for type {value_type!r}")

        if isinstance(args[-1], type(None)):
            raise NotImplementedError("only supported union form is Union[T, None]")

        return lookup_accessor(args[0])
    elif get_origin(value_type) is Literal:
        return NameAccessor, {}
    elif isinstance(value_type, enum.IntFlag):
        return BitFlagAccessor[value_type], {"enum_cls": value_type}

    return StandardAccessor, {}
