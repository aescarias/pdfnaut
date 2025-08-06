from __future__ import annotations

import enum
from typing import Generator, Literal, Union, cast

from typing_extensions import Self

from ..common.dictmodels import defaultize, dictmodel, field
from ..cos.objects.base import PdfName, PdfReference
from ..cos.objects.containers import PdfArray, PdfDictionary
from ..cos.objects.stream import PdfStream
from ..cos.tokenizer import ContentStreamTokenizer

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

TabOrder = Literal["R", "C", "S", "A", "W"]


class AnnotationFlags(enum.IntFlag):
    """Flags for a particular annotation. See § 12.5.3, "Annotation flags" for details."""

    NULL = 0
    """A default value meaning that no flags are set."""

    INVISIBLE = 1 << 0
    """If the annotation is non-standard, do not render or print the annotation.
    
    If this flag is clear, the annotation shall be rendered according to its 
    appearance stream.
    """

    HIDDEN = 1 << 1
    """Do not render the annotation or allow user interaction with it."""

    PRINT = 1 << 2
    """Print the annotation when the page is printed unless :attr:`.AnnotationFlags.HIDDEN` 
    is set. If clear, do not print the annotation."""

    NO_ZOOM = 1 << 3
    """Do not scale the annotation's appearance to the page's zoom factor."""

    NO_ROTATE = 1 << 4
    """Do not rotate the annotation to match the page's rotation."""

    NO_VIEW = 1 << 5
    """Do not render the annotation or allow user interaction with it, but still
    allow printing according to the :attr:`.AnnotationFlags.PRINT` flag."""

    READ_ONLY = 1 << 6
    """Do not allow user interaction with the annotation. This is ignored for Widget
    annotations."""

    LOCKED = 1 << 7
    """Do not allow the annotation to be removed or its properties to be modified
    but still allow its contents to be modified."""

    TOGGLE_NO_VIEW = 1 << 8
    """Toggle the :attr:`.AnnotationFlags.No_VIEW` flag when selecting or hovering 
    over the annotation."""

    LOCKED_CONTENTS = 1 << 9
    """Do not allow the contents of the annotation to be modified."""


@dictmodel()
class Annotation(PdfDictionary):
    """An annotation associates an object such as a note, link, or multimedia element
    with a location on a page of a PDF document (see § 12.5, "Annotations")."""

    kind: AnnotationKind = field("Subtype")
    """The kind of annotation. See "Table 171: Annotation types" in the PDF spec 
    for an overview of their functions."""

    rect: PdfArray[float]
    """A rectangle specifying the location of the annotation in the page."""

    contents: str
    """The text contents that shall be displayed when the annotation is open or, if this
    annotation kind does not display text, an alternate description of the annotation's 
    contents."""

    name: str = field("NM")
    """An annotation name uniquely identifying the annotation among others in its page."""

    last_modified: Union[str, None] = field("M", default=None)
    """The date and time the annotation was most recently modified. This value should
    be a PDF date string but PDF processors are expected to accept and display a string
    in any format."""

    language: Union[str, None] = field("Lang", default=None)
    """(PDF 2.0) A language identifier specifying the natural language for all 
    text in the annotation except where overridden by other explicit language 
    specifications (see § 14.9.2, "Natural language specification")."""

    flags: AnnotationFlags = field("F", default=AnnotationFlags.NULL.value)
    """Flags specifying various characteristics of the annotation."""

    color: Union[float, None] = field("C", default=None)
    """An array of 0 to 4 numbers in the range 0.0 to 1.0, representing a color used
    for the following purposes:

    - The background of the annotation's icon when closed.
    - The title bar of the annotation's popup window.
    - The border of a link annotation.

    The number of array elements determines the color space in which the color shall
    be defined: 0 is no color or transparent; 1 is grayscale; 3 is RGB; and 4 is CMYK.
    """

    @classmethod
    def from_dict(cls, mapping: PdfDictionary) -> Self:
        dictionary = defaultize(cls)
        dictionary.data = mapping.data

        return dictionary


