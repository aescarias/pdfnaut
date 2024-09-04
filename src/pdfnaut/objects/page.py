from __future__ import annotations

import enum
from typing import Literal, cast

from ..cos.objects.base import PdfHexString, parse_text_string
from ..cos.objects.containers import PdfArray, PdfDictionary
from ..cos.objects.stream import PdfStream
from ..cos.tokenizer import ContentStreamIterator

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
FontKind = Literal["Type1"]


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

    def __init__(self, mapping: PdfDictionary) -> None:
        super().__init__(mapping)

        self.mapping = mapping

    @property
    def kind(self) -> AnnotationKind:
        """The type of annotation (``Table 171: Annotation types``)"""
        return cast(AnnotationKind, self["Subtype"].value.decode())

    @property
    def rectangle(self) -> PdfArray[int | float]:
        """A rectangle specifying the location of the annotation in the page."""
        return cast(PdfArray[int], self["Rectangle"])

    @property
    def contents(self) -> str | None:
        """The text contents that shall be displayed when the annotation is open, or if this
        type does not display text, an alternate description of the annotation's contents."""
        if "Contents" not in self:
            return

        return parse_text_string(cast("PdfHexString | bytes", self["Contents"]))

    @property
    def name(self) -> str | None:
        """An annotation name uniquely identifying it among other annotations in its page."""
        if "NM" not in self:
            return

        return parse_text_string(cast("PdfHexString | bytes", self["NM"]))

    @property
    def last_modified(self) -> str | None:
        """The date and time the annotation was most recently modified. This value should
        be a PDF date string but processors are expected to accept any text string."""
        if "M" not in self:
            return

        return parse_text_string(cast("PdfHexString | bytes", self["M"]))

    @property
    def flags(self) -> AnnotationFlags:
        """A set of flags specifying various characteristics of the annotation."""
        return AnnotationFlags(self.get("F", 0))

    @property
    def language(self) -> str | None:
        """A language identifier that shall specify the natural language for all text in
        the annotation except where overridden by other explicit language specifications
        (``§ 14.9.2 Natural language specification``)."""
        if "Lang" not in self:
            return

        return parse_text_string(cast("PdfHexString | bytes", self["Lang"]))


class Page(PdfDictionary):
    """A page in the document (``§ 7.7.3.3 Page Objects``)."""

    def __init__(self, mapping: PdfDictionary) -> None:
        super().__init__(mapping)

        self.mapping = mapping

    @property
    def resources(self) -> PdfDictionary | None:
        """Resources required by the page contents.

        If the page requires no resources, this returns an empty resource dictionary.
        If the page inherits its resources from an ancestor, this returns None.
        """
        if "Resources" not in self:
            return

        return cast(PdfDictionary, self.get("Resources"))

    @property
    def mediabox(self) -> PdfArray[int]:
        """A rectangle specifying the boundaries of the physical medium in which the page
        should be printed or displayed."""
        return cast(PdfArray[int], self["MediaBox"])

    @property
    def cropbox(self) -> PdfArray[int] | None:
        """A rectangle specifying the visible region of the page."""
        if "CropBox" not in self:
            return

        return cast(PdfArray[int], self["CropBox"])

    @property
    def rotation(self) -> int:
        """The number of degrees by which the page shall be rotated clockwise.
        The value is a multiple of 90 (by default, 0)."""
        return cast(int, self.get("Rotate", 0))

    @property
    def metadata(self) -> PdfStream | None:
        """A metadata stream in XMP containing information about this page."""
        if "Metadata" not in self:
            return

        return cast(PdfStream, self["Metadata"])

    @property
    def content_stream(self) -> ContentStreamIterator | None:
        """An iterator over the instructions producing the contents of this page."""
        if "Contents" not in self:
            return

        if isinstance(self["Contents"], PdfArray):
            return ContentStreamIterator(b"\n".join(stm.decode() for stm in self["Contents"]))

        return ContentStreamIterator(self["Contents"].decode())

    @property
    def annotations(self) -> PdfArray[Annotation]:
        """All annotations associated with this page (``§ 12.5 Annotations``)"""
        return PdfArray(
            Annotation(annot)
            for annot in cast(PdfArray[PdfDictionary], self.get("Annots", PdfArray()))
        )
