from __future__ import annotations

from typing import Generator, cast

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

        For details on the contents of the catalog, see ``§ 7.7.2 Document Catalog``.
        """
        return cast(PdfDictionary, self.trailer["Root"])

    @catalog.setter
    def catalog(self, value: PdfDictionary) -> None:
        root_ref = cast(PdfReference, self.trailer.data["Root"])
        self.objects[root_ref.object_number] = value

    @property
    def doc_info(self) -> Info | None:
        """The ``Info`` entry in the catalog which includes document-level information
        described in ``§ 14.3.3 Document information dictionary``.

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
        """The document's page tree. See ``§ 7.7.3 Page Tree``.

        For iterating over the pages of a PDF, prefer :attr:`.PdfDocument.flattened_pages`.
        """
        return cast(PdfDictionary, self.catalog["Pages"])

    @property
    def outline_tree(self) -> PdfDictionary | None:
        """The document's outline tree including what is commonly referred to as
        bookmarks. See ``§ 12.3.3 Document Outline``.
        """
        return cast("PdfDictionary | None", self.catalog.get("Outlines"))

    def decrypt(self, password: str) -> PermsAcquired:
        self.access_level = super().decrypt(password)
        return self.access_level

    def _flatten_pages(self, *, parent: PdfDictionary | None = None) -> Generator[Page, None, None]:
        root = cast(PdfDictionary, parent or self.page_tree)

        for page in cast(PdfArray[PdfDictionary], root["Kids"]):
            type_ = cast(PdfName, page["Type"])
            if type_.value == b"Pages":
                yield from self._flatten_pages(parent=page)
            elif type_.value == b"Page":
                yield Page.from_dict(page)

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
        elements or marked content (``§ 14.9.2 Natural language specification``).

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

        encrypt = cast(PdfDictionary, self.trailer["Encrypt"])

        if (perms := encrypt.get("P")) is not None:
            return UserAccessPermissions(perms)
