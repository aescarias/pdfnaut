from __future__ import annotations

from typing import Generator, cast

from pdfnaut.cos.objects.base import parse_text_string
from pdfnaut.objects.catalog import PageLayout, PageMode

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

    PDF authors who want to work with a document in a high-level way should use
    this interface over ``PdfParser``."""

    @classmethod
    def from_filename(cls, path: str, *, strict: bool = False) -> PdfDocument:
        """Loads a PDF document from a file ``path``."""
        with open(path, "rb") as fp:
            return PdfDocument(fp.read(), strict=strict)

    def __init__(self, data: bytes, *, strict: bool = False) -> None:
        super().__init__(data, strict=strict)

        self.parse()

        self.access_level = PermsAcquired.OWNER
        """The current access level of the document, specified as a value from the
        :class:`.PermsAcquired` enum.

        - Owner: Full access to the document. If the document is not encrypted, \
        this is the default value.
        - User: Access to the document under restrictions.
        - None: Document is currently encrypted.
        """

        # some files use an empty string as a password
        if self.has_encryption:
            self.access_level = self.decrypt("")

    @property
    def has_encryption(self) -> bool:
        """Whether this document includes encryption."""
        return "Encrypt" in self.trailer

    @property
    def catalog(self) -> PdfDictionary:
        """The root of the document's object hierarchy, including references to pages,
        outlines, destinations, and other core attributes of a PDF document.

        For details on the contents of the catalog, see ``§ 7.7.2 Document Catalog``.
        """
        return cast(PdfDictionary, self.trailer["Root"])

    @property
    def info(self) -> Info | None:
        """The ``Info`` entry in the catalog which includes document-level information
        described in ``§ 14.3.3 Document information dictionary``.

        Some documents may specify a metadata stream rather than an Info entry. This can be
        accessed with :attr:`.PdfDocument.metadata`. PDF 2.0 deprecates all keys of this
        entry except for ``CreationDate`` and ``ModDate``.
        """
        if "Info" not in self.trailer:
            return

        return Info(cast(PdfDictionary, self.trailer["Info"]))

    @info.setter
    def info(self, value: Info | None) -> None:
        info_ref = cast("PdfReference | None", self.trailer.data.get("Info"))

        # A new docinfo object will be created
        if info_ref is None and value is not None:
            new_object = max(self.objects) + 1
            self.objects[new_object] = PdfDictionary(**value.mapping.data)
            self.trailer.data["Info"] = PdfReference(new_object, 0).with_resolver(self.get_object)
        # A docinfo object will be set
        elif info_ref and isinstance(value, Info):
            self.objects[info_ref.object_number] = PdfDictionary(**value.mapping.data)
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
    def metadata(self) -> PdfStream | None:
        """The Metadata entry of the catalog which includes document-level metadata
        stored as XMP."""
        if "Metadata" not in self.catalog:
            return

        return cast(PdfStream, self.catalog["Metadata"])

    @property
    def page_tree(self) -> PdfDictionary:
        """The document's page tree. See ``§ 7.7.3 Page Tree``.

        For iterating over the pages of a PDF, prefer :attr:`.PdfDocument.flattened_pages`.
        """
        return cast(PdfDictionary, self.catalog["Pages"])

    @property
    def outline_tree(self) -> PdfDictionary | None:
        """The document's outlines commonly referred to as bookmarks.

        See ``§ 12.3.3 Document Outline``."""
        return cast("PdfDictionary | None", self.catalog.get("Outlines"))

    def decrypt(self, password: str) -> PermsAcquired:
        self.access_level = super().decrypt(password)
        return self.access_level

    def _flatten_pages(self, *, parent: PdfDictionary | None = None) -> Generator[Page, None, None]:
        root = cast(PdfDictionary, parent or self.page_tree)

        for page in cast(PdfArray[PdfDictionary], root["Kids"]):
            if page["Type"].value == b"Pages":
                yield from self._flatten_pages(parent=page)
            elif page["Type"].value == b"Page":
                yield Page(page.data)

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
        If this entry is absent, the language shall be considered unknown."""
        if "Lang" not in self.catalog:
            return

        return parse_text_string(cast("PdfHexString | bytes", self.catalog["Lang"]))
