from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PdfXrefTable:
    """A cross-reference table which permits random access to objects across a PDF.
    
    It is conformed of subsections indicating where objects are located. A PDF file
    starts with one subsection and additional ones are added per each incremental update.
    """
    sections: list[PdfXrefSubsection]


@dataclass
class PdfXrefSubsection:
    """A subsection part of an XRef table. Each subsection generally indicates 
    incremental updates to a document."""
    first_obj_number: int
    count: int
    entries: list[PdfXrefEntry]


@dataclass
class PdfXrefEntry:
    """An entry inside a subsection in an XRef table. It represents the position of an object
    in the table.
    
    In the case the entry is in use, ``offset`` points to the start position of the object.
    In the case it is a free entry, ``offset`` points to the object number of the next free 
    object and ``generation`` is the generation to use when this object number is used again.
    """
    offset: int
    generation: int
    in_use: bool

