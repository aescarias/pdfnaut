import enum
from collections.abc import Iterable
from datetime import datetime
from typing import Annotated, cast

from typing_extensions import Self

from pdfnaut.common.dictmodels import dictmodel, field
from pdfnaut.common.utils import is_null
from pdfnaut.cos.objects.base import PdfName, PdfReference
from pdfnaut.cos.objects.containers import PdfArray, PdfDictionary

from .base import Annotation, AnnotationBorderStyle, AnnotationKind, annotation_into


class AnnotationReplyType(str, enum.Enum):
    """The reply type or relationship between an annotation and its annotation's
    :attr:`.MarkupAnnotation.in_reply_to` value."""

    REPLY = "R"
    """The annotation is considered a reply to another annotation."""

    GROUP = "Group"
    """The annotation shall be grouped with the annotation replied to."""


class LineEndingStyle(str, enum.Enum):
    SQUARE = "Square"
    CIRCLE = "Circle"
    DIAMOND = "Diamond"
    OPEN_ARROW = "OpenArrow"
    CLOSED_ARROW = "ClosedArrow"
    NONE = "None"
    BUTT = "Butt"
    REVERSED_OPEN_ARROW = "ROpenArrow"
    REVERSED_CLOSED_ARROW = "RClosedArrow"
    SLASH = "Slash"

    def __str__(self) -> str:
        return self.value


@dictmodel(init=False)
class MarkupAnnotation(Annotation):
    """A markup annotation is a type of annotation used primarily to mark
    PDF documents.

    See ISO 32000-2:2020 § 12.5.6.2 "Markup annotations" for details.
    """

    title: str | None = field("T", default=None)
    """The text label to display as the title of the annotation's popup window.
    This shall identify the user who added the annotation.
    """

    creation_date: datetime | None = None
    """The datetime the annotation was created."""

    subject: str | None = field("Subj", default=None)
    """A short description of the subject being addressed by the annotation."""

    def __init__(
        self,
        kind: AnnotationKind,
        rect: Iterable[float],
        contents: str | None = None,
        name: str | None = None,
        *,
        indirect_ref: PdfReference | None = None,
    ) -> None:
        super().__init__(kind, rect, contents, name, indirect_ref=indirect_ref)

    @property
    def in_reply_to(self) -> Annotation | None:
        """The annotation that this annotation is in reply to."""
        irt = self.get("IRT")

        if not is_null(irt):
            irt = cast(PdfReference, self.data["IRT"])
            return annotation_into(irt.get(), indirect_ref=irt)

    @property
    def reply_type(self) -> AnnotationReplyType | str | None:
        """The relationship or reply type between this annotation and the one
        in :attr:`.in_reply_to`."""

        rt_name = self.get("RT")
        if is_null(rt_name):
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
        contents: str | None = None,
        name: str | None = None,
        is_open: bool = False,
        icon: str = "Note",
        *,
        indirect_ref: PdfReference | None = None,
    ) -> None:
        super().__init__("Text", rect, contents, name, indirect_ref=indirect_ref)

        self.is_open = is_open
        self.icon = icon


@dictmodel(init=False)
class LineAnnotation(MarkupAnnotation):
    """A line annotation displays a simple straight line on the page.

    See ISO 32000-2:2020 § 12.5.6.7 "Line annotations" for details.
    """

    path: list[float] = field("L", decoder=list, encoder=PdfArray)
    """An array of four numbers (x1, y1, x2, y2) representing the start and end
    coordinates of the line in default user space units."""

    border_style: AnnotationBorderStyle | None = field("BS", default=None)
    """The border style of the line annotation, controlling the width and dash
    pattern of the line."""

    line_ending_color: list[float] | None = field("IC", default=None)
    """The interior color that will be used for the line endings.

    The number of elements determines the color space: 0 is no color or transparent,
    1 is grayscale, 3 is RGB, and 4 is CMYK.
    """

    @property
    def line_endings(self) -> tuple[LineEndingStyle, LineEndingStyle]:
        """The line ending styles to use when drawing the line.

        The value consists of two line endings for the first and second pair
        of coordinates, respectively.
        """
        line_ends = self.get("LE")
        if is_null(line_ends):
            return (LineEndingStyle.NONE, LineEndingStyle.NONE)

        line_ends = cast(PdfArray[PdfName], line_ends)

        first_end = LineEndingStyle(line_ends[0].value.decode())
        last_end = LineEndingStyle(line_ends[1].value.decode())
        return (first_end, last_end)

    @line_endings.setter
    def line_endings(self, value: tuple[LineEndingStyle, LineEndingStyle] | None) -> None:
        if value is None:
            self.data.pop("LE", None)
            return

        first_le = PdfName(value[0].encode())
        last_le = PdfName(value[1].encode())

        self["LE"] = PdfArray([first_le, last_le])

    @classmethod
    def from_dict(
        cls,
        mapping: PdfDictionary,
        *,
        indirect_ref: PdfReference | None = None,
    ) -> Self:
        dictionary = cls(rect=[0, 0, 0, 0], p1=(0, 0), p2=(0, 0), indirect_ref=indirect_ref)
        dictionary.data = mapping.data

        return dictionary

    def __init__(
        self,
        rect: Iterable[float],
        p1: tuple[int, int],
        p2: tuple[int, int],
        line_endings: tuple[LineEndingStyle, LineEndingStyle] | None = None,
        contents: str | None = None,
        name: str | None = None,
        *,
        indirect_ref: PdfReference | None = None,
    ) -> None:
        super().__init__("Line", rect, contents, name, indirect_ref=indirect_ref)

        self.line_endings = line_endings
        self.path = [*p1, *p2]


@dictmodel(init=False)
class RectangleAnnotation(MarkupAnnotation):
    """A rectangle annotation displays a rectangle on the page.

    See ISO 32000-2:2020 § 12.5.6.8 "Square and circle annotations" for details.
    """

    border_style: AnnotationBorderStyle | None = field("BS", default=None)
    """The border style of the rectangle."""

    interior_color: list[float] | None = field("IC", default=None)
    """The interior color that will be used for the rectangle.

    The number of elements determines the color space: 0 is no color or transparent,
    1 is grayscale, 3 is RGB, and 4 is CMYK.
    """

    def __init__(
        self,
        rect: Iterable[float],
        interior_color: list[float] | None = None,
        border_style: AnnotationBorderStyle | None = None,
        contents: str | None = None,
        name: str | None = None,
        *,
        indirect_ref: PdfReference | None = None,
    ) -> None:
        super().__init__("Square", rect, contents, name, indirect_ref=indirect_ref)

        self.interior_color = interior_color
        self.border_style = border_style
