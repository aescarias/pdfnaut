from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Literal, cast

from typing_extensions import Self

from pdfnaut.common.dictmodels import dictmodel, field
from pdfnaut.cos.objects.base import PdfHexString, PdfName, PdfNull, PdfObject, PdfReference
from pdfnaut.cos.objects.containers import PdfArray, PdfDictionary
from pdfnaut.objects.page import Page

ActionKind = Literal[
    "GoTo",
    "GoToR",
    "GoToE",
    "GoToDPart",
    "Launch",
    "Thread",
    "URI",
    "Sound",
    "Movie",
    "Hide",
    "Named",
    "SubmitForm",
    "ResetForm",
    "ImportData",
    "SetOCGState",
    "Rendition",
    "Trans",
    "GoTo3DView",
    "JavaScript",
    "RichMediaExecute",
]


def action_into(mapping: PdfDictionary) -> Action:
    """Converts a dictionary ``mapping`` into a corresponding :class:`Action` subclass."""

    subtype_name = cast(PdfName, mapping["S"])
    subtype = cast(ActionKind, subtype_name.value.decode())

    if subtype == "GoTo":
        return GoToAction.from_dict(mapping)

    return Action.from_dict(mapping)


@dictmodel()
class Action(PdfDictionary):
    """An action instructs the PDF reader to perform an action such as opening an
    application, going to a page in the document, or playing a sound, when activating
    an annotation or outline item.

    See § 12.6 "Actions" for details.
    """

    subtype: Annotated[ActionKind, "name"] = field("S")
    """The type of action described. See "Table 201 - Action types" for details."""

    @classmethod
    def from_dict(cls, mapping: PdfDictionary) -> Self:
        action = cls(subtype=mapping["S"].value.decode())
        action.data = mapping.data
        return action

    def __init__(
        self, subtype: ActionKind, next_action: list[Action] | Action | None = None
    ) -> None:
        super().__init__()

        self["Subtype"] = PdfName(subtype.encode())
        self.next_action = next_action

    @property
    def next_action(self) -> list[Action] | Action | None:
        """The next action or sequence of actions that shall be performed after this action."""
        next_seq = self.get("Next", None)
        if next_seq is None:
            return

        if isinstance(next_seq, PdfArray):
            return [action_into(act) for act in next_seq]

        return action_into(next_seq)

    @next_action.setter
    def next_action(self, action: list[Action] | Action | None = None) -> None:
        if action is None:
            self.pop("Next", None)
        elif isinstance(action, Action):
            self["Next"] = PdfDictionary(action.data)
        else:
            self["Next"] = PdfArray([PdfDictionary(act.data) for act in action])


class GoToAction(Action):
    """A go-to action changes the view to a specified destination.

    See § 12.6.4.2 "Go-To actions" for details.
    """

    @classmethod
    def from_dict(cls, mapping: PdfDictionary) -> Self:
        action = cls(Destination())
        action.data = mapping.data
        return action

    def __init__(
        self, destination: DestType, next_action: list[Action] | Action | None = None
    ) -> None:
        super().__init__("GoTo")

        self.destination = destination
        self.next_action = next_action

    @property
    def destination(self) -> DestType:
        """The destination to jump to."""
        dest = self["D"]

        if isinstance(dest, PdfArray):
            return Destination(dest)

        return cast(NamedDestination, self["D"])

    @destination.setter
    def destination(self, dest: DestType) -> None:
        self["D"] = dest

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(destination={self.destination!r})"


DestinationKind = Literal["XYZ", "Fit", "FitH", "FitV", "FitR", "FitB", "FitBH", "FitBV"]


def nullify(*objs: PdfObject | None) -> list[PdfObject]:
    return [obj if obj is not None else PdfNull() for obj in objs]


