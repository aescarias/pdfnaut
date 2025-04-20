from __future__ import annotations

from collections.abc import Iterable, MutableSequence
from typing import Generator, cast, overload

from pdfnaut.common.utils import renumber_references
from pdfnaut.cos.objects.base import parse_text_string
from pdfnaut.cos.objects.xref import FreeXRefEntry, InUseXRefEntry, PdfXRefEntry
from pdfnaut.cos.serializer import PdfSerializer
from pdfnaut.objects.catalog import PageLayout, PageMode, UserAccessPermissions
from pdfnaut.objects.xmp import XmpMetadata

from .cos.objects import (
    PdfArray,
    PdfDictionary,
    PdfHexString,
    PdfName,
    PdfReference,
    PdfStream,
)
from .cos.parser import FreeObject, PdfParser, PermsAcquired
from .objects.page import Page
from .objects.trailer import Info


class PdfDocument(PdfParser):
    """A high-level interface over :class:`~.PdfParser`.

    PDF authors who want to work with a document in a high-level way should
    use this interface over ``PdfParser``.
    """

    @classmethod
    def from_filename(cls, path: str, *, strict: bool = False) -> PdfDocument:
        """Loads a PDF document from a file ``path``."""
        with open(path, "rb") as fp:
            return PdfDocument(fp.read(), strict=strict)

    @classmethod
    def new(cls) -> PdfDocument:
        """Creates a blank PDF document."""

        builder = PdfSerializer()
        builder.write_header("2.0")

        builder.objects[(1, 0)] = PdfDictionary(
            {"Type": PdfName(b"Catalog"), "Pages": PdfReference(2, 0)}
        )
        builder.objects[(2, 0)] = PdfDictionary(
            {"Type": PdfName(b"Pages"), "Kids": PdfArray(), "Count": 0}
        )

        section: list[tuple[int, PdfXRefEntry]] = [(0, FreeXRefEntry(0, 65535))]

        for (obj_num, gen_num), item in builder.objects.items():
            offset = builder.write_object((obj_num, gen_num), item)
            section.append((obj_num, InUseXRefEntry(offset, gen_num)))

        subsections = builder.generate_xref_section(section)

        startxref = builder.write_standard_xref_section(subsections)

        builder.write_trailer(
            PdfDictionary({"Size": subsections[0].count, "Root": PdfReference(1, 0)}), startxref
        )

        builder.write_eof()

        return PdfDocument(builder.content)

    def __init__(self, data: bytes, *, strict: bool = False) -> None:
        super().__init__(data, strict=strict)

        self.parse()

        self.access_level = PermsAcquired.OWNER
        """The current access level of the document, specified as a value from the
        :class:`.PermsAcquired` enum.

        - Owner (2): Full access to the document. If the document is not encrypted, \
        this is the default value.
        - User (1): Access to the document under restrictions.
        - None (0): Document is currently encrypted.
        """

        # files under permissions usually use an empty string as a password
        if self.has_encryption:
            self.access_level = self.decrypt("")

    @property
    def has_encryption(self) -> bool:
        """Whether this document includes encryption."""
        return "Encrypt" in self.trailer

    @property
    def catalog(self) -> PdfDictionary:
        """The root of the document's object hierarchy, including references to pages,
        outlines, destinations, and other core elements of a PDF document.

        For details on the contents of the catalog, see § 7.7.2 Document Catalog.
        """
        return cast(PdfDictionary, self.trailer["Root"])

    @catalog.setter
    def catalog(self, value: PdfDictionary) -> None:
        root_ref = cast(PdfReference, self.trailer.data["Root"])
        self.objects[root_ref.object_number] = value

    @property
    def doc_info(self) -> Info | None:
        """The ``Info`` entry in the catalog which includes document-level information
        described in § 14.3.3 Document information dictionary.

        Some documents may specify a metadata stream rather than a DocInfo dictionary.
        Such metadata can be accessed using :attr:`.PdfDocument.xmp_info`.

        PDF 2.0 deprecates all keys of the DocInfo dictionary except for ``CreationDate``
        and ``ModDate``.
        """
        if "Info" not in self.trailer:
            return

        return Info.from_dict(cast(PdfDictionary, self.trailer["Info"]))

    @doc_info.setter
    def doc_info(self, value: Info | None) -> None:
        info_ref = cast("PdfReference | None", self.trailer.data.get("Info"))

        # A new docinfo object will be created
        if info_ref is None and value is not None:
            new_object = max(self.objects) + 1
            self.objects[new_object] = PdfDictionary(**value.data)
            self.trailer.data["Info"] = PdfReference(new_object, 0).with_resolver(self.get_object)
        # A docinfo object will be set
        elif info_ref and isinstance(value, Info):
            self.objects[info_ref.object_number] = PdfDictionary(**value.data)
        # A docinfo object will be removed
        elif info_ref:
            self.objects[info_ref.object_number] = FreeObject()
            self.trailer.data.pop("Info", None)

    @property
    def pdf_version(self) -> str:
        """The version of the PDF standard used in this document.

        The version of a PDF may be identified by either its header or the Version entry
        in the catalog. If the Version entry is absent or the header specifies a later
        version, the header version is returned. Otherwise, the Version entry is returned.
        """
        header_version = self.header_version
        catalog_version = cast("PdfName | None", self.catalog.get("Version"))

        if not catalog_version:
            return header_version

        return max((header_version, catalog_version.value.decode()))

    @property
    def xmp_info(self) -> XmpMetadata | None:
        """The Metadata entry of the catalog which includes document-level metadata
        stored as XMP."""
        if "Metadata" not in self.catalog:
            return

        stm = cast(PdfStream, self.catalog["Metadata"])

        return XmpMetadata(stm)

    @xmp_info.setter
    def xmp_info(self, xmp: XmpMetadata | None) -> None:
        metadata_ref = cast("PdfReference | None", self.catalog.data.get("Metadata"))

        # A new metadata object will be created
        if metadata_ref is None and xmp is not None:
            self.catalog["Metadata"] = self.objects.add(xmp.stream)
        # A metadata object will be set
        elif metadata_ref and isinstance(xmp, XmpMetadata):
            self.objects[metadata_ref.object_number] = xmp.stream
        # A metadata object will be removed
        elif metadata_ref:
            self.objects.delete(metadata_ref.object_number)
            self.catalog.pop("Metadata", None)

    @property
    def page_tree(self) -> PdfDictionary:
        """The document's page tree. See "§ 7.7.3 Page Tree" for details.

        For iterating over the pages of a PDF, prefer :attr:`.PdfDocument.flattened_pages`.
        """
        return cast(PdfDictionary, self.catalog["Pages"])

    @property
    def outline_tree(self) -> PdfDictionary | None:
        """The document's outline tree including what is commonly referred to as
        bookmarks. See "§ 12.3.3 Document Outline" for details.
        """
        return cast("PdfDictionary | None", self.catalog.get("Outlines"))

    def decrypt(self, password: str) -> PermsAcquired:
        self.access_level = super().decrypt(password)
        return self.access_level

    def _flatten_pages(self, root: PdfDictionary | None = None) -> Generator[Page, None, None]:
        """Yields all pages within ``root`` and its descendants."""

        for page_ref in cast(list[PdfReference], root["Kids"].data):
            page = cast(PdfDictionary, page_ref.get())

            type_ = cast(PdfName, page["Type"])
            if type_.value == b"Pages":
                yield from self._flatten_pages(page)
            elif type_.value == b"Page":
                yield Page.from_dict(page, indirect_ref=page_ref)

    @property
    def flattened_pages(self) -> Generator[Page, None, None]:
        """A generator suitable for iterating over the pages of a PDF."""
        return self._flatten_pages()

    @property
    def page_layout(self) -> PageLayout:
        """The page layout to use when opening the document. May be one of the following
        values:

        - SinglePage: Display one page at a time (default).
        - OneColumn: Display the pages in one column.
        - TwoColumnLeft: Display the pages in two columns, with odd-numbered pages
          on the left.
        - TwoColumnRight: Display the pages in two columns, with odd-numbered pages
          on the right.
        - TwoPageLeft: Display the pages two at a time, with odd-numbered
          pages on the left (PDF 1.5).
        - TwoPageRight: Display the pages two at a time, with odd-numbered
          pages on the right (PDF 1.5).
        """
        if "PageLayout" not in self.catalog:
            return "SinglePage"

        return cast(PageLayout, cast(PdfName, self.catalog["PageLayout"]).value.decode())

    @property
    def page_mode(self) -> PageMode:
        """Value specifying how the document shall be displayed when opened:

        - UseNone: Neither document outline nor thumbnail images visible (default).
        - UseOutlines: Document outline visible.
        - UseThumbs: Thumbnail images visible.
        - FullScreen: Full-screen mode, with no menu bar, window controls, or any
          other window visible.
        - UseOC: Optional content group panel visible (PDF 1.5).
        - UseAttachments: Attachments panel visible (PDF 1.6).
        """
        if "PageMode" not in self.catalog:
            return "UseNone"

        return cast(PageMode, cast(PdfName, self.catalog["PageMode"]).value.decode())

    @property
    def language(self) -> str | None:
        """A language identifier that shall specify the natural language for all text in
        the document except where overridden by language specifications for structure
        elements or marked content (see "§ 14.9.2 Natural language specification" for details).

        If this entry is absent, the language shall be considered unknown.
        """

        if "Lang" not in self.catalog:
            return

        return parse_text_string(cast("PdfHexString | bytes", self.catalog["Lang"]))

    @property
    def access_permissions(self) -> UserAccessPermissions | None:
        """User access permissions relating to the document.

        See "Table 22: User Access Permissions" and :class:`.UserAccessPermissions`
        for details.
        """
        if not self.has_encryption:
            return

        encrypt_dict = cast(PdfDictionary, self.trailer["Encrypt"])

        if (perms := encrypt_dict.get("P")) is not None:
            return UserAccessPermissions(perms)

    @property
    def pages(self) -> PageList:
        """The page list in the document."""

        if not self.access_level:
            raise PermissionError("Cannot read pages of encrypted document.")

        pages = list(self._flatten_pages(self.page_tree))
        return PageList(self, self.page_tree, pages)