@dictmodel(init=False)
class Page(PdfDictionary):
    """A page in a PDF document (see § 7.7.3.3, "Page objects").

    Arguments:
        size (tuple[float, float]):
            The width and height of the physical medium in which the page should
            be printed or displayed. Values shall be provided in multiples of
            1/72 of an inch.

        indirect_ref (PdfReference, optional):
            The indirect reference that this page object is referred to by.

            In typical usage, this value need not be specified.
            pdfnaut will take care of populating it.
    """

    mediabox: PdfArray[float] = field("MediaBox")
    """A rectangle defining the boundaries of the physical medium in which the page
    should be printed or displayed."""

    cropbox: Union[PdfArray[float], None] = field("CropBox", default=None)
    """A rectangle defining the visible region of the page.
    
    If none, the cropbox is the same as the mediabox.
    """

    bleedbox: Union[PdfArray[float], None] = field("BleedBox", default=None)
    """A rectangle defining the region to which the contents of the page shall be 
    clipped when output in a production environment.
    
    If none, the bleedbox is the same as the cropbox.
    """

    trimbox: Union[PdfArray[float], None] = field("TrimBox", default=None)
    """A rectangle defining the intended dimensions of the finished page after trimming.

    If none, the trimbox is the same as the cropbox.
    """

    artbox: Union[PdfArray[float], None] = field("ArtBox", default=None)
    """A rectangle defining the extent of the page's meaningful content as intended 
    by the page's creator.
    
    If none, the artbox is the same as the cropbox.
    """

    resources: Union[PdfDictionary, None] = None
    """Resources required by the page contents.

    If the page requires no resources, this should return an empty resource
    dictionary. If the page inherits its resources from an ancestor,
    this should return None.
    """

    tab_order: Union[TabOrder, None] = field("Tabs", default=None)
    """(optional; PDF 1.5) The tab order to be used for annotations on the page.
    If present, it shall be one of the following values:

    - R: Row order
    - C: Column order
    - S: Logical structure order
    - A: Annotations array order (PDF 2.0)
    - W: Widget order (PDF 2.0)
    """

    user_unit: float = 1
    """The size of a user space unit, in multiples of 1/72 of an inch (by default, 1)."""

    rotation: int = field("Rotate", default=0)
    """The number of degrees by which the page shall be visually rotated clockwise.
    The value is a multiple of 90 (by default, 0)."""

    metadata: Union[PdfStream, None] = None
    """A metadata stream, generally written in XMP, containing information about this page."""

    @classmethod
    def from_dict(cls, mapping: PdfDictionary, indirect_ref: PdfReference | None = None) -> Self:
        dictionary = cls(size=(0, 0), indirect_ref=indirect_ref)
        dictionary.data = mapping.data

        return dictionary

    def __init__(
        self, size: tuple[float, float], *, indirect_ref: PdfReference | None = None
    ) -> None:
        super().__init__()

        self.indirect_ref = indirect_ref

        self["Type"] = PdfName(b"Page")
        self["MediaBox"] = PdfArray([0, 0, *size])

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} mediabox={self.mediabox!r} rotation={self.rotation!r}>"

    @property
    def content_stream(self) -> ContentStreamTokenizer | None:
        """An iterator over the instructions producing the contents of this page."""
        if "Contents" not in self:
            return

        contents = cast("PdfStream | PdfArray[PdfStream]", self["Contents"])

        if isinstance(contents, PdfArray):
            # when Contents is an array, it shall be concatenated into a single
            # content stream with at least one whitespace character in between.
            return ContentStreamTokenizer(b"\n".join(stm.decode() for stm in contents))

        return ContentStreamTokenizer(contents.decode())

    @property
    def annotations(self) -> Generator[Annotation, None, None]:
        """All annotations associated with this page (see § 12.5, "Annotations"
        and :class:`.Annotation`)."""
        for annot in cast(PdfArray[PdfDictionary], self.get("Annots", PdfArray())):
            yield Annotation.from_dict(annot)