class Destination(PdfArray):
    """A explicit destination points to a page within a PDF document with a specified
    location and zoom factor.

    See § 12.3.2 "Destinations" for details.
    """

    @classmethod
    def xyz(
        cls,
        page: Page,
        left: int | float | None = None,
        top: int | float | None = None,
        zoom: int | float | None = None,
    ) -> Self:
        """Creates a coordinate destination to ``page`` with the coordinates (``left``, ``top``)
        positioned at the upper-left corner of the window and the contents of the page magnified
        by the specified ``zoom`` factor.

        Omitting these parameters means that the current value shall remain unchanged.
        """
        if page.indirect_ref is None:
            raise ValueError("page must be in document")

        return cls([page.indirect_ref, PdfName(b"XYZ"), *nullify(left, top, zoom)])

    @classmethod
    def fit(cls, page: Page) -> Self:
        """Creates a destination to ``page`` with its contents magnified to fit the entire
        page within the window."""
        if page.indirect_ref is None:
            raise ValueError("page must be in document")

        return cls([page.indirect_ref, PdfName(b"Fit")])

    @classmethod
    def fit_horizontal(cls, page: Page, top: int | float | None = None) -> Self:
        """Creates a destination to ``page`` with its contents magnified to fit the entire
        page within the window horizontally and the top edge of the window positioned at the
        vertical coordinate ``top``."""
        if page.indirect_ref is None:
            raise ValueError("page must be in document")

        return cls([page.indirect_ref, PdfName(b"FitH"), *nullify(top)])

    @classmethod
    def fit_vertical(cls, page: Page, left: int | float | None = None) -> Self:
        """Creates a destination to ``page`` with its contents magnified to fit the entire
        page within the window vertically and the left edge of the window positioned at the
        horizontal coordinate ``left``."""
        if page.indirect_ref is None:
            raise ValueError("page must be in document")

        return cls([page.indirect_ref, PdfName(b"FitV"), *nullify(left)])

    @classmethod
    def fit_rectangle(
        cls,
        page: Page,
        left: int | float,
        bottom: int | float,
        right: int | float,
        top: int | float,
    ) -> Self:
        """Creates a destination to ``page`` with its contents magnified to fit the rectangle
        formed by the coordinates ``left``, ``bottom``, ``right``, and ``top``.
        """
        if page.indirect_ref is None:
            raise ValueError("page must be in document")

        return cls([page.indirect_ref, PdfName(b"FitR"), left, bottom, right, top])

    @classmethod
    def fit_bbox(cls, page: Page) -> Self:
        """Creates a destination to ``page`` with its contents magnified to fit the page
        bounding box."""
        if page.indirect_ref is None:
            raise ValueError("page must be in document")

        return cls([page.indirect_ref, PdfName(b"FitB")])

    @classmethod
    def fit_bbox_horizontal(cls, page: Page, top: int | float | None = None) -> Self:
        """Creates a destination to ``page`` with its contents magnified to fit the entire
        bounding box of the page within the window horizontally and the top edge of the window
        positioned at the vertical coordinate ``top``."""
        if page.indirect_ref is None:
            raise ValueError("page must be in document")

        return cls([page.indirect_ref, PdfName(b"FitBH"), *nullify(top)])

    @classmethod
    def fit_bbox_vertical(cls, page: Page, left: int | float | None = None) -> Self:
        """Creates a destination to ``page`` with its contents magnified to fit the entire
        bounding box of the page within the window vertically and the left edge of the window
        positioned at the horizontal coordinate ``left``."""
        if page.indirect_ref is None:
            raise ValueError("page must be in document")

        return cls([page.indirect_ref, PdfName(b"FitBV"), *nullify(left)])

    @property
    def page(self) -> Page:
        page_ref = cast(PdfReference, self.data[0])
        return Page.from_dict(page_ref.get(), indirect_ref=page_ref)

    @property
    def kind(self) -> DestinationKind:
        name = cast(PdfName, self[1]).value.decode()
        return cast(DestinationKind, name)

    @property
    def args(self) -> Sequence[PdfObject]:
        return self[2:]


NamedDestination = PdfName | PdfHexString | bytes
DestType = NamedDestination | Destination