class PageList(MutableSequence[Page]):
    """A mutable sequence of the pages in a document."""

    def __init__(self, pdf: PdfParser, root_tree: PdfDictionary, indexed_pages: list[Page]) -> None:
        self._pdf = pdf
        self._root_tree = root_tree
        self._indexed_pages = indexed_pages

    def __len__(self) -> int:
        return len(self._indexed_pages)

    @overload
    def __getitem__(self, index: int) -> Page: ...

    @overload
    def __getitem__(self, index: slice) -> PageList: ...

    def __getitem__(self, index: int | slice) -> Page | PageList:
        if isinstance(index, slice):
            return PageList(self._pdf, self._root_tree, self._indexed_pages[index])

        page = self._indexed_pages[index]
        return page

    def __delitem__(self, index: int | slice) -> None:
        # TODO: implement deletion
        raise NotImplementedError

    @overload
    def __setitem__(self, index: int, value: Page) -> None: ...

    @overload
    def __setitem__(self, index: slice, value: Iterable[Page]) -> None: ...

    def __setitem__(self, index: int | slice, value: Page | Iterable[Page]) -> None:
        # TODO: Implement setting the pages in the tree
        raise NotImplementedError

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
        page_ref: PdfReference = tree.data["Kids"].pop(tree_index)
        self._pdf.objects.delete(page_ref.object_number)

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

    def insert(self, index: int, value: Page) -> None:
        """Inserts a page ``value`` at ``index``. ``index`` is the index of
        the page before which to insert.

        When inserting, the page object is copied into the page list.
        """

        index = self._pos_idx_of(index)
        inserting_page = self._add_page_to_obj_store(value)

        root_tree_ref: PdfReference = self._pdf.trailer["Root"].data["Pages"]

        if self._indexed_pages:
            # document has pages, traverse the tree and insert at location
            result, _ = self._get_tree_with_index(self._root_tree, root_tree_ref, index)
        else:
            result = None

        if result is not None:
            tree, tree_ref, tree_idx = result
        else:
            tree = self._root_tree
            tree_ref = root_tree_ref
            tree_idx = index

        self._insert_page_into_tree(inserting_page, tree_idx, tree=tree, tree_ref=tree_ref)
        self._indexed_pages.insert(index, value)

    def append(self, value: Page) -> None:
        """Appends a page ``value`` to the page list."""
        self.insert(len(self._indexed_pages), value)

    def remove(self, value: Page) -> None:
        """Removes the first occurrence of page ``value`` in the document.

        Raises:
            IndexError: The page list is empty or the page is not in this document.
        """
        index = self._indexed_pages.index(value)
        self.pop(index)

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
        root_tree_ref: PdfReference = self._pdf.trailer["Root"].data["Pages"]

        if self._indexed_pages:
            # document has pages, traverse the tree and insert at location
            result, _ = self._get_tree_with_index(self._root_tree, root_tree_ref, index)
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
