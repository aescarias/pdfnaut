from __future__ import annotations

from typing import Union, List, Any, Dict
from dataclasses import dataclass, field


class PdfNull:
    pass


@dataclass
class PdfComment:
    value: bytes


@dataclass
class PdfName:
    value: bytes


@dataclass
class PdfHexString:
    value: bytes
    
    def __post_init__(self) -> None:
        # If uneven, we append a zero. (it's hexadecimal -- 2 chars = byte)
        if len(self.value) % 2 != 0:
            self.value += b"0"

@dataclass
class PdfXrefTable:
    sections: list[PdfXrefSubsection]


@dataclass
class PdfXrefSubsection:
    first_obj_number: int
    count: int
    entries: list[PdfXrefEntry]


@dataclass
class PdfXrefEntry:
    offset: int
    generation: int
    in_use: bool


@dataclass
class PdfIndirectRef:
    object_number: int
    generation: int


@dataclass
class PdfStream:
    extent: dict[str, Any]
    contents: bytes = field(repr=False)

PdfObject = Union[
    bool, int, float, bytes, 
    List[Any], Dict[str, Any], 
    PdfHexString, PdfName, 
    PdfIndirectRef, PdfNull
]
