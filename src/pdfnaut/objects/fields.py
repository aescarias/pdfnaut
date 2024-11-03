from __future__ import annotations

import datetime
import enum
from typing import Any, Generic, Type, TypeVar, cast

from typing_extensions import Self

from pdfnaut.cos.objects.base import (
    PdfHexString,
    PdfName,
    PdfObject,
    encode_text_string,
    parse_text_string,
)
from pdfnaut.cos.objects.containers import PdfDictionary
from pdfnaut.cos.objects.date import PdfDate


class FieldDictionary(PdfDictionary):
    """A dictionary that includes fields.

    Fields are essentially similar to properties but, rather than affecting an attribute,
    they affect a key in the dictionary."""

    @classmethod
    def from_dict(cls, mapping: PdfDictionary) -> Self:
        dictionary = cls()
        dictionary.data = mapping.data

        return dictionary

    # The two methods below are practically placeholders
    def __init__(self) -> None:
        super().__init__()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({super().__repr__()})"


class Required:
    """Sentinel to mark a field as required."""

    pass


class TextStringField:
    """A field defining a key whose value is a text string (``§ 7.9.2.2 Text string type``)."""

    def __init__(self, field: str) -> None:
        self.field = field

    def __get__(self, obj: FieldDictionary, objtype: Any | None = None) -> str | None:
        if (value := obj.get(self.field)) is not None:
            return parse_text_string(cast("PdfHexString | bytes", value))

    def __set__(self, obj: FieldDictionary, value: str) -> None:
        obj[self.field] = encode_text_string(value)

    def __delete__(self, obj: FieldDictionary) -> None:
        obj.pop(self.field, None)


ET = TypeVar("ET")
LT = TypeVar("LT")


class EnumField(Generic[LT, ET]):
    """A field defining a key whose value is a set of names part of an enumeration."""

    def __init__(self, field: str, enum_map: dict[LT, ET], default: ET) -> None:
        self.field = field
        self.default = default
        self.enum_map = enum_map

    def __get__(self, obj: FieldDictionary, objtype: Any | None = None) -> ET:
        if (value := obj.get(self.field)) is not None:
            name = cast(LT, cast(PdfName, value).value.decode())
            return self.enum_map[name]

        return self.default

    def __set__(self, obj: FieldDictionary, value: ET) -> None:
        lit_map = {val: key for key, val in self.enum_map.items()}
        obj[self.field] = PdfName(lit_map[value].encode())  # type: ignore

    def __delete__(self, obj: FieldDictionary) -> None:
        obj.pop(self.field, None)


T = TypeVar("T")


class StandardField(Generic[T]):
    """A field defining a key whose value is one of the following basic types: boolean,
    numeric, arrays, dictionaries, names, streams, and null.

    Text strings and dates have special handling and are better served by the
    :class:`.TextStringField` and :class:`.DateField` classes respectively.

    Names part of an enumeration are better served by the :class:`.EnumField` class."""

    def __init__(self, field: str, default: T | Type[Required] = Required) -> None:
        self.field = field
        self.default = default

    def __get__(self, obj: FieldDictionary, objtype: Any | None = None) -> T:
        if self.default is Required:
            return cast(T, obj[self.field])

        return cast(T, obj.get(self.field, self.default))

    def __set__(self, obj: FieldDictionary, value: T) -> None:
        obj[self.field] = cast(PdfObject, value)

    def __delete__(self, obj: FieldDictionary) -> None:
        obj.pop(self.field, None)


T = TypeVar("T")


class NameField(Generic[T]):
    """A field defining a key whose value is a name."""

    def __init__(self, field: str, default: T | Type[Required] = Required) -> None:
        self.field = field
        self.default = default

    def __get__(self, obj: FieldDictionary, objtype: Any | None = None) -> T:
        if self.default is Required:
            name = cast(PdfName, obj[self.field]).value.decode()
            return cast(T, name)

        name = cast(PdfName, obj.get(self.field, self.default)).value.decode()
        return cast(T, name)

    def __set__(self, obj: FieldDictionary, value: T) -> None:
        obj[self.field] = PdfName(cast(str, value).encode())

    def __delete__(self, obj: FieldDictionary) -> None:
        obj.pop(self.field, None)


E = TypeVar("E", bound=enum.IntFlag)


class FlagField(Generic[E]):
    """A field defining a key whose value is part of a set of bit flags."""

    def __init__(
        self, field: str, enum_cls: Type[E], default: E | Type[Required] = Required
    ) -> None:
        self.field = field
        self.enum_cls = enum_cls
        self.default = default

    def __get__(self, obj: FieldDictionary, objtype: Any | None = None) -> E:
        if self.default is Required:
            return self.enum_cls(obj[self.field])

        value = obj.get(self.field)
        if value is None:
            return cast(E, self.default)

        return self.enum_cls(value)

    def __set__(self, obj: FieldDictionary, value: E) -> None:
        obj[self.field] = int(value)

    def __delete__(self, obj: FieldDictionary) -> None:
        obj.pop(self.field, None)


class DateField:
    """A field defining a key whose value is a date (``§ 7.9.4 Dates``)."""

    def __init__(self, field: str) -> None:
        self.field = field

    def __get__(self, obj: FieldDictionary, objtype: Any | None = None) -> PdfDate | None:
        text = TextStringField(self.field).__get__(obj)
        if text is not None:
            return PdfDate.from_pdf(text)

    def __set__(self, obj: FieldDictionary, value: PdfDate | datetime.datetime) -> None:
        if isinstance(value, datetime.datetime):
            value = PdfDate.from_datetime(value)

        TextStringField(self.field).__set__(obj, value.as_pdf_string())

    def __delete__(self, obj: FieldDictionary) -> None:
        obj.pop(self.field, None)
