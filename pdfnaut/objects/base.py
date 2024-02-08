from __future__ import annotations

from dataclasses import dataclass
from binascii import unhexlify
from typing import Union, List, Dict, Any


class PdfNull:
    """A PDF null object."""
    def __repr__(self) -> str:
        return "PdfNull"


@dataclass
class PdfComment:
    """A PDF comment. These have no syntactical meaning and are assumed to be whitespace."""
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

    @property
    def value(self) -> bytes:
        return unhexlify(self.raw)


@dataclass
class PdfIndirectRef:
    """A reference to a PDF indirect object."""
    object_number: int
    generation: int


PdfObject = Union[
    bool, int, float, bytes, 
    List[Any], Dict[str, Any], 
    PdfHexString, PdfName, 
    PdfIndirectRef, PdfNull
]
