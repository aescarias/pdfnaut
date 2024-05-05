from __future__ import annotations
from typing import Union

from dataclasses import dataclass


@dataclass
class PdfXRefTable:
    """A cross-reference table which permits random access to objects across a PDF.
    
    It is conformed of subsections indicating where objects are located. A PDF file
    starts with one section (table) containing one subsection (or two if linearized). 
    Additional sections are added per each incremental update.
    """
    sections: list[PdfXRefSubsection]


@dataclass
class PdfXRefSubsection:
    """A subsection part of an XRef table. A subsection includes ``count`` entries 
    whose object numbers start at ``first_obj_num`` and are incremented by one."""
    first_obj_number: int
    count: int
    entries: list[PdfXRefEntry]


@dataclass
class FreeXRefEntry:
    """A Type 0 (f) entry. These entries are members of the linked list of free objects."""
    next_free_object: int
    gen_if_used_again: int


@dataclass
class InUseXRefEntry:
    """A Type 1 (n) entry. These entries point to indirect objects currently in use."""
    offset: int
    generation: int


@dataclass
class CompressedXRefEntry:
    """A Type 2 entry. These entries point to objects that are within an object stream 
    which is assumed "compressed" although it may not be."""
    objstm_number: int
    index_within: int


PdfXRefEntry = Union[FreeXRefEntry, InUseXRefEntry, CompressedXRefEntry]
