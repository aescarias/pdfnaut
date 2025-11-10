from __future__ import annotations

from collections.abc import Generator
from enum import IntFlag

from typing_extensions import Self

from pdfnaut.common.dictmodels import dictmodel, field
from pdfnaut.cos.objects import PdfDictionary
from pdfnaut.cos.objects.base import PdfHexString, PdfName, PdfReference
from pdfnaut.cos.objects.containers import PdfArray
from pdfnaut.cos.parser import PdfParser
from pdfnaut.objects.actions import Action


def _is_outline_tree(item: PdfDictionary) -> bool:
    type_ = item.get("Type", PdfName(b""))
    if type_ == PdfName(b"Outlines"):
        return True

    if "Prev" not in item or "Next" not in item:
        return True

    return False


def flatten_outlines(item: OutlineItem | OutlineTree) -> Generator[OutlineItem, None, None]:
    """Yields the immediate children of the outline ``item``."""
    current = item.first
    while current is not None:
        yield current
        current = current.next


class OutlineItemFlags(IntFlag):
    """Flags specifying style characteristics for an outline item. See "Table 152 -
    Outline item flags" for details."""

    NULL = 0
    """No flags"""

    ITALIC = 1 << 0
    """Display the outline item text in italic."""

    BOLD = 1 << 1
    """Display the outline item text in bold."""


# TODO: proper type someday
Destination = PdfName | bytes | PdfHexString | PdfArray


@dictmodel()
class OutlineItem(PdfDictionary):
    """An outline item within the outline tree. See "Table 151 - Entries in an
    outline item dictionary" for details."""

    text: str = field("Title")
    """The display text for this outline item."""

    flags: OutlineItemFlags = field("F", default=OutlineItemFlags.NULL.value)
    """A set of bit flags describing characteristics of the outline item text."""

    @classmethod
    def from_dict(
        cls,
        mapping: PdfDictionary,
        *,
        pdf: PdfParser | None = None,
        indirect_ref: PdfReference | None = None,
    ) -> Self:
        item = cls("", pdf=pdf, indirect_ref=indirect_ref)
        item.data = mapping.data

        return item

    def __init__(
        self,
        text: str,
        flags: OutlineItemFlags = OutlineItemFlags.NULL,
        destination: Destination | None = None,
        action: Action | None = None,
        color: PdfArray[int | float] | None = None,
        *,
        pdf: PdfParser | None = None,
        indirect_ref: PdfReference | None = None,
    ) -> None:
        super().__init__()

        self.indirect_ref = indirect_ref
        self.pdf = pdf

        self.text = text
        self.flags = flags
        self.color = color
        self.destination = destination
        self.action = action

        self._cached_items: list[OutlineItem] = []

    @property
    def first(self) -> OutlineItem | None:
        """The first child item of the outline if any."""
        if "First" not in self:
            return

        return OutlineItem.from_dict(self["First"], pdf=self.pdf, indirect_ref=self.data["First"])

    @property
    def last(self) -> OutlineItem | None:
        """The last child item of the outline if any."""
        if "Last" not in self:
            return

        return OutlineItem.from_dict(self["Last"], pdf=self.pdf, indirect_ref=self.data["Last"])

    @property
    def previous(self) -> OutlineItem | None:
        """The previous item at the current outline level if any."""
        if "Prev" not in self:
            return

        return OutlineItem.from_dict(self["Prev"], pdf=self.pdf, indirect_ref=self.data["Prev"])

    @property
    def next(self) -> OutlineItem | None:
        """The next item at the current outline level if any."""
        if "Next" not in self:
            return

        return OutlineItem.from_dict(self["Next"], pdf=self.pdf, indirect_ref=self.data["Next"])

    @property
    def visible_items(self) -> int:
        """
        If the outline item is open, the number of visible descendent outline items.
        If the outline item is closed, a negative number representing the number of
        descendants that would be visible if the item were opened.
        If the outline item has no children, zero.
        """
        return self.get("Count", 0)

    @property
    def parent(self) -> OutlineItem | OutlineTree:
        """The parent outline item or tree containing this outline."""
        parent, parent_ref = self["Parent"], self.data["Parent"]
        assert isinstance(parent, PdfDictionary)

        if _is_outline_tree(parent):
            return OutlineTree(self.pdf, parent, parent_ref)

        return OutlineItem.from_dict(parent, pdf=self.pdf, indirect_ref=parent_ref)

    @property
    def color(self) -> PdfArray[int | float]:
        """The color that shall be used for the outline item text, as an array of RGB
        color components in the range 0 to 1."""
        if "C" not in self:
            return PdfArray([0, 0, 0])

        return self["C"]

    @color.setter
    def color(self, value: PdfArray[int | float] | None) -> None:
        if value is None:
            self.pop("C", None)
        else:
            self["C"] = value

    @property
    def destination(self) -> Destination | None:
        """The destination that shall be displayed when the item is activated. Either a
        named destination (a name or byte string) or an explicit destination (an array)."""
        if "Dest" not in self:
            return

        return self["Dest"]

    @destination.setter
    def destination(self, dest: Destination | None = None) -> None:
        if dest is None:
            self.pop("Dest", None)
        else:
            self["Dest"] = dest

    @property
    def action(self) -> Action | None:
        """The action that shall be triggered when the item is activated."""
        if "A" not in self:
            return

        return Action.from_dict(self["A"])

    @action.setter
    def action(self, act: Action | None) -> None:
        if act is None:
            self.pop("A", None)
        else:
            self["A"] = act

    @property
    def children(self) -> list[OutlineItem]:
        """The immediate children of the the outline item."""
        if not self._cached_items:
            self._cached_items = list(flatten_outlines(self))

        return self._cached_items

    def open(self) -> None:
        """If the item has children, opens the outline item and displays the immediate
        children (and its descendants if they are also visible)."""
        if not self.visible_items:
            return

        self["Count"] = len(self.children)

    def close(self) -> None:
        """If the item has children, closes the outline item and hides the immediate children."""
        if not self.visible_items:
            return

        self["Count"] = -len(self.children)


class OutlineTree(PdfDictionary):
    """The document outline tree containing a hierarchy of outline items that allow
    navigating throughout the document. See § 12.3.3 "Document outline" for details."""

    def __init__(
        self,
        pdf: PdfParser,
        tree: PdfDictionary,
        tree_ref: PdfReference,
    ) -> None:
        super().__init__()
        self.data = tree.data

        self._pdf = pdf
        self._tree = tree
        self._tree_ref = tree_ref

        self._cached_items: list[OutlineItem] = []

    @property
    def first(self) -> OutlineItem:
        """The first outline item in the tree."""
        return OutlineItem.from_dict(self["First"], pdf=self._pdf, indirect_ref=self.data["First"])

    @property
    def last(self) -> OutlineItem:
        """The last outline item in the tree."""
        return OutlineItem.from_dict(self["Last"], pdf=self._pdf, indirect_ref=self.data["Last"])

    @property
    def visible_items(self) -> int:
        """The total number of visible outline items at all levels of the tree."""
        return self.get("Count", 0)

    @property
    def children(self) -> list[OutlineItem]:
        """The immediate children of the outline tree."""
        if not self._cached_items:
            self._cached_items = list(flatten_outlines(self))

        return self._cached_items
