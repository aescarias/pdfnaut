from __future__ import annotations
from typing import Union

from dataclasses import dataclass


@dataclass
class PdfXRefTable:
    """A cross-reference table which permits random access to objects across a PDF.
    
    It is conformed of subsections indicating where objects are located. A PDF file
    starts with one subsection and additional ones are added per each incremental update.
    """
    sections: list[PdfXRefSubsection]


@dataclass
class PdfXRefSubsection:
    """A subsection part of an XRef table. Each subsection generally indicates 
    incremental updates to a document."""
    first_obj_number: int
    count: int
    entries: list[PdfXRefEntry]


@dataclass
class FreeXRefEntry:
    """A Type 0 entry. These entries form the linked list of free objects."""
    next_free_object: int
    gen_if_used_again: int


@dataclass
class InUseXRefEntry:
    """A Type 1 entry. These point to uncompressed entries currently in use."""
    offset: int
    generation: int


@dataclass
class CompressedXRefEntry:
    """A Type 2 entry. These point to entries that are within an object stream."""
    objstm_number: int
    index_within: int


PdfXRefEntry = Union[FreeXRefEntry, InUseXRefEntry, CompressedXRefEntry]
