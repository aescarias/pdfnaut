import enum
from collections.abc import Iterable, MutableSequence
from datetime import datetime
from typing import Annotated, Literal, cast, overload

from typing_extensions import Self

from pdfnaut.cos.objects.base import PdfName, PdfReference, encode_text_string
from pdfnaut.cos.parser import PdfParser
from pdfnaut.exceptions import PdfParseError, PdfWriteError
from pdfnaut.objects.actions import Action, action_into
from pdfnaut.objects.destinations import Destination, DestType, NamedDestination

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
    """Flags for a particular annotation.

    See ISO 32000-2:2020 § 12.5.3 "Annotation flags" for details.
    """

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


@dictmodel(init=False)
class Annotation(PdfDictionary):
    """An annotation associates an object such as a note, link, or multimedia element
    with a location on a page of a PDF document.

    See ISO 32000-2:2020 § 12.5 "Annotations" for details.
    """

    kind: AnnotationKind = field("Subtype")
    """The kind of annotation. See ISO 32000-2:2020 "Table 171 — Annotation types" for details."""

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
    specifications 
    
    See ISO 32000-2:2020 § 14.9.2 "Natural language specification" for details.
    """

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


LinkHighlightMode = Literal["N", "I", "O", "P"]
BorderStyle = Literal["S", "D", "B", "I", "U"]


@dictmodel(init=False)
class AnnotationBorderStyle(PdfDictionary):
    """The border style for the outline that surrounds an annotation.

    See ISO 32000-2:2020 § 12.5.4 "Border styles" for details.
    """

    width: float = field("W", default=1)
    """The border width in points."""

    style: BorderStyle = field("S", default="S")
    """The border style. May be either of the following:

    - S: A solid rectangle.
    - D: A dashed rectangle specified by :attr:`.AnnotationBorderStyle.dash_pattern`.
    - B: A simulated embossed (beveled) rectangle.
    - I: A simulated engraved (inset) rectangle.
    - U: An underline.
    """

    dash_pattern: PdfArray[float] | None = field("D", default=None)
    """The dash pattern used for the border style if dashed."""

    @classmethod
    def from_dict(cls, mapping: PdfDictionary) -> Self:
        border_style = cls()
        border_style.data = mapping.data
        return border_style


@dictmodel(init=False)
class LinkAnnotation(Annotation):
    """A link annotation represents either a hypertext link to a location within
    the document or an action to perform.

    See ISO 32000-2:2020 § 12.5.6.5 "Link annotations" for details.
    """

    highlight_mode: LinkHighlightMode = field("H", default="I")
    """The annotation's highlight mode. May be either of the following:

    - N: No highlight.
    - I: Invert the contents of the annotation rectangle (default).
    - O: Invert the annotation's border/outline.
    - P: Display the annotation as if it were being pushed below the surface of the page.
    """

    quad_points: PdfArray[float] | None = field(default=None)
    """A sequence of n quadrilaterals, comprised of 8 numbers representing the coordinates
    in default user space that comprise the region in which the link should be activated.
    
    Item order: x1, y1, x2, y2, x3, y3, x4, y4
    """

    @classmethod
    def from_dict(
        cls,
        mapping: PdfDictionary,
        *,
        indirect_ref: PdfReference | None = None,
    ) -> Self:
        dictionary = cls([0, 0, 0, 0], "", "", indirect_ref=indirect_ref)
        dictionary.data = mapping.data

        return dictionary

    def __init__(
        self,
        rect: Iterable[float],
        contents: str,
        name: str,
        action: Action | None = None,
        destination: DestType | None = None,
        *,
        indirect_ref: PdfReference | None = None,
    ) -> None:
        super().__init__("Link", rect, contents, name, indirect_ref=indirect_ref)

        self.action = action
        self.destination = destination

    @property
    def action(self) -> Action | None:
        """The action that shall be performed when the link annotation is triggered."""
        if "A" not in self:
            return

        act = cast(PdfDictionary, self["A"])
        return action_into(act)

    @action.setter
    def action(self, act: Action | None) -> None:
        if act is None:
            self.pop("A", None)
        else:
            self["A"] = PdfDictionary(act.data)

    @property
    def destination(self) -> DestType | None:
        """The destination that shall be displayed when the link annotation is triggered."""

        if "Dest" not in self:
            return

        dest = self["Dest"]

        if isinstance(dest, PdfArray):
            return Destination(dest)

        return cast(NamedDestination, self["Dest"])

    @destination.setter
    def destination(self, dest: DestType | None = None) -> None:
        if dest is None:
            self.pop("Dest", None)
        else:
            self["Dest"] = dest

    @property
    def border_style(self) -> AnnotationBorderStyle | None:
        """The border style specifying the line width and dash pattern
        that shall be used when drawing the annotation outline."""

        if "BS" not in self:
            return

        mapping = cast(PdfDictionary, self["BS"])
        return AnnotationBorderStyle.from_dict(mapping)

    @border_style.setter
    def border_style(self, style: AnnotationBorderStyle | None) -> None:
        if style is None:
            self.pop("BS", None)
        else:
            self["BS"] = PdfDictionary(style.data)


class AnnotationReplyType(enum.Enum):
    """The reply type or relationship between an annotation and its annotation's
    :attr:`.MarkupAnnotation.in_reply_to` value."""

    REPLY = 0
    """The annotation is considered a reply to another annotation."""

    GROUP = 0
    """The annotation shall be grouped with the annotation replied to."""


@dictmodel(init=False)
class MarkupAnnotation(Annotation):
    """A markup annotation is a type of annotation used primarily to mark
    PDF documents.

    See ISO 32000-2:2020 § 12.5.6.2 "Markup annotations" for details.
    """

    title: str | None = field("T", None)
    """The text label to display as the title of the annotation's popup window.
    This shall identify the user who added the annotation.
    """

    creation_date: datetime | None = None
    """The datetime the annotation was created."""

    subject: str | None = field("Subj", default=None)
    """A short description of the subject being addressed by the annotation."""

    @property
    def in_reply_to(self) -> Annotation | None:
        """The annotation that this annotation is in reply to."""
        irt = self.data.get("IRT")

        if irt is not None:
            return annotation_into(irt.get(), indirect_ref=irt)

    def __init__(
        self,
        kind: AnnotationKind,
        rect: Iterable[float],
        contents: str,
        name: str,
        *,
        indirect_ref: PdfReference | None = None,
    ) -> None:
        super().__init__(kind, rect, contents, name, indirect_ref=indirect_ref)

    @property
    def reply_type(self) -> AnnotationReplyType | str | None:
        """The relationship or reply type between this annotation and the one
        in :attr:`.in_reply_to`."""

        rt_name = self.get("RT")
        if rt_name is None:
            return

        reply_type = cast(PdfName, rt_name).value.decode()

        if reply_type == "R":
            return AnnotationReplyType.REPLY
        elif reply_type == "Group":
            return AnnotationReplyType.GROUP
        else:
            return reply_type


@dictmodel(init=False)
class TextAnnotation(MarkupAnnotation):
    """A text annotation represents a sticky note attached to a point in the PDF document.
    When closed, it shall appear as an icon (defined by :attr:`.TextAnnotation.icon`);
    when open, it shall display a popup window containing the text of the note.

    See ISO 32000-2:2020 § 12.5.6.4 "Text annotations" for details.
    """

    is_open: bool = field("Open", default=False)
    """Whether the annotation is initially displayed open."""

    icon: Annotated[str, "name"] = field("Name", default="Note")
    """The name of an icon that shall be used when displaying the annotation.
    
    The icon name may be any of the following standard names or any other
    supported value. 
    
    Standard names: Comment, Key, Note, Help, NewParagraph, Paragraph, and Insert.
    """

    @classmethod
    def from_dict(
        cls,
        mapping: PdfDictionary,
        *,
        indirect_ref: PdfReference | None = None,
    ) -> Self:
        dictionary = cls([0, 0, 0, 0], "", "", indirect_ref=indirect_ref)
        dictionary.data = mapping.data

        return dictionary

    def __init__(
        self,
        rect: Iterable[float],
        contents: str,
        name: str,
        is_open: bool = False,
        icon: str = "Note",
        *,
        indirect_ref: PdfReference | None = None,
    ) -> None:
        super().__init__("Text", rect, contents, name, indirect_ref=indirect_ref)

        self.is_open = is_open
        self.icon = icon


def annotation_into(
    annot: PdfDictionary, *, indirect_ref: PdfReference | None = None
) -> Annotation:
    """Converts a mapping ``annot`` into an instance of :class:`.Annotation` or
    one of its subclasses according to the annotation subtype."""

    subtype = cast(PdfName, annot["Subtype"]).value.decode()

    if subtype == "Link":
        return LinkAnnotation.from_dict(annot, indirect_ref=indirect_ref)
    elif subtype == "Text":
        return TextAnnotation.from_dict(annot, indirect_ref=indirect_ref)
    elif subtype in {
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
        "FileAttachment",
        "Sound",
        "Redact",
        "Projection",
    }:
        return MarkupAnnotation.from_dict(annot, indirect_ref=indirect_ref)
    else:
        return Annotation.from_dict(annot, indirect_ref=indirect_ref)


class AnnotationList(MutableSequence[Annotation]):
    """A mutable sequence representing the list of annotations (the ``Annots`` key)
    in a page object."""

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
            return annotation_into(ref.get(), indirect_ref=ref)

        return [annotation_into(ref.get(), indirect_ref=ref) for ref in self.array.data[index]]

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
        return annotation_into(value.get())

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
