from __future__ import annotations

import pathlib
from collections.abc import Generator
from typing import cast

from pdfnaut.objects.actions import Action, action_into
from pdfnaut.objects.destinations import Destination, DestType, NamedDestination

from .common import metadata
from .common.metadata import MetadataCopyDirection
from .common.utils import is_null
from .cos.objects import (
    PdfArray,
    PdfDictionary,
    PdfHexString,
    PdfName,
    PdfReference,
    PdfStream,
)
from .cos.objects.base import PdfObject, encode_text_string, parse_text_string
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
from .objects.outlines import OutlineTree
from .objects.page import Page
from .objects.trailer import Info
from .objects.xmp import XmpMetadata
from .page_list import PageList, flatten_pages


class PdfDocument(PdfParser):
    """A PDF document that can be read and written to.

    In essence, it is a high-level wrapper around :class:`~.PdfParser` intended for
    PDF users who want to work with a document via high-level interfaces.
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

        objects: dict[tuple[int, int], PdfObject] = {
            (1, 0): PdfDictionary({"Type": PdfName(b"Catalog"), "Pages": PdfReference(2, 0)}),
            (2, 0): PdfDictionary({"Type": PdfName(b"Pages"), "Kids": PdfArray(), "Count": 0}),
        }

        section: list[tuple[int, PdfXRefEntry]] = [(0, FreeXRefEntry(0, 65535))]

        for (obj_num, gen_num), item in objects.items():
            offset = builder.write_object((obj_num, gen_num), item)
            section.append((obj_num, InUseXRefEntry(offset, gen_num)))

        subsections = builder.generate_xref_section(section)

        startxref = builder.write_standard_xref_section(subsections)

        builder.write_trailer(
            PdfDictionary({"Size": subsections[0].count, "Root": PdfReference(1, 0)}), startxref
        )

        builder.write_eof()

        return PdfDocument(builder.content.getvalue())

    def __init__(self, data: bytes, *, strict: bool = False) -> None:
        super().__init__(data, strict=strict)

        self.parse()

        self.access_level = PermsAcquired.OWNER
        """The current access level of the document. It may be either of the values in
        :class:`.PermsAcquired`:
         
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
        return not is_null(self.trailer.get("Encrypt"))

    @property
    def catalog(self) -> PdfDictionary:
        """The document catalog representing the root of the document's object
        hierarchy, including references to the page tree, outlines, destinations,
        and other core elements in a PDF document.

        For details on the contents of the document catalog, see ISO 32000-2:2020
        § 7.7.2 "Document catalog dictionary".
        """

        return cast(PdfDictionary, self.trailer["Root"])

    @catalog.setter
    def catalog(self, value: PdfDictionary) -> None:
        root_ref = cast(PdfReference, self.trailer.data["Root"])
        self.objects[root_ref.object_number] = value

    @property
    def doc_info(self) -> Info | None:
        """The ``Info`` entry of the document trailer which includes the document-level
        information described in ISO 32000-2:2020 § 14.3.3 "Document information dictionary".

        Some documents may specify a metadata stream rather than a DocInfo dictionary.
        Such metadata can be accessed using :attr:`.PdfDocument.xmp_info`.

        PDF 2.0 deprecated all keys of the DocInfo dictionary except for ``CreationDate``
        and ``ModDate``.
        """
        info = self.trailer.get("Info")
        if is_null(info):
            return

        return Info.from_dict(cast(PdfDictionary, info))

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
        """The ``/Metadata`` entry of the document catalog which includes
        document-level metadata stored as XMP."""
        metadata = self.catalog.get("Metadata")
        if is_null(metadata):
            return

        return XmpMetadata(cast(PdfStream, metadata))

    @xmp_info.setter
    def xmp_info(self, xmp: XmpMetadata | None) -> None:
        metadata_ref = cast("PdfReference | None", self.catalog.data.get("Metadata"))

        if is_null(metadata_ref) and xmp is not None:
            # A new metadata object will be created
            self.catalog["Metadata"] = self.objects.add(xmp.stream)
        elif metadata_ref and isinstance(xmp, XmpMetadata):
            # A metadata object will be set
            self.objects[metadata_ref.object_number] = xmp.stream
        elif metadata_ref:
            # A metadata object will be removed
            self.objects.delete(metadata_ref.object_number)
            self.catalog.pop("Metadata", None)

    @property
    def page_tree(self) -> PdfDictionary:
        """The document's page tree described in ISO 32000-2:2020 § 7.7.3 "Page Tree".

        :attr:`.PdfDocument.pages` should be preferred in typical usage.
        """
        return cast(PdfDictionary, self.catalog["Pages"])

    @property
    def outline_tree(self) -> PdfDictionary | None:
        """The document's outline tree including what is commonly referred to as
        bookmarks. See ISO 32000-2:2020 § 12.3.3 "Document outline" for details."""
        outlines = self.catalog.get("Outlines")
        if is_null(outlines):
            return

        return cast("PdfDictionary | None", outlines)

    @property
    def outline(self) -> OutlineTree | None:
        """The outline tree including a hierarchy of outline items or bookmarks used
        for document-level navigation."""
        outlines = self.catalog.get("Outlines")
        if is_null(outlines):
            return

        outline = cast(PdfDictionary, self.catalog["Outlines"])
        outline_ref = cast(PdfReference, self.catalog.data["Outlines"])
        return OutlineTree(self, outline, outline_ref)

    @outline.deleter
    def outline(self) -> None:
        if self.outline is None:
            return

        self.outline.children.clear()
        del self.catalog["Outlines"]

    def new_outline(self) -> None:
        """Creates an empty outline tree."""
        outline = PdfDictionary[str, PdfObject]({"Type": PdfName(b"Outlines")})
        outline_ref = self.objects.add(outline)
        self.catalog["Outlines"] = outline_ref

    def decrypt(self, password: str) -> PermsAcquired:
        self.access_level = super().decrypt(password)
        return self.access_level

    @property
    def flattened_pages(self) -> Generator[Page, None, None]:
        """A generator suitable for iterating over the pages of a PDF."""
        return flatten_pages(self.page_tree, pdf=self)

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
        page_layout = self.catalog.get("PageLayout")
        if is_null(page_layout):
            return "SinglePage"

        layout_name = cast(PdfName, page_layout).value.decode()
        return cast(PageLayout, layout_name)

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
        page_mode = self.catalog.get("PageMode")
        if is_null(page_mode):
            return "UseNone"

        mode_name = cast(PdfName, page_mode).value.decode()
        return cast(PageMode, mode_name)

    @page_mode.setter
    def page_mode(self, mode: PageMode) -> None:
        self.catalog["PageMode"] = PdfName(mode.encode())

    @property
    def language(self) -> str | None:
        """A language identifier that shall specify the natural language for all text in
        the document except where overridden by language specifications for structure
        elements or marked content.

        See ISO 32000-2:2020 § 14.9.2 "Natural language specification" for details.

        If this entry is absent or invalid, the language shall be considered unknown.
        """
        lang = self.catalog.get("Lang")
        if is_null(lang):
            return

        return parse_text_string(cast("PdfHexString | bytes", lang))

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

        if not is_null(perms := encrypt_dict.get("P")):
            return UserAccessPermissions(perms)

    @property
    def pages(self) -> PageList:
        """The page list in the document."""

        if not self.access_level:
            raise PermissionError("cannot read pages of encrypted document.")

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
        viewer_prefs = self.catalog.get("ViewerPreferences")
        if is_null(viewer_prefs):
            return

        return ViewerPreferences.from_dict(cast(PdfDictionary, viewer_prefs))

    @viewer_preferences.setter
    def viewer_preferences(self, value: ViewerPreferences | None) -> None:
        self._set_dict_attribute(self.catalog, "ViewerPreferences", value)

    @property
    def extensions(self) -> ExtensionMap | None:
        """Developer-defined extensions to this document. This feature was introduced
        in ISO 32000-1 (PDF 1.7). See :class:`.ExtensionMap` for details."""
        extensions = self.catalog.get("Extensions")
        if is_null(extensions):
            return

        return ExtensionMap.from_dict(cast(PdfDictionary, extensions))

    @property
    def mark_info(self) -> MarkInfo | None:
        """Information pertaining to the document's conformance to tagged PDF conventions.

        See :class:`.MarkInfo` for details.
        """
        mark_info = self.catalog.get("MarkInfo")
        if is_null(mark_info):
            return

        return MarkInfo.from_dict(cast(PdfDictionary, mark_info))

    @property
    def open_action(self) -> DestType | Action | None:
        """The destination or action that shall be displayed or performed when
        the document is opened."""

        dest_or_action = self.catalog.get("OpenAction")
        if is_null(dest_or_action):
            return

        if isinstance(dest_or_action, PdfArray):
            return Destination(dest_or_action)
        elif isinstance(dest_or_action, PdfDictionary):
            return action_into(dest_or_action)

        return cast(NamedDestination, dest_or_action)

    @open_action.setter
    def open_action(self, action: DestType | Action | None) -> None:
        self._set_dict_attribute(self.catalog, "OpenAction", action)

    def _set_dict_attribute(
        self, dest: PdfDictionary, key: str, value: PdfObject | None, indirect: bool = True
    ) -> None:
        current_value = dest.data.get(key)
        if value is None:
            dest.data.pop(key, None)
            return

        if isinstance(value, PdfReference):
            dest.data[key] = value
            return

        if indirect and isinstance(current_value, PdfReference):
            self.objects[current_value.object_number] = value
        elif indirect:
            reference = self.objects.add(value)
            dest.data[key] = reference
        else:
            dest.data[key] = value

    def copy_metadata(self, direction: MetadataCopyDirection) -> None:
        """Performs reconciling of the document metadata sources by copying data
        from one source to another, based on the provided ``direction``.

        A PDF may store document metadata in either the document information (DocInfo)
        dictionary or in XMP. This function ensures that the two sources are equivalent
        by using the metadata mapping described in :ref:`Reconciling PDF metadata`.

        If the metadata source to copy to does not exist, it will be created; otherwise,
        it will be overwritten. :class:`ValueError` is raised if the source to copy from
        does not exist.
        """

        if direction == MetadataCopyDirection.XMP_TO_DOC_INFO:
            return metadata.copy_xmp_to_doc_info(self)
        elif direction == MetadataCopyDirection.DOC_INFO_TO_XMP:
            return metadata.copy_doc_info_to_xmp(self)
