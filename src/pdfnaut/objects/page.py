from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Generator, Literal, cast

from typing_extensions import Self

from ..common.fields import FlagField, NameField, StandardField, TextStringField
from ..cos.objects.base import PdfName, PdfReference
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
    """A default value."""

    Invisible = 1 << 0
    """For non-standard annotation types, do not render or print the annotation.
    If not set, the annotation shall be rendered according to its appearance stream.
    """

    Hidden = 1 << 1
    """Do not render the annotation or allow user interaction with it."""

    Print = 1 << 2
    """Print the annotation when the page is printed, except where the Hidden flag
    is set. If clear, do not print the annotation.
    """

    NoZoom = 1 << 3
    """Do not scale the annotation's appearance to the page's zoom factor."""

    NoRotate = 1 << 4
    """Do not rotate the annotation to match the page's rotation."""

    NoView = 1 << 5
    """Do not render the annotation or allow user interaction with it, but still
    allow printing according to the Print flag.
    """

    ReadOnly = 1 << 6
    """Do not allow user interaction with the annotation. This is ignored for Widget
    annotations."""

    Locked = 1 << 7
    """Do not allow the annotation to be removed or its properties to be modified
    but still allow its contents to be modified.
    """

    ToggleNoView = 1 << 8
    """Toggle the NoView flag when selecting or hovering over the annotation."""

    LockedContents = 1 << 9
    """Do not allow the contents of the annotation to be modified."""


class Annotation(PdfDictionary):
    """An annotation associates an object such as a note, link or rich media element
    with a location on a page of a PDF document (``§ 12.5 Annotations``)."""

    kind = NameField[AnnotationKind]("Subtype")
    """The type of annotation. See "Table 171: Annotation types""" ""

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

    color = StandardField["PdfArray[float] | None"]("C", None)
    """An array of 0 to 4 numbers in the range 0.0 to 1.0, representing a color used
    for the following purposes: 
        
    - The background of the annotation's icon when closed
    - The title bar of the annotation's popup window
    - The border of a link annotation.
    
    The number of array elements determines the color space in which the color shall
    be defined: 0 is no color, transparent; 1 is DeviceGray (grayscale); 3 is DeviceRGB;
    and 4 is DeviceCMYK 
    """

    language = TextStringField("Lang")
    """(PDF 2.0) A language identifier that shall specify the natural language for all 
    text in the annotation except where overridden by other explicit language 
    specifications (``§ 14.9.2 Natural language specification``)."""

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
            be printed or displayed. Values provided in multiples of 1/72 of an inch.

        indirect_ref (:class:`PdfReference`, optional):
            The indirect reference that this page object represents.
            In typical usage, this parameter should be none.
    """

    resources = StandardField["PdfDictionary | None"]("Resources", None)
    """Resources required by the page contents.

    If the page requires no resources, this returns an empty resource dictionary.
    If the page inherits its resources from an ancestor, this returns None.
    """

    mediabox = StandardField[PdfArray["int | float"]]("MediaBox")
    """A rectangle defining the boundaries of the physical medium in which the page
    should be printed or displayed."""

    cropbox = StandardField["PdfArray[int | float] | None"]("CropBox", None)
    """A rectangle defining the visible region of the page."""

    bleedbox = StandardField["PdfArray[int | float] | None"]("BleedBox", None)
    """A rectangle defining the region to which the contents of the page shall be 
    clipped when output in a production environment."""

    trimbox = StandardField["PdfArray[int | float] | None"]("TrimBox", None)
    """A rectangle defining the intended dimensions of the finished page after trimming."""

    artbox = StandardField["PdfArray[int | float] | None"]("ArtBox", None)
    """A rectangle defining the extent of the page's meaningful content as intended 
    by the page's creator."""

    user_unit = StandardField["int | float"]("UserUnit", 1)
    """The size of a user space unit, in multiples of 1/72 of an inch."""

    rotation = StandardField[int]("Rotate", 0)
    """The number of degrees by which the page shall be visually rotated clockwise.
    The value is a multiple of 90 (by default, 0)."""

    metadata = StandardField["PdfStream | None"]("Metadata", None)
    """A metadata stream, generally written in XMP, containing information about this page."""

    @classmethod
    def from_dict(cls, mapping: PdfDictionary, indirect_ref: PdfReference | None = None) -> Self:
        dictionary = cls(size=(0, 0), indirect_ref=indirect_ref)
        dictionary.data = mapping.data

        return dictionary

    def __init__(
        self, size: tuple[int | float, int | float], *, indirect_ref: PdfReference | None = None
    ) -> None:
        super().__init__()

        self.indirect_ref = indirect_ref

        self["Type"] = PdfName(b"Page")
        self["MediaBox"] = PdfArray([0, 0, *size])

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} mediabox={self.mediabox!r} rotation={self.rotation!r}>"

    @property
    def content_stream(self) -> ContentStreamIterator | None:
        """An iterator over the instructions producing the contents of this page."""
        if "Contents" not in self:
            return

        contents = cast("PdfStream | PdfArray[PdfStream]", self["Contents"])

        if isinstance(contents, PdfArray):
            # in case the Contents of a document are an array, they must be
            # concatenated into a single one.
            return ContentStreamIterator(b"\n".join(stm.decode() for stm in contents))

        return ContentStreamIterator(contents.decode())

    @property
    def annotations(self) -> Generator[Annotation, None, None]:
        """All annotations associated with this page (``§ 12.5 Annotations``)"""
        for annot in cast(PdfArray[PdfDictionary], self.get("Annots", PdfArray())):
            yield Annotation.from_dict(annot)
