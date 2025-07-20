from __future__ import annotations

import pathlib
from typing import Generator, cast

from .cos.objects import (
    PdfArray,
    PdfDictionary,
    PdfHexString,
    PdfName,
    PdfReference,
    PdfStream,
)
from .cos.objects.base import encode_text_string, parse_text_string
from .cos.objects.xref import FreeXRefEntry, InUseXRefEntry, PdfXRefEntry
from .cos.parser import PdfParser, PermsAcquired
from .cos.serializer import PdfSerializer
from .objects.catalog import (
    ExtensionMap,
    MarkInfo,
    PageLayout,
    PageMode,
    UserAccessPermissions,
    ViewerPreferences,
)
from .objects.page import Page
from .objects.trailer import Info
from .objects.xmp import XmpMetadata
from .page_list import PageList, flatten_pages


class PdfDocument(PdfParser):
    """A high-level interface over :class:`~.PdfParser`.

    PDF authors who want to work with a document in a high-level way should
    use this interface over ``PdfParser``.
    """

    @classmethod
    def from_filename(cls, path: str | pathlib.Path, *, strict: bool = False) -> PdfDocument:
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

        self._page_list: PageList | None = None

    @property
    def has_encryption(self) -> bool:
        """Whether this document includes encryption."""
        return "Encrypt" in self.trailer

    @property
    def catalog(self) -> PdfDictionary:
        """The root of the document's object hierarchy, including references to pages,
        outlines, destinations, and other core elements of a PDF document.

        For details on the contents of the catalog, see § 7.7.2, "Document Catalog".
        """
        return cast(PdfDictionary, self.trailer["Root"])

    @catalog.setter
    def catalog(self, value: PdfDictionary) -> None:
        root_ref = cast(PdfReference, self.trailer.data["Root"])
        self.objects[root_ref.object_number] = value

    @property
    def doc_info(self) -> Info | None:
        """The ``/Info`` entry in the catalog which includes document-level information
        described in § 14.3.3, "Document information dictionary".

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
        self._set_dict_attribute(self.trailer, "Info", value)

    @property
    def pdf_version(self) -> str:
        """The version of the PDF standard implemented by this document.

        For obtaining the PDF version, the ``/Version`` entry in the catalog
        is checked. If no such key is present, the version specified in the
        header is returned. If both are present, the version returned is the
        latest specified according to lexicographical comparison.
        """
        header_version = self.header_version
        catalog_version = cast("PdfName | None", self.catalog.get("Version"))

        if not catalog_version:
            return header_version

        return max((header_version, catalog_version.value.decode()))

    @property
    def xmp_info(self) -> XmpMetadata | None:
        """The ``/Metadata`` entry of the catalog which includes document-level
        metadata stored as XMP."""
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
        """The document's page tree. See § 7.7.3, "Page Tree" for details.

        For iterating over the pages of a PDF, prefer :attr:`PdfDocument.pages`
        or :attr:`.PdfDocument.flattened_pages`.
        """
        return cast(PdfDictionary, self.catalog["Pages"])

    @property
    def outline_tree(self) -> PdfDictionary | None:
        """The document's outline tree including what is commonly referred to as
        bookmarks. See § 12.3.3, "Document Outline" for details.
        """
        return cast("PdfDictionary | None", self.catalog.get("Outlines"))

    def decrypt(self, password: str) -> PermsAcquired:
        self.access_level = super().decrypt(password)
        return self.access_level

    @property
    def flattened_pages(self) -> Generator[Page, None, None]:
        """A generator suitable for iterating over the pages of a PDF."""
        return flatten_pages(self.page_tree)

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

    @page_layout.setter
    def page_layout(self, layout: PageLayout) -> None:
        self.catalog["PageLayout"] = PdfName(layout.encode())

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

    @page_mode.setter
    def page_mode(self, mode: PageMode) -> None:
        self.catalog["PageMode"] = PdfName(mode.encode())

    @property
    def language(self) -> str | None:
        """A language identifier that shall specify the natural language for all text in
        the document except where overridden by language specifications for structure
        elements or marked content (see § 14.9.2, "Natural language specification").

        If this entry is absent, the language shall be considered unknown.
        """

        if "Lang" not in self.catalog:
            return

        return parse_text_string(cast("PdfHexString | bytes", self.catalog["Lang"]))

    @language.setter
    def language(self, text: str) -> None:
        self.catalog["Lang"] = encode_text_string(text)

    @property
    def access_permissions(self) -> UserAccessPermissions | None:
        """User access permissions relating to the document if any.

        See :class:`.UserAccessPermissions` for details.
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

        if self._page_list is None:
            self._page_list = PageList(
                self, self.page_tree, cast(PdfReference, self.catalog.data["Pages"])
            )

        return self._page_list

    @property
    def viewer_preferences(self) -> ViewerPreferences | None:
        """Settings controlling how a PDF reader shall display a document
        on the screen. If this value is absent, the PDF reader should choose
        its own default preferences.

        See :class:`.ViewerPreferences` for details.
        """
        if "ViewerPreferences" not in self.catalog:
            return

        return ViewerPreferences.from_dict(cast(PdfDictionary, self.catalog["ViewerPreferences"]))

    @viewer_preferences.setter
    def viewer_preferences(self, value: ViewerPreferences | None) -> None:
        self._set_dict_attribute(self.catalog, "ViewerPreferences", value)

    @property
    def extensions(self) -> ExtensionMap | None:
        """Developer-defined extensions to this document. Introduced in
        ISO 32000-1 (PDF 1.7). See :class:`.ExtensionMap` for details."""
        if "Extensions" not in self.catalog:
            return

        return ExtensionMap.from_dict(cast(PdfDictionary, self.catalog["Extensions"]))

    @property
    def mark_info(self) -> MarkInfo | None:
        """Information pertaining to the document's conformance to tagged PDF conventions.

        See :class:`.MarkInfo` for details.
        """
        if "MarkInfo" not in self.catalog:
            return

        return MarkInfo.from_dict(cast(PdfDictionary, self.catalog["MarkInfo"]))

    def _set_dict_attribute(
        self, dest: PdfDictionary, key: str, value: PdfDictionary | None
    ) -> None:
        current_value = dest.data.get(key)
        if value is None:
            # The object will be removed.
            if isinstance(current_value, PdfReference):
                self.objects.free(current_value.object_number)

            dest.data.pop(key, None)
            return

        new_value = PdfDictionary(**value.data)

        if current_value is None:
            # A new object will be created.
            reference = self.objects.add(new_value)
            dest.data[key] = reference
        elif isinstance(current_value, PdfReference):
            # A new object will be set as a reference.
            self.objects[current_value.object_number] = new_value
        else:
            # A new object will be set as is.
            dest.data[key] = new_value
