from collections.abc import Iterable
from enum import Enum
from typing import cast

from typing_extensions import Self

from pdfnaut.common.dictmodels import dictmodel, field
from pdfnaut.common.utils import is_null
from pdfnaut.cos.objects.base import PdfName, PdfReference
from pdfnaut.cos.objects.containers import PdfArray, PdfDictionary
from pdfnaut.objects.actions import Action, action_into
from pdfnaut.objects.annotations import Annotation, AnnotationBorderStyle
from pdfnaut.objects.destinations import Destination, DestType, NamedDestination


class LinkHighlightMode(str, Enum):
    """The highlighting mode for link annotations (see :class:`LinkAnnotation`)."""

    NONE = "N"
    """No highlight."""

    INVERT_CONTENTS = "I"
    """Invert the contents of the annotation rectangle (default)."""

    INVERT_OUTLINE = "O"
    """Invert the annotation's border or outline."""

    PUSH = "P"
    """Display the annotation as if it were being pushed below the surface of the page."""

    def __str__(self) -> str:
        return self.value


@dictmodel(init=False)
class LinkAnnotation(Annotation):
    """A link annotation represents either a hypertext link to a location within
    the document or an action to perform.

    See ISO 32000-2:2020 § 12.5.6.5 "Link annotations" for details.
    """

    @staticmethod
    def _get_highlight(highlight_name: PdfName) -> LinkHighlightMode | str:
        name = cast(PdfName, highlight_name).value.decode()

        if name in list(LinkHighlightMode):
            return LinkHighlightMode(name)

        return name

    @staticmethod
    def _set_highlight(style: LinkHighlightMode | str) -> PdfName:
        return PdfName(style.encode())

    highlight_mode: LinkHighlightMode | str = field(
        "H",
        default=LinkHighlightMode.INVERT_CONTENTS,
        encoder=_set_highlight,
        decoder=_get_highlight,
    )
    """The annotation's highlight mode."""

    quad_points: list[float] | None = field(
        default=None,
        encoder=lambda lst: PdfArray(lst) if lst is not None else None,
        decoder=lambda arr: list(arr) if not is_null(arr) else None,
    )
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
        contents: str | None = None,
        name: str | None = None,
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
        act = self.get("A")
        if is_null(act):
            return

        act = cast(PdfDictionary, act)
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
        dest = self.get("Dest")
        if is_null(dest):
            return

        if isinstance(dest, PdfArray):
            return Destination(dest)

        return cast(NamedDestination, dest)

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
        border_style = self.get("BS")
        if is_null(border_style):
            return

        border_style = cast(PdfDictionary, border_style)
        return AnnotationBorderStyle.from_dict(border_style)

    @border_style.setter
    def border_style(self, style: AnnotationBorderStyle | None) -> None:
        if style is None:
            self.pop("BS", None)
        else:
            self["BS"] = PdfDictionary(style.data)
