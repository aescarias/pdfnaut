from __future__ import annotations

from typing import Annotated, Literal

from typing_extensions import Self

from pdfnaut.common.dictmodels import defaultize, dictmodel, field
from pdfnaut.cos.objects.containers import PdfArray, PdfDictionary

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
        action = defaultize(cls)
        action.data = mapping.data
        return action

    @property
    def next_action(self) -> list[Action] | Action | None:
        """The next action or sequence of actions that shall be performed after this action."""
        next_seq = self.get("Next", None)
        if next_seq is None:
            return

        if isinstance(next_seq, PdfArray):
            return [Action.from_dict(act) for act in next_seq]

        return Action.from_dict(next_seq)
