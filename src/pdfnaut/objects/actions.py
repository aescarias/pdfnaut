from __future__ import annotations

from typing import Annotated, Literal, cast

from typing_extensions import Self

from pdfnaut.common.dictmodels import dictmodel, field
from pdfnaut.common.utils import is_null
from pdfnaut.cos.objects.base import PdfName
from pdfnaut.cos.objects.containers import PdfArray, PdfDictionary

from .destinations import Destination, DestType, NamedDestination

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
    elif subtype == "URI":
        return URIAction.from_dict(mapping)

    return Action.from_dict(mapping)


@dictmodel
class Action(PdfDictionary):
    """An action instructs the PDF reader to perform an action such as opening an
    application, going to a page in the document, or playing a sound, when activating
    an annotation or outline item.

    See ISO 32000-2:2020 § 12.6 "Actions" for details.
    """

    subtype: Annotated[ActionKind, "name"] = field("S")
    """The type of action.
    
    Refer to ISO 32000-2:2020 "Table 201 - Action types" for available types.
    """

    @classmethod
    def from_dict(cls, mapping: PdfDictionary) -> Self:
        action = cls(subtype=mapping["S"].value.decode())
        action.data = mapping.data
        return action

    def __init__(
        self, subtype: ActionKind, next_action: list[Action] | Action | None = None
    ) -> None:
        super().__init__()

        self.subtype = subtype
        self.next_action = next_action

    @property
    def next_action(self) -> list[Action] | Action | None:
        """The next action or sequence of actions that shall be performed after this action."""
        next_seq = self.get("Next")
        if is_null(next_seq):
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


@dictmodel
class GoToAction(Action):
    """A go-to action changes the view to a specified destination.

    See ISO 32000-2:2020 § 12.6.4.2 "Go-To actions" for details.
    """

    @classmethod
    def from_dict(cls, mapping: PdfDictionary) -> Self:
        action = cls(Destination())
        action.data = mapping.data
        return action

    def __init__(
        self, destination: DestType, next_action: list[Action] | Action | None = None
    ) -> None:
        super().__init__("GoTo", next_action)

        self.destination = destination

    @property
    def destination(self) -> DestType:
        """The destination to jump to."""
        dest = self["D"]

        if isinstance(dest, PdfArray):
            return Destination(dest)

        return cast(NamedDestination, self["D"])

    @destination.setter
    def destination(self, dest: DestType) -> None:
        if isinstance(dest, Destination):
            self["D"] = PdfArray(dest.data)
        else:
            self["D"] = dest

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(destination={self.destination!r})"


@dictmodel
class URIAction(Action):
    """A URI action causes a URI or uniform resource identifier to be resolved.

    See ISO 32000-2:2020 § 12.6.4.8 "URI actions" for details.
    """

    uri: str = field("URI")
    """The uniform resource identifier (URI) to resolve."""

    is_map: bool = field(default=False)
    """Whether to track the mouse position when the URI is resolved."""

    @classmethod
    def from_dict(cls, mapping: PdfDictionary) -> Self:
        action = cls("")
        action.data = mapping.data
        return action

    def __init__(
        self, uri: str, is_map: bool = False, next_action: list[Action] | Action | None = None
    ) -> None:
        super().__init__("URI", next_action)

        self.uri = uri
        self.is_map = is_map
