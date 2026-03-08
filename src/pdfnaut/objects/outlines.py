from __future__ import annotations

import sys
from collections.abc import Generator, Iterable, Iterator, MutableSequence
from enum import IntFlag
from typing import Any, cast, overload

from typing_extensions import Self

from pdfnaut.common.dictmodels import dictmodel, field
from pdfnaut.cos.objects import PdfDictionary
from pdfnaut.cos.objects.base import PdfName, PdfReference
from pdfnaut.cos.objects.containers import PdfArray
from pdfnaut.cos.parser import PdfParser
from pdfnaut.objects.actions import Action, action_into
from pdfnaut.objects.destinations import Destination, DestType, NamedDestination


def is_outline_tree(item: PdfDictionary) -> bool:
    """Reports whether a dictionary ``item`` is an outline tree."""
    type_ = item.get("Type", PdfName(b""))
    if type_ == PdfName(b"Outlines"):
        return True

    # these keys should only appear in an outline item
    item_keys = ["Title", "Parent", "Prev", "Next", "Dest", "A", "SE", "C", "F"]
    for key in item_keys:
        if key in item:
            return False

    return True


def get_count(item: OutlineTree | OutlineItem) -> int:
    """Calculates the count of visible items within an outline ``item`` or tree."""
    count = len(item.children)
    for child in item.children:
        if child.visible_items >= 0:
            count += get_count(child)

    return count


def update_ancestor_count(item: OutlineTree | OutlineItem) -> None:
    """Recalculates the visible item count for the outline ``item``, reflecting
    this count in the ancestors."""
    new_count = get_count(item)

    if cast(int, item.get("Count", 0)) < 0:
        item["Count"] = -new_count
    else:
        item["Count"] = new_count

    if isinstance(item, OutlineItem):
        update_ancestor_count(item.parent)


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


