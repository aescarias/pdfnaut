from __future__ import annotations

from typing import Any, Generator, TypeVar, cast, overload

from pdfnaut.cos.objects.base import parse_text_string
from pdfnaut.objects.catalog import PageLayout, PageMode

from .cos.objects import (
    PdfArray,
    PdfDictionary,
    PdfHexString,
    PdfName,
    PdfObject,
    PdfReference,
    PdfStream,
    PdfXRefEntry,
)
from .cos.parser import PdfParser, PermsAcquired
from .objects.page import Page
from .objects.trailer import Info


class PdfDocument:
    """A high-level interface over :class:`~pdfnaut.cos.parser.PdfParser`"""

    @classmethod
    def from_filename(cls, path: str, *, strict: bool = False) -> PdfDocument:
        """Loads a PDF document from a file ``path``."""
        with open(path, "rb") as fp:
            return PdfDocument(fp.read(), strict=strict)

    def __init__(self, data: bytes, *, strict: bool = False) -> None:
        self._reader = PdfParser(data, strict=strict)
        self._reader.parse()

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

    T = TypeVar("T")

    @overload
    def get_object(self, reference: PdfReference[T], cache: bool = True) -> T: ...

    @overload
    def get_object(
        self, reference: tuple[int, int], cache: bool = True
    ) -> PdfObject | PdfStream: ...

    def get_object(
        self, reference: PdfReference | tuple[int, int], cache: bool = True
    ) -> PdfObject | PdfStream | Any:
        """Resolves a reference into the indirect object it points to.

        Arguments:
            reference (:class:`.PdfReference` | :class:`tuple[int, int]`):
                A :class:`.PdfReference` object or a tuple of two integers representing,
                in order, the object number and the generation number.

            cache (bool, optional):
                Whether to interact with the object store when resolving references.
                Defaults to True.

                When True, the parser will read entries from cache and write new ones
                if they are not present. If False, the parser will always fetch new
                entries and will not write to cache.

        Returns:
            The object the reference resolves to if valid, otherwise :class:`.PdfNull`.
        """
        return self._reader.get_object(reference, cache)

    @property
    def has_encryption(self) -> bool:
        """Whether this document includes encryption."""
        return "Encrypt" in self._reader.trailer

    @property
    def trailer(self) -> PdfDictionary:
        """The PDF trailer which allows access to other core parts of the PDF structure.

        For details on the contents of the trailer, see ``§ 7.5.5 File Trailer``.

        For documents using an XRef stream, the stream extent is returned. See
        ``§ 7.5.8.2 Cross-Reference Stream Dictionary`` for more details.
        """
        return cast(PdfDictionary, self._reader.trailer)

    @property
    def xref(self) -> dict[tuple[int, int], PdfXRefEntry]:
        """A cross-reference mapping combining the entries of all XRef tables present
        in the document.

        The key is a tuple of two integers: object number and generation number.
        The value is any of the 3 types of XRef entries (free, in use, compressed)
        """
        return self._reader.xref

    @property
    def catalog(self) -> PdfDictionary:
        """The root of the document's object hierarchy, including references to pages,
        outlines, destinations, and other core attributes of a PDF document.

        For details on the contents of the catalog, see ``§ 7.7.2 Document Catalog``.
        """
        return cast(PdfDictionary, self._reader.trailer["Root"])

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

    @property
    def pdf_version(self) -> str:
        """The version of the PDF standard used in this document.

        The version of a PDF may be identified by either its header or the Version entry
        in the catalog. If the Version entry is absent or the header specifies a later
        version, the header version is returned. Otherwise, the Version entry is returned.
        """
        header_version = self._reader.header_version
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
        """Decrypts this document assuming it was encrypted with a ``password``.

        The Standard security handler may specify 2 passwords:
        - An owner password, allowing full access to the PDF
        - A user password, allowing restricted access to the PDF according to its permissions.

        Returns:
            A :class:`.PermsAcquired` specifying the permissions acquired by ``password``.

            - If the document is not encrypted, defaults to :attr:`.PermsAcquired.OWNER`
            - if the document was not decrypted, defaults to :attr:`.PermsAcquired.NONE`
        """
        self.access_level = self._reader.decrypt(password)
        return self.access_level

    def _flatten_pages(self, *, parent: PdfDictionary | None = None) -> Generator[Page, None, None]:
        root = cast(PdfDictionary, parent or self.page_tree)

        for page in cast(PdfArray[PdfDictionary], root["Kids"]):
            if page["Type"].value == b"Pages":
                yield from self._flatten_pages(parent=page)
            elif page["Type"].value == b"Page":
                yield Page(page)

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
