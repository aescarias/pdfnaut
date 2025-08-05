from __future__ import annotations

from collections.abc import Generator, Iterable, MutableSequence
from typing import Any, Iterator, cast, overload

from typing_extensions import Self

from pdfnaut.exceptions import PdfParseError

from .common.utils import clone_into_document, copy_object
from .cos.objects import PdfArray, PdfDictionary, PdfName, PdfReference
from .cos.parser import PdfParser
from .objects.page import Page


def flatten_pages(root: PdfDictionary) -> Generator[Page, None, None]:
    """Yields all :class:`.Page` objects within ``root`` and its descendants."""

    kids = cast(PdfArray, root["Kids"])

    for page_ref in cast(list[PdfReference], kids.data):
        page = cast(PdfDictionary, page_ref.get())

        type_ = cast(PdfName, page["Type"])
        if type_.value == b"Pages":
            yield from flatten_pages(page)
        elif type_.value == b"Page":
            yield Page.from_dict(page, indirect_ref=page_ref)


class PageList(MutableSequence[Page]):
    """A mutable sequence of the pages in a document.

    This class isn't designed to be constructed by a user. To access the page
    list of a PDF, use :attr:`.PdfDocument.pages`.
    """

    def __init__(
        self,
        pdf: PdfParser,
        root_tree: PdfDictionary,
        root_tree_ref: PdfReference,
    ) -> None:
        self._pdf = pdf
        self._root_tree = root_tree
        self._root_tree_ref = root_tree_ref
        self._indexed_page_cache = list(flatten_pages(self._root_tree))
        self._last_hash = hash(self._root_tree)

    def _update_on_hash(self) -> None:
        # process: if the page tree has changed, only replace the pages
        # in the indexed page cache that have also changed.

        if self._last_hash == hash(self._root_tree):
            return

        page_list: list[Page] = []

        for idx, page in enumerate(flatten_pages(self._root_tree)):
            if 0 <= idx < len(self._indexed_page_cache):
                # page in list, check if it is different.
                prev_page = self._indexed_page_cache[idx]
                if hash(prev_page) != hash(page):
                    page_list.append(page)
                else:
                    page_list.append(prev_page)
            else:
                # page not in list, simply append.
                page_list.append(page)

        self._indexed_page_cache = page_list

    def _get_indexed_pages(self) -> list[Page]:
        self._update_on_hash()
        return self._indexed_page_cache

    # * mutable sequence methods
    def __len__(self) -> int:
        return len(self._get_indexed_pages())

    def __contains__(self, value: object) -> bool:
        return value in self._get_indexed_pages()

    def __iter__(self) -> Iterator[Page]:
        return iter(self._get_indexed_pages())

    def __reversed__(self) -> Iterator[Page]:
        return reversed(self._get_indexed_pages())

    @overload
    def __getitem__(self, index: int) -> Page: ...

    @overload
    def __getitem__(self, index: slice) -> list[Page]: ...

    def __getitem__(self, index: int | slice) -> Page | list[Page]:
        return self._get_indexed_pages()[index]

    @overload
    def __setitem__(self, index: int, value: Page) -> None: ...

    @overload
    def __setitem__(self, index: slice, value: Iterable[Page]) -> None: ...

    def __setitem__(self, index: int | slice, value: Page | Iterable[Page]) -> None:
        if isinstance(index, slice):
            raise NotImplementedError

        assert isinstance(value, Page)

        result, _ = self._get_tree_with_index(self._root_tree, self._root_tree_ref, index)
        if result is None:
            raise IndexError("page tree assignment index out of range")

        tree, _, tree_idx = result

        value = self._add_page_to_obj_store(value)

        # delete the page being replaced from the object store
        replacing_ref = tree["Kids"].data[tree_idx]
        self._pdf.objects.delete(replacing_ref.object_number)
        self._indexed_page_cache[index].indirect_ref = None

        # set the page
        tree["Kids"][tree_idx] = value.indirect_ref
        self._indexed_page_cache[index] = value

    def __delitem__(self, index: int | slice) -> None:
        if isinstance(index, slice):
            raise NotImplementedError

        self.pop(index)

    def __iadd__(self, values: Iterable[Page]) -> Self:
        self.extend(values)
        return self

    def index(self, value: Any, start: int = 0, stop: int = ...) -> int:
        """Returns the index at which page ``value`` was first found in the
        range of ``start`` included to ``stop`` excluded."""
        return self._get_indexed_pages().index(value, start, stop)

    def count(self, value: Any) -> int:
        """Returns the amount of times page ``value`` appears in the page list."""
        return self._get_indexed_pages().count(value)

    def insert(self, index: int, value: Page) -> None:
        """Inserts a page ``value`` at ``index``. ``index`` is the index of
        the page before which to insert.

        When inserting, the page object is copied into the page list.

        The object identity of the output shall match the identity of the input page.
        The input page shall receive the indirect reference of the inserted page.

        .. note::
            When adding a page belonging to a different document, the page will likely
            refer to resources that are part of the document such as fonts, images,
            and annotations.

            Some of these resources cannot be reliably copied and so it is possible
            that they're not added to the document, in which case, the references of
            such resources are simply marked null.

            Annotations that point to destinations not within the page will be preserved
            but not in working order. Form objects will not be copied at all.
        """
        if index < -len(self):
            index = 0
        elif index >= len(self):
            return self._append_pages_to_tree([value])
        else:
            index = self._pos_idx_of(index)

        inserting_page = self._add_page_to_obj_store(value)

        if self._get_indexed_pages():
            # document has pages, traverse the tree and insert at location
            result, _ = self._get_tree_with_index(self._root_tree, self._root_tree_ref, index)
        else:
            # document has no pages, insert in root page tree
            result = (self._root_tree, self._root_tree_ref, index)

        # This should always be the case but, for good measure, we check it.
        assert result is not None, f"expected tree for index {index}."

        tree, tree_ref, tree_idx = result

        self._insert_page_into_tree(inserting_page, tree_idx, tree=tree, tree_ref=tree_ref)
        self._indexed_page_cache.insert(index, value)

    def append(self, value: Page) -> None:
        """Appends a page ``value`` to the page list.

        If appending a page from a different document, please refer to the note in
        :meth:`PageList.insert` for additional considerations.
        """
        self.insert(len(self._get_indexed_pages()), value)

    def clear(self) -> None:
        raise NotImplementedError

    def reverse(self) -> None:
        raise NotImplementedError

    def extend(self, values: Iterable[Page]) -> None:
        """Appends a list of pages ``values`` into the page list.

        When extending, all pages will be copied and inserted into the last page
        tree within the page list.

        If any of the pages belong to a different document, please refer to the note in
        :meth:`PageList.insert` for additional considerations.
        """
        self._append_pages_to_tree(values)

    def pop(self, index: int = -1) -> Page:
        """Removes the page at ``index``.

        Only the page object is removed from the document and its reference is
        invalidated. The resources used by the page are not removed as they may
        be used later on in other pages.

        Raises:
            IndexError: The page list is empty or the index does not exist.

        Returns:
            Page: The page object that was popped.
        """
        index = self._pos_idx_of(index)

        if self._get_indexed_pages():
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
        output = self._indexed_page_cache.pop(index)

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
        index = self.index(value)
        value.indirect_ref = None

        self.pop(index)

    # * helper methods
    def _pos_idx_of(self, index: int) -> int:
        # positive index is within 0 and len(self), both inclusive
        # if index < 0, index = len(self) - abs(index)

        if index >= 0:
            return min(index, len(self))

        return len(self) - abs(index)

    def _add_page_to_obj_store(self, page: Page) -> Page:
        if page.indirect_ref is not None:
            # page has an indirect ref, assume page comes from different
            # document and create copy.
            added_page = clone_into_document(self._pdf, page, ignore_keys=["Parent"])
        else:
            # no indirect reference, assume new page and create copy.
            added_page = copy_object(page)

        added_page = cast(PdfDictionary, added_page)
        added_page.pop("Parent", None)

        page_ref = self._pdf.objects.add(added_page)
        added_page = Page.from_dict(added_page, indirect_ref=page_ref)

        # only set the reference if the page has none.
        if page.indirect_ref is None:
            page.indirect_ref = page_ref
            page.data = added_page.data
            return page

        return added_page

    def _insert_page_into_tree(
        self, page: Page, tree_index: int, *, tree: PdfDictionary, tree_ref: PdfReference
    ) -> None:
        if page.indirect_ref is None:
            raise ValueError("Page has no indirect reference assigned to it.")

        tree["Kids"].insert(tree_index, page.indirect_ref)
        tree["Count"] += 1

        page["Parent"] = tree_ref

        parent = tree
        while (parent := parent.get("Parent")) is not None:
            parent["Count"] += 1

    def _append_pages_to_tree(self, values: Iterable[Page]) -> None:
        last_tree, last_tree_ref = self._get_last_tree(self._root_tree, self._root_tree_ref)

        for value in values:
            inserting_page = self._add_page_to_obj_store(value)

            self._insert_page_into_tree(
                inserting_page, len(last_tree["Kids"]), tree=last_tree, tree_ref=last_tree_ref
            )
            self._indexed_page_cache.insert(len(self._indexed_page_cache), value)

    def _delete_page_in_tree(self, tree_index: int, tree: PdfDictionary) -> None:
        tree.data["Kids"].pop(tree_index)

        tree["Count"] -= 1

        parent = tree
        while (parent := parent.get("Parent")) is not None:
            parent["Count"] -= 1

    def _get_last_tree(
        self, root: PdfDictionary, root_ref: PdfReference
    ) -> tuple[PdfDictionary, PdfReference]:
        kids = cast(PdfArray[PdfReference], root["Kids"]).data
        result = (root, root_ref)

        for page_ref in kids:
            page = page_ref.get()
            type_ = cast(PdfName, page["Type"])

            if type_.value == b"Pages":
                result = self._get_last_tree(page, page_ref)

        return result

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
