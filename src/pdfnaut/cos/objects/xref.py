from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from .containers import PdfDictionary


@dataclass
class PdfXRefSection:
    """A cross-reference section in a XRef table representing an incremental update.

    Each section is comprised of one or multiple subsections containing XRef entries.
    """

    subsections: list[PdfXRefSubsection]
    """The subsections conforming this XRef section."""

    trailer: PdfDictionary
    """The trailer dictionary specified within this XRef section."""


@dataclass
class PdfXRefSubsection:
    """A cross-reference subsection in an XRef section."""

    first_obj_number: int
    """The object number of the first entry in this section. Each entry's object number 
    starts here and is incremented by one."""

    count: int
    """The number of entries in this subsection."""

    entries: list[PdfXRefEntry]
    """The entries contained in this subsection."""


@dataclass
class FreeXRefEntry:
    """A Type 0 (``f``) or free entry. Free entries are entries not currently in use and are
    members of the linked list of free objects."""

    next_free_object: int
    """The object number of the next free object in the linked list."""

    gen_if_used_again: int
    """The generation to apply to an object if this entry is used again."""


@dataclass
class InUseXRefEntry:
    """A Type 1 (``n``) or in-use entry. In-use entries refer to the objects stored in a
    document."""

    offset: int
    """The byte offset of the object in the file (starting after the %PDF marker)."""

    generation: int
    """The generation of the object."""


@dataclass
class CompressedXRefEntry:
    """A Type 2 or compressed entry. Compressed entries refer to objects stored within
    an object stream."""

    objstm_number: int
    """The object number of the object stream containing this object."""

    index_within: int
    """The index of the object within the object stream."""


PdfXRefEntry = Union[FreeXRefEntry, InUseXRefEntry, CompressedXRefEntry]
