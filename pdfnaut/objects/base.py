from __future__ import annotations

from dataclasses import dataclass
from binascii import unhexlify, hexlify
from typing import Union, List, Dict, Any


class PdfNull:
    """A PDF null object."""
    pass

@dataclass
class PdfComment:
    """A PDF comment. Comments have no syntactical meaning and are interpreted as whitespace."""
    value: bytes


@dataclass
class PdfName:
    """A PDF name object."""
    value: bytes


@dataclass
class PdfHexString:
    """A PDF hexadecimal string. These are used to include arbitrary binary data in a PDF."""
    raw: bytes
    """The raw value of the string"""
    
    def __post_init__(self) -> None:
        # If uneven, we append a zero. (it's hexadecimal -- 2 chars = byte)
        if len(self.raw) % 2 != 0:
            self.raw += b"0"

    @classmethod
    def from_raw(cls, data: bytes):
        return cls(hexlify(data))

    @property
    def value(self) -> bytes:
        """The decoded value of the hex string"""
        return unhexlify(self.raw)


@dataclass
class PdfIndirectRef:
    """A reference to a PDF indirect object."""
    object_number: int
    generation: int


@dataclass
class PdfOperator:
    """A PDF operator within a content stream."""
    value: bytes


PdfObject = Union[
    bool, int, float, bytes, 
    List[Any], Dict[str, Any], 
    PdfHexString, PdfName, 
    PdfIndirectRef, PdfNull
]
