from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Generator, Literal, cast

from typing_extensions import Self

from ..common.fields import FlagField, NameField, StandardField, TextStringField
from ..cos.objects.base import PdfName
from ..cos.objects.containers import PdfArray, PdfDictionary
from ..cos.tokenizer import ContentStreamIterator

if TYPE_CHECKING:
    from ..cos.objects.stream import PdfStream


AnnotationKind = Literal[
    "Text",
    "Link",
    "FreeText",
    "Line",
    "Square",
    "Circle",
    "Polygon",
    "PolyLine",
    "Highlight",
    "Underline",
    "Squiggly",
    "StrikeOut",
    "Caret",
    "Stamp",
    "Ink",
    "Popup",
    "FileAttachment",
    "Sound",
    "Movie",
    "Screen",
    "Widget",
    "PrinterMark",
    "TrapNet",
    "Watermark",
    "3D",
    "Redact",
    "Projection",
    "RichMedia",
]


class AnnotationFlags(enum.IntFlag):
    Null = 0
    Invisible = 1 << 1
    Hidden = 1 << 2
    Print = 1 << 3
    NoZoom = 1 << 4
    NoRotate = 1 << 5
    NoView = 1 << 6
    ReadOnly = 1 << 7
    Locked = 1 << 8
    ToggleNoView = 1 << 9
    LockedContents = 1 << 10


class Annotation(PdfDictionary):
    """An annotation associates an object such as a note, link or rich media element
    with a location on a page of a PDF document (``§ 12.5 Annotations``)."""

    kind = NameField[AnnotationKind]("Subtype")
    """The type of annotation (``Table 171: Annotation types``)"""

    rect = StandardField[PdfArray["int | float"]]("Rect")
    """A rectangle specifying the location of the annotation in the page."""

    contents = TextStringField("Contents")
    """The text contents that shall be displayed when the annotation is open, or if this
    annotation kind does not display text, an alternate description of the annotation's 
    contents."""

    name = TextStringField("NM")
    """An annotation name uniquely identifying it among other annotations in its page."""

    last_modified = TextStringField("M")
    """The date and time the annotation was most recently modified. This value should
    be a PDF date string but processors are expected to accept any text string."""

    flags = FlagField("F", AnnotationFlags, AnnotationFlags.Null)
    """A set of flags specifying various characteristics of the annotation."""

    language = TextStringField("Lang")
    """A language identifier that shall specify the natural language for all text in
    the annotation except where overridden by other explicit language specifications
    (``§ 14.9.2 Natural language specification``)."""

    @classmethod
    def from_dict(cls, mapping: PdfDictionary) -> Self:
        dictionary = cls()
        dictionary.data = mapping.data

        return dictionary


class Page(PdfDictionary):
    """A page in the document (``§ 7.7.3.3 Page Objects``).

    Arguments:
        size (tuple[int, int]):
            The width and height of the physical medium in which the page should
            be printed or displayed.
    """

    resources = StandardField["PdfDictionary | None"]("Resources", None)
    """Resources required by the page contents.

    If the page requires no resources, this returns an empty resource dictionary.
    If the page inherits its resources from an ancestor, this returns None.
    """

    mediabox = StandardField[PdfArray[int]]("MediaBox")
    """A rectangle specifying the boundaries of the physical medium in which the page
    should be printed or displayed."""

    cropbox = StandardField["PdfArray[int] | None"]("CropBox", None)
    """A rectangle specifying the visible region of the page."""

    user_unit = StandardField["int | float"]("UserUnit", 1)
    """The size of a user space unit, in multiples of 1/72 of an inch."""

    rotation = StandardField[int]("Rotate", 0)
    """The number of degrees by which the page shall be visually rotated clockwise.
    The value is a multiple of 90 (by default, 0)."""

    metadata = StandardField["PdfStream | None"]("Metadata", None)
    """A metadata stream, generally written in XMP, containing information about this page."""

    @classmethod
    def from_dict(cls, mapping: PdfDictionary) -> Self:
        dictionary = cls(size=(0, 0))
        dictionary.data = mapping.data

        return dictionary

    def __init__(self, size: tuple[int, int]) -> None:
        super().__init__()

        self["Type"] = PdfName(b"Page")
        self["MediaBox"] = PdfArray([0, 0, *size])

    @property
    def content_stream(self) -> ContentStreamIterator | None:
        """An iterator over the instructions producing the contents of this page."""
        if "Contents" not in self:
            return

        contents = cast("PdfStream | PdfArray[PdfStream]", self["Contents"])

        if isinstance(contents, PdfArray):
            return ContentStreamIterator(b"\n".join(stm.decode() for stm in contents))

        return ContentStreamIterator(contents.decode())

    @property
    def annotations(self) -> Generator[Annotation, None, None]:
        """All annotations associated with this page (``§ 12.5 Annotations``)"""
        for annot in cast(PdfArray[PdfDictionary], self.get("Annots", PdfArray())):
            yield Annotation.from_dict(annot)
