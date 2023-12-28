from __future__ import annotations

from typing import Any
from dataclasses import dataclass, field


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
    value: bytes
    
    def __post_init__(self) -> None:
        # If uneven, we append a zero. (it's hexadecimal -- 2 chars = byte)
        if len(self.value) % 2 != 0:
            self.value += b"0"


@dataclass
class PdfIndirectRef:
    """A reference to a PDF indirect object."""
    object_number: int
    generation: int


@dataclass
class PdfStream:
    """A stream object in a PDF"""
    details: dict[str, Any]
    raw: bytes = field(repr=False)

