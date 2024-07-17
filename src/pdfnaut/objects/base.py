from __future__ import annotations

from binascii import hexlify, unhexlify
from dataclasses import dataclass
from typing import Generic, List, Mapping, TYPE_CHECKING, TypeVar, Union 


class PdfNull:
    """A PDF null object (``§ 7.3.9 Null Object``)."""
    pass


@dataclass
class PdfComment:
    """A PDF comment (``§ 7.2.3 Comments``). Comments have no syntactical meaning and shall 
    be interpreted as whitespace."""
    value: bytes


if TYPE_CHECKING:
    from typing_extensions import TypeVar

    T = TypeVar("T", default=bytes)
else:
    T = TypeVar("T") # pytest complains if this is not here


@dataclass
class PdfName(Generic[T]):
    """A PDF name object (``§ 7.3.5 Name Objects``)."""
    value: T


@dataclass
class PdfHexString:
    """A PDF hexadecimal string which can be used to include arbitrary binary data in a PDF
    (``§ 7.3.4.3 Hexadecimal Strings``)."""
    
    raw: bytes
    """The hex value of the string"""
    
    def __post_init__(self) -> None:
        # If uneven, we append a zero. (it's hexadecimal -- 2 chars = byte)
        if len(self.raw) % 2 != 0:
            self.raw += b"0"

    @classmethod
    def from_raw(cls, data: bytes):
        """Creates a hexadecimal string from ``data``"""
        return cls(hexlify(data))

    @property
    def value(self) -> bytes:
        """The decoded value of the hex string"""
        return unhexlify(self.raw)


T = TypeVar("T")
@dataclass
class PdfIndirectRef(Generic[T]):
    """A reference to a PDF indirect object."""
    object_number: int
    generation: int


@dataclass
class PdfOperator:
    """A PDF operator within a content stream."""
    value: bytes


PdfObject = Union[
    bool, int, float, bytes, 
    List["PdfObject"], Mapping[str, "PdfObject"], 
    PdfHexString, PdfName, PdfIndirectRef, PdfNull
]
