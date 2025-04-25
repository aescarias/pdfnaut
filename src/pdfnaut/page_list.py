from __future__ import annotations

from collections.abc import Iterable, MutableSequence
from typing import Any, Iterator, cast, overload

from typing_extensions import Self

from .common.utils import renumber_references
from .cos.objects import PdfArray, PdfDictionary, PdfName, PdfReference
from .cos.parser import PdfParser
from .objects.page import Page


class PageList(MutableSequence[Page]):
    """A mutable sequence of the pages in a document."""

    def __init__(
        self,
        pdf: PdfParser,
        root_tree: PdfDictionary,
        root_tree_ref: PdfReference,
        indexed_pages: list[Page],
    ) -> None:
        self._pdf = pdf
        self._root_tree = root_tree
        self._root_tree_ref = root_tree_ref
        self._indexed_pages = indexed_pages

    # * mutable sequence methods
    def __len__(self) -> int:
        return len(self._indexed_pages)

    def __contains__(self, value: object) -> bool:
        return value in self._indexed_pages

    def __iter__(self) -> Iterator[Page]:
        return iter(self._indexed_pages)

    def __reversed__(self) -> Iterator[Page]:
        return reversed(self._indexed_pages)

    @overload
    def __getitem__(self, index: int) -> Page: ...

    @overload
    def __getitem__(self, index: slice) -> list[Page]: ...

    def __getitem__(self, index: int | slice) -> Page | list[Page]:
        return self._indexed_pages[index]

    @overload
    def __setitem__(self, index: int, value: Page) -> None: ...

    @overload
    def __setitem__(self, index: slice, value: Iterable[Page]) -> None: ...

    def __setitem__(self, index: int | slice, value: Page | Iterable[Page]) -> None:
        if isinstance(index, slice):
            raise NotImplementedError

        result, _ = self._get_tree_with_index(self._root_tree, self._root_tree_ref, index)
        if result is None:
            raise IndexError("Assignment index out of range.")

        tree, _, tree_idx = result

        # check whether this page comes from another document
        obj = None
        is_ref_not_in_doc = (
            value.indirect_ref is None
            or (obj := self._pdf.objects.get(value.indirect_ref.object_number)) is None
        )
        is_object_equal = obj is not None and hasattr(obj, "data") and obj.data is value.data

        if is_ref_not_in_doc or not is_object_equal:
            value = self._add_page_to_obj_store(value)

        # delete the page being replaced from the object store
        replacing_ref = tree["Kids"].data[tree_idx]
        self._pdf.objects.delete(replacing_ref.object_number)

        # set the page
        tree["Kids"][tree_idx] = value.indirect_ref
        self._indexed_pages[index] = value

    def __delitem__(self, index: int | slice) -> None:
        if isinstance(index, slice):
            raise NotImplementedError

        self.pop(index)

    def __iadd__(self, values: Iterable[Page]) -> Self:
        raise NotImplementedError

    def index(self, value: Any, start: int = 0, stop: int = ...) -> int:
        return self._indexed_pages.index(value, start, stop)

    def count(self, value: Any) -> int:
        return self._indexed_pages.count(value)

    def insert(self, index: int, value: Page) -> None:
        """Inserts a page ``value`` at ``index``. ``index`` is the index of
        the page before which to insert.

        When inserting, the page object is copied into the page list.
        """

        index = self._pos_idx_of(index)
        inserting_page = self._add_page_to_obj_store(value)

        if self._indexed_pages:
            # document has pages, traverse the tree and insert at location
            result, _ = self._get_tree_with_index(self._root_tree, self._root_tree_ref, index)
        else:
            result = None

        if result is not None:
            tree, tree_ref, tree_idx = result
        else:
            tree = self._root_tree
            tree_ref = self._root_tree_ref
            tree_idx = index

        self._insert_page_into_tree(inserting_page, tree_idx, tree=tree, tree_ref=tree_ref)
        self._indexed_pages.insert(index, value)

    def append(self, value: Page) -> None:
        """Appends a page ``value`` to the page list."""
        self.insert(len(self._indexed_pages), value)

    def clear(self) -> None:
        raise NotImplementedError

    def reverse(self) -> None:
        raise NotImplementedError

    def extend(self, values: Iterable[Page]) -> None:
        raise NotImplementedError

    def pop(self, index: int = -1) -> Page:
        """Removes the page at ``index``.

        Only the page object is removed from the document. The resources used by
        the page are left intact as they may be used later on in other pages.

        Raises:
            IndexError: The page list is empty or the index does not exist.

        Returns:
            Page: The page object that was popped.
        """

        index = self._pos_idx_of(index)

        if self._indexed_pages:
            # document has pages, traverse the tree and insert at location
            result, _ = self._get_tree_with_index(self._root_tree, self._root_tree_ref, index)
        else:
            result = None

        if result is not None:
            tree, _, tree_idx = result
        else:
            tree = self._root_tree
            tree_idx = index

        # delete the page from the tree
        self._delete_page_in_tree(tree_idx, tree)
        output = self._indexed_pages.pop(index)

        # delete the page from the object store
        if output.indirect_ref is not None:
            self._pdf.objects.delete(output.indirect_ref.object_number)
            output.indirect_ref = None

        return output

    def remove(self, value: Page) -> None:
        """Removes the first occurrence of page ``value`` in the document.

        Raises:
            IndexError: The page list is empty or the page is not in this document.
        """
        index = self._indexed_pages.index(value)
        self.pop(index)

    # * helper methods
    def _pos_idx_of(self, index: int) -> int:
        # positive index is within 0 and len(self), both inclusive
        # if index < 0, index = len(self) - abs(index)

        if index >= 0:
            return min(index, len(self))

        return len(self) - abs(index)

    def _add_page_to_obj_store(self, page: Page) -> Page:
        # Ensure that the page has no parent. having one will cause a
        # reference loop and the page will be re-parented anyways.

        if "Parent" in page:
            page.pop("Parent")

        if page.indirect_ref is not None:
            # page has an indirect ref, assume page comes from different
            # document and create copy.
            added_page, refs = renumber_references(
                PdfDictionary(page.data.copy()),
                self._pdf.get_object,
                start=self._pdf.objects.get_next_ref().object_number,
            )

            for num, ref in refs.items():
                self._pdf.objects[num] = ref
        else:
            # no indirect reference, assume new page and create copy.
            added_page = PdfDictionary(page.data.copy())

        page_ref = self._pdf.objects.add(added_page)

        added_page = Page.from_dict(added_page, indirect_ref=page_ref)
        return added_page

    def _insert_page_into_tree(
        self, page: Page, tree_index: int, *, tree: PdfDictionary, tree_ref: PdfReference
    ) -> None:
        if page.indirect_ref is None:
            raise ValueError("Page has no indirect reference assigned.")

        tree["Kids"].insert(tree_index, page.indirect_ref)
        tree["Count"] += 1

        page["Parent"] = tree_ref

        parent = tree
        while (parent := parent.get("Parent")) is not None:
            parent["Count"] += 1

    def _delete_page_in_tree(self, tree_index: int, tree: PdfDictionary) -> None:
        tree.data["Kids"].pop(tree_index)

        tree["Count"] -= 1

        parent = tree
        while (parent := parent.get("Parent")) is not None:
            parent["Count"] -= 1

    def _get_tree_with_index(
        self, root: PdfDictionary, root_ref: PdfReference, index: int
    ) -> tuple[tuple[PdfDictionary, PdfReference, int] | None, int]:
        kids = cast(PdfArray[PdfReference], root["Kids"].data)

        for tree_index, page_ref in enumerate(kids):
            page = page_ref.get()

            type_ = cast(PdfName, page["Type"])

            if type_.value == b"Pages":  # intermediate node
                result, index = self._get_tree_with_index(page, page_ref, index)
                if result is not None:
                    return (result, index)
            elif type_.value == b"Page":  # page node
                if index <= 0:
                    return (root, root_ref, tree_index), index

                index -= 1

        return (None, index)
