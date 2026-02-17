import enum
from collections.abc import Iterable, MutableSequence
from typing import Literal, cast, overload

from typing_extensions import Self

from pdfnaut.cos.objects.base import PdfName, PdfReference, encode_text_string
from pdfnaut.cos.parser import PdfParser
from pdfnaut.exceptions import PdfParseError, PdfWriteError

from ..common.dictmodels import dictmodel, field
from ..cos.objects.containers import PdfArray, PdfDictionary

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
    """Toggle the :attr:`.AnnotationFlags.NO_VIEW` flag when selecting or hovering 
    over the annotation."""

    LOCKED_CONTENTS = 1 << 9
    """Do not allow the contents of the annotation to be modified."""


@dictmodel()
class Annotation(PdfDictionary):
    """An annotation associates an object such as a note, link, or multimedia element
    with a location on a page of a PDF document (see § 12.5, "Annotations")."""

    kind: AnnotationKind = field("Subtype")
    """The kind of annotation. See ``"Table 171: Annotation types"`` in the PDF spec for 
    an overview of their functions."""

    rect: PdfArray[float]
    """A rectangle specifying the location of the annotation in the page."""

    contents: str
    """The text contents that shall be displayed when the annotation is open or, if this
    annotation kind does not display text, an alternate description of the annotation's 
    contents."""

    name: str = field("NM")
    """An annotation name uniquely identifying the annotation among others in its page."""

    last_modified: str | None = field("M", default=None)
    """The date and time the annotation was most recently modified. This value should
    be a PDF date string but PDF processors are expected to accept and display a string
    in any format."""

    language: str | None = field("Lang", default=None)
    """(PDF 2.0) A language identifier specifying the natural language for all 
    text in the annotation except where overridden by other explicit language 
    specifications (see § 14.9.2, "Natural language specification")."""

    flags: AnnotationFlags = field("F", default=AnnotationFlags.NULL.value)
    """Flags specifying various characteristics of the annotation."""

    color: PdfArray[float] | None = field("C", default=None)
    """An array of 0 to 4 numbers in the range 0.0 to 1.0, representing a color used
    for the following purposes:

    - The background of the annotation's icon when closed.
    - The title bar of the annotation's popup window.
    - The border of a link annotation.

    The number of array elements determines the color space in which the color shall
    be defined: 0 is no color or transparent; 1 is grayscale; 3 is RGB; and 4 is CMYK.
    """

    @classmethod
    def from_dict(
        cls,
        mapping: PdfDictionary,
        *,
        indirect_ref: PdfReference | None = None,
    ) -> Self:
        dictionary = cls("Text", [0, 0, 0, 0], "", "", indirect_ref=indirect_ref)
        dictionary.data = mapping.data

        return dictionary

    def __init__(
        self,
        kind: AnnotationKind,
        rect: Iterable[float],
        contents: str,
        name: str,
        *,
        indirect_ref: PdfReference | None = None,
    ) -> None:
        super().__init__()

        self["Subtype"] = PdfName(kind.encode("ascii"))
        self["Rect"] = PdfArray(rect)
        self["Contents"] = encode_text_string(contents)
        self["NM"] = encode_text_string(name)

        self.indirect_ref = indirect_ref


class AnnotationList(MutableSequence[Annotation]):
    """A list of annotations representing the ``Annots`` key in a page object."""

    def __init__(self, array: PdfArray, pdf: PdfParser | None = None) -> None:
        self.pdf = pdf
        self.array = array

    @overload
    def __getitem__(self, index: int) -> Annotation: ...
    @overload
    def __getitem__(self, index: slice) -> MutableSequence[Annotation]: ...

    def __getitem__(self, index: int | slice) -> Annotation | MutableSequence[Annotation]:
        # TODO: implement caching similar to page list
        if isinstance(index, int):
            ref = self.array.data[index]
            return Annotation.from_dict(ref.get(), indirect_ref=ref)

        return [Annotation.from_dict(ref.get(), indirect_ref=ref) for ref in self.array.data[index]]

    @overload
    def __setitem__(self, index: int, value: Annotation) -> None: ...
    @overload
    def __setitem__(self, index: slice, value: Iterable[Annotation]) -> None: ...

    def __setitem__(self, index: int | slice, value: Annotation | Iterable[Annotation]) -> None:
        if isinstance(index, slice):
            value = cast(Iterable[Annotation], value)
            self.array[index] = self._ensure_annots_in_pdf(*value)
        else:
            value = cast(Annotation, value)
            self.array[index] = self._ensure_annots_in_pdf(value)[0]

    @overload
    def __delitem__(self, index: int) -> None: ...
    @overload
    def __delitem__(self, index: slice) -> None: ...

    def __delitem__(self, index: int | slice) -> None:
        del self.array[index]  # TODO: consider also deleting the associated annotation

    def insert(self, index: int, value: Annotation) -> None:
        """Inserts an annotation ``value`` at ``index``."""
        self.array.insert(index, self._ensure_annots_in_pdf(value)[0])

    def append(self, value: Annotation) -> None:
        """Appends an annotation ``value`` to the list."""
        self.array.append(self._ensure_annots_in_pdf(value)[0])

    def clear(self) -> None:
        """Clears the annotation list."""
        self.array.clear()

    def extend(self, values: Iterable[Annotation]) -> None:
        """Extends the annotation list by appending ``values`` to its end."""
        self.array.extend(self._ensure_annots_in_pdf(*values))

    def reverse(self) -> None:
        """Reverses the annotation list."""
        self.array.reverse()

    def pop(self, index: int = -1) -> Annotation:
        """Pops an annotation at ``index``."""
        value = self.array.pop(index)
        return Annotation.from_dict(value.get())

    def remove(self, value: Annotation) -> None:
        """Removes an annotation ``value`` from the list."""

        if value.indirect_ref is None:
            raise PdfParseError("annotation has no indirect reference")

        self.array.remove(value.indirect_ref)

    def __iadd__(self, values: Iterable[Annotation]) -> Self:
        self.extend(values)
        return self

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.array.data}>"

    def __len__(self) -> int:
        return len(self.array)

    def _ensure_annots_in_pdf(self, *annots: Annotation) -> list[PdfReference]:
        references: list[PdfReference] = []

        for annot in annots:
            if annot.indirect_ref is not None:
                references.append(annot.indirect_ref)
                continue

            if self.pdf is None:
                raise PdfWriteError("annotation list must belong to a pdf")

            annot.indirect_ref = self.pdf.objects.add(PdfDictionary(annot.data))
            references.append(annot.indirect_ref)

        return references