@dictmodel
class OutlineItem(PdfDictionary):
    """An outline item within the outline tree.

    See ISO 32000-2:2020 "Table 151 - Entries in an outline item dictionary"
    for details."""

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
        destination: DestType | None = None,
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

        self._cached_items: OutlineList | None = None

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
        - If the outline item is open, the number of visible descendent outline items.
        - If the outline item is closed, a negative number representing the number of
          descendants that would be visible if the item were opened.
        - If the outline item has no children, zero.
        """
        return self.get("Count", 0)

    @property
    def parent(self) -> OutlineItem | OutlineTree:
        """The parent outline item or tree containing this outline."""
        parent, parent_ref = self["Parent"], self.data["Parent"]
        assert isinstance(parent, PdfDictionary)

        if is_outline_tree(parent):
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
    def destination(self) -> DestType | None:
        """The destination that shall be displayed when the item is activated, either
        a named destination (a name or byte string) or an explicit destination
        (a :class:`Destination` object)."""

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
        elif isinstance(dest, Destination):
            self["Dest"] = PdfArray(dest.data)
        else:
            self["Dest"] = dest

    @property
    def action(self) -> Action | None:
        """The action that shall be triggered when the item is activated."""
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
    def children(self) -> OutlineList:
        """The immediate children of the outline item."""
        if not self._cached_items:
            self._cached_items = OutlineList(self.pdf, self)

        return self._cached_items

    def open(self) -> None:
        """If the item has children, opens the outline item and displays the immediate
        children (and its descendants if they are also visible)."""
        if not self.visible_items:
            return

        self["Count"] = get_count(self)
        update_ancestor_count(self)

    def close(self) -> None:
        """If the item has children, closes the outline item and hides the immediate children."""
        if not self.visible_items:
            return

        self["Count"] = -get_count(self)
        update_ancestor_count(self)


class OutlineTree(PdfDictionary):
    """The document outline tree containing a hierarchy of outline items that allow
    navigating throughout the document.

    See ISO 32000-2:2020 § 12.3.3 "Document outline" for details.

    .. warning::
        This class is not designed to be constructed by a user. To add an outline tree
        to a document, :meth:`PdfDocument.new_outline` should be used.
    """

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

        self._cached_items: OutlineList | None = None

    @property
    def first(self) -> OutlineItem | None:
        """The first outline item in the tree."""
        if "First" not in self:
            return

        return OutlineItem.from_dict(self["First"], pdf=self._pdf, indirect_ref=self.data["First"])

    @property
    def last(self) -> OutlineItem | None:
        """The last outline item in the tree."""
        if "Last" not in self:
            return

        return OutlineItem.from_dict(self["Last"], pdf=self._pdf, indirect_ref=self.data["Last"])

    @property
    def visible_items(self) -> int:
        """The total number of visible outline items at all levels of the tree."""
        return self.get("Count", 0)

    @property
    def children(self) -> OutlineList:
        """The immediate children of the outline tree."""
        if not self._cached_items:
            self._cached_items = OutlineList(self._pdf, self)

        return self._cached_items

    def open(self) -> None:
        """If the item has children, opens all outline items within the tree."""
        for item in self.children:
            item.open()

    def close(self) -> None:
        """If the item has children, closes all outline items within the tree."""
        for item in self.children:
            item.close()


class OutlineList(MutableSequence[OutlineItem]):
    """The outline list representing the children of an outline tree or item.

    .. warning::
        This class is not designed to be constructed by a user. Using the outline
        list should be done via :class:`OutlineTree` and :class:`OutlineItem`.
    """

    def __init__(
        self,
        pdf: PdfParser,
        parent: OutlineItem | OutlineTree,
    ) -> None:
        super().__init__()

        self._pdf = pdf
        self._parent = parent
        self._last_hash = hash(self._parent)
        self._cached_items = self._get_cached_items()

    def _update_on_hash(self) -> None:
        if self._last_hash == hash(self._parent):
            return

        outline: list[OutlineItem] = []

        for idx, item in enumerate(flatten_outlines(self._parent)):
            if 0 <= idx < len(self._cached_items):
                # item in list, check if it is different.
                prev_item = self._cached_items[idx]
                if hash(prev_item) != hash(item):
                    outline.append(item)
                else:
                    outline.append(prev_item)
            else:
                # item not in list, simply append.
                outline.append(item)

        self._last_hash = hash(self._parent)
        self._cached_items = outline

    def _get_cached_items(self) -> list[OutlineItem]:
        self._update_on_hash()
        return list(flatten_outlines(self._parent))

    def __repr__(self) -> str:
        return repr(self._cached_items)

    def __len__(self) -> int:
        return len(self._get_cached_items())

    def __contains__(self, value: object) -> bool:
        return value in self._get_cached_items()

    def __iter__(self) -> Iterator[OutlineItem]:
        return iter(self._get_cached_items())

    def __reversed__(self) -> Iterator[OutlineItem]:
        return reversed(self._get_cached_items())

    @overload
    def __getitem__(self, index: int) -> OutlineItem: ...

    @overload
    def __getitem__(self, index: slice) -> list[OutlineItem]: ...

    def __getitem__(self, index: int | slice) -> OutlineItem | list[OutlineItem]:
        return self._get_cached_items()[index]

    @overload
    def __setitem__(self, index: int, value: OutlineItem) -> None: ...

    @overload
    def __setitem__(self, index: slice, value: Iterable[OutlineItem]) -> None: ...

    def __setitem__(self, index: int | slice, value: OutlineItem | Iterable[OutlineItem]) -> None:
        if isinstance(index, slice):
            raise NotImplementedError

        assert isinstance(value, OutlineItem)

        self.pop(index)
        self.insert(index, value)

    def __delitem__(self, index: int | slice) -> None:
        if isinstance(index, slice):
            raise NotImplementedError

        self.pop(index)

    def __iadd__(self, values: Iterable[OutlineItem]) -> Self:
        raise NotImplementedError

    def insert(self, index: int, value: OutlineItem) -> None:
        if self._parent.first is None and self._parent.last is None:
            # no items, simply append
            self.append(value)
            return

        if self._pdf is None:
            raise ValueError("outline must be in document")

        item_ref = self._pdf.objects.add(it := PdfDictionary(value.data))
        if value.pdf is None:
            value.pdf = self._pdf
            value.indirect_ref = item_ref
            value.data = it.data

        index = self._pos_idx_of(index)
        current = self._cached_items[min(index, len(self._cached_items) - 1)]

        if index == len(self._cached_items):
            current["Next"] = value.indirect_ref
            value["Prev"] = current.indirect_ref
            current["Parent"]["Last"] = value.indirect_ref
        elif index == 0:
            value["Next"] = current.indirect_ref
            current["Prev"] = value.indirect_ref
            current["Parent"]["First"] = value.indirect_ref
        else:
            prev_item = self._cached_items[index - 1]
            prev_item["Next"] = value.indirect_ref
            value["Next"] = current.indirect_ref
            current["Prev"] = value.indirect_ref

        if isinstance(p := self._parent, OutlineTree):
            value["Parent"] = p._tree_ref
        else:
            value["Parent"] = p.indirect_ref

        self._cached_items.insert(index, value)
        update_ancestor_count(self._parent)

    def index(self, value: Any, start: int = 0, stop: int = sys.maxsize) -> int:
        """Returns the index at which outline item ``value`` was first found in the
        range of ``start`` included to ``stop`` excluded."""
        return self._get_cached_items().index(value, start, stop)

    def count(self, value: Any) -> int:
        """Returns the amount of times outline item ``value`` appears in the page list."""
        return self._get_cached_items().count(value)

    def append(self, value: OutlineItem) -> None:
        """Appends an outline item ``value`` to the immediate children of the list."""
        if self._pdf is None:
            raise ValueError("outline must be in document")

        item_ref = self._pdf.objects.add(it := PdfDictionary(value.data))
        if value.pdf is None:
            value.pdf = self._pdf
            value.indirect_ref = item_ref
            value.data = it.data

        if self._parent.first is None and self._parent.last is None:
            # no top-level items
            self._parent["First"] = item_ref
            self._parent["Last"] = item_ref
        else:
            # link the new item to the previous last item
            self._parent["Last"]["Next"] = item_ref
            value["Prev"] = self._parent.data["Last"]
            # set the new last item
            self._parent["Last"] = item_ref

        if isinstance(p := self._parent, OutlineTree):
            value["Parent"] = p._tree_ref
        else:
            value["Parent"] = p.indirect_ref

        self._cached_items.append(value)
        update_ancestor_count(self._parent)

    def clear(self) -> None:
        """Removes all children in the outline item."""
        while self._cached_items:
            self.pop()

    def reverse(self) -> None:
        raise NotImplementedError

    def extend(self, values: Iterable[OutlineItem]) -> None:
        """Appends a list of outline items ``values`` to the end of the outline list."""
        for value in values:
            self.append(value)

    def pop(self, index: int = -1) -> OutlineItem:
        """Removes the outline item at ``index`` from the immediate children
        of this outline list.

        Raises:
            IndexError: The outline list is empty or the item is not in the list.

        Returns:
            OutlineItem: The outline item that was popped.
        """
        index = self._pos_idx_of(index)
        item = self._cached_items[index]

        if index == len(self._cached_items) - 1:
            new_last = self._cached_items[index - 1]
            new_last.pop("Next", None)

            item["Parent"]["Last"] = new_last.indirect_ref
        elif index == 0:
            new_first = self._cached_items[index + 1]
            new_first.pop("Prev", None)

            item["Parent"]["First"] = new_first.indirect_ref
        else:
            next_item = self._cached_items[index + 1]
            prev_item = self._cached_items[index - 1]

            prev_item["Next"] = next_item.indirect_ref

        self._cached_items.pop(index)

        if not self._cached_items:
            # pop removed all items
            item["Parent"].pop("First", None)
            item["Parent"].pop("Last", None)

        update_ancestor_count(self._parent)

        if item.indirect_ref is not None:
            self._pdf.objects.delete(item.indirect_ref.object_number)
            item.indirect_ref = None

        item["Parent"] = None
        return item

    def remove(self, value: OutlineItem) -> None:
        """Removes the first occurrence of outline item ``value`` in the immediate
        children of this tree.

        Raises:
            IndexError: The outline list is empty or the item is not in the list.
        """
        index = self.index(value)
        self.pop(index)

    def _pos_idx_of(self, index: int) -> int:
        # positive index is within 0 and len(self), both inclusive
        # if index < 0, index = len(self) - abs(index)

        if index >= 0:
            return min(index, len(self))

        return len(self) - abs(index)
