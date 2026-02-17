import enum
from typing import Annotated, Literal, cast

from typing_extensions import Self

from ..common.dictmodels import defaultize, dictmodel, field
from ..cos.objects.base import PdfName
from ..cos.objects.containers import PdfArray, PdfDictionary

PageLayout = Literal[
    "SinglePage", "OneColumn", "TwoColumnLeft", "TwoColumnRight", "TwoPageLeft", "TwoPageRight"
]
PageMode = Literal["UseNone", "UseOutlines", "UseThumbs", "FullScreen", "UseOC", "UseAttachments"]
NonFSPageMode = Literal["UseNone", "UseOutlines", "UseThumbs", "UseOC"]
TextDirection = Literal["L2R", "R2L"]
PageBoundary = Literal["MediaBox", "CropBox", "BleedBox", "TrimBox", "ArtBox"]
PrintScalingMode = Literal["None", "AppDefault"]
PaperHandlingOption = Literal["Simplex", "DuplexFlipShortEdge", "DuplexFlipLongEdge"]
Enforceable = Literal["PrintScaling"]


class UserAccessPermissions(enum.IntFlag):
    """User access permissions as specified in the P entry of the document's standard
    encryption dictionary.

    See "Table 22 - Standard security handler user access permissions" in the PDF spec
    for details.
    """

    # bits 0 and 1 are reserved and should be 0.

    PRINT = 1 << 2
    """For security revision 2 or greater, Print the document. If the document uses 
    revision 3 or greater, print quality may be influenced by :attr:`.FAITHFUL_PRINT`."""

    MODIFY = 1 << 3
    """Modify the contents of the document. May be influenced by :attr:`.MANAGE_ANNOTATIONS`, 
    :attr:`.FILL_FORM_FIELDS`, and :attr:`.ASSEMBLE_DOCUMENT`."""

    COPY_CONTENT = 1 << 4
    """Copy or extract text and graphics. Assistive technology should assume this bit
    as set for its purposes, as per :attr:`.ACCESSIBILITY`."""

    MANAGE_ANNOTATIONS = 1 << 5
    """Add or modify text annotations, fill interactive form fields and, depending 
    on whether :attr:`.MODIFY` is set, create and modify form fields."""

    # bits 6 and 7 are reversed and should be 1.

    FILL_FORM_FIELDS = 1 << 8
    """For security revision 3 or greater, fill existing interactive form 
    fields, even if :attr:`.MANAGE_ANNOTATIONS` is clear."""

    ACCESSIBILITY = 1 << 9
    """(deprecated in PDF 2.0) Extract content for the purposes of accessibility.
    
    This bit should always be set for compatibility with processors supporting 
    earlier specifications.
    """

    ASSEMBLE_DOCUMENT = 1 << 10
    """For security revision 3 or greater, assemble the document (i.e. insert, rotate, 
    and delete pages, create outlines, etc.), even if :attr:`.MODIFY` is clear."""

    FAITHFUL_PRINT = 1 << 11  # revision 3+
    """For security revision 3 or greater, print the document in such a way that a 
    faithful digital representation of the PDF can be generated. 
    
    If this bit is not set (and :attr:`.PRINT` is set), printing shall be limited to 
    a low-level representation, possibly of lower quality.
    """

    # bits 12-31 are reserved and must be 1.


@dictmodel()
class ViewerPreferences(PdfDictionary):
    """The viewer preferences dictionary specifying the way a PDF viewer shall
    display a document on the screen.

    See § 12.2, "Viewer preferences" for details.
    """

    hide_toolbar: bool = field(default=False)
    """Whether to hide the interactive PDF processor's toolbars when the document is active."""

    hide_menubar: bool = field(default=False)
    """Whether to hide the interactive PDF processor's menubar when the document is active."""

    hide_window_ui: bool = field("HideWindowUI", default=False)
    """Whether to hide UI elements in the document's window (such as scroll bars or
    navigation controls), leaving only the document's contents displayed."""

    fit_window: bool = field(default=False)
    """Whether to resize the document's window to fit the size of the page."""

    center_window: bool = field(default=False)
    """Whether to center the document's window position on the screen."""

    display_doc_title: bool = field(default=False)
    """(PDF 1.4) Whether the document's window title should display the title described in 
    the document's metadata. If False, the title bar should instead display the name of the 
    PDF file containing the document."""

    non_full_screen_page_mode: NonFSPageMode = field(default="UseNone")
    """The document's page mode displayed when exiting full-screen mode. This property is only
    relevant if the PageMode entry in the catalog is set to 'FullScreen' and should be ignored
    otherwise. Accepted values are 'UseNone', 'UseOutlines', 'UseThumbs', and 'UseOC'."""

    direction: TextDirection = field(default="L2R")
    """The predominant logical content order for text. Either 'L2R' (left to right, default)
    or 'R2L' (right to left). This is effectively a display hint and has no direct effect
    on the contents of the document."""

    view_area: PageBoundary = field(default="CropBox")
    """(deprecated in PDF 2.0) The name of the page boundary representing the area of a page
    that shall be displayed when viewing the document on the screen. The value should be the
    key of the relevant page boundary in a page object. If no such boundary is defined,
    the default value ('CropBox') is used.

    Accepted values are 'CropBox', 'MediaBox', 'BleedBox', 'TrimBox', and 'ArtBox'.
    """

    view_clip: PageBoundary = field(default="CropBox")
    """(deprecated in PDF 2.0) The name of the page boundary representing to which the
    contents of a page shall be clipped when viewing the document. Similar to ViewArea,
    the value should be the key of the relevant page boundary in a page object.
    """

    print_area: PageBoundary = field(default="CropBox")
    """(deprecated in PDF 2.0) The name of the page boundary representing the area of a
    page that shall be rendered when printing the document. Similar to ViewArea, the value
    should be the key of the relevant page boundary in a page object."""

    print_clip: PageBoundary = field(default="CropBox")
    """(deprecated in PDF 2.0) The name of the page boundary representing to which the
    contents of a page shall be clipped when printing the document. Similar to ViewArea,
    the value should be the key of the relevant page boundary in a page object."""

    print_scaling: PrintScalingMode = field(default="AppDefault")
    """The page scaling option to select when a print dialog is displayed for this document.

    Accepted values are 'None' meaning no page scaling or 'AppDefault' (default) indicating
    that the interactive PDF processor should select its default print scaling value."""

    duplex: PaperHandlingOption | None = field(default=None)
    """The paper handling option to use when printing the document. Should be either of:

    - Simplex: Print single-sided
    - DuplexFlipShortEdge: Duplex, flip on the short edge of the sheet
    - DuplexFlipLongEdge: Duplex, flip on the long edge of the sheet

    If this value is none, the document producer may choose their own default setting.
    """

    pick_tray_by_pdf_size: bool | None = field(default=None)
    """Whether the PDF page size shall be used to select the input paper tray. This setting
    influences only the preset values used to populate the print dialog. This setting
    has no effect on systems that do not provide the ability to pick the input tray by size.

    If this value is none, the document producer may choose their own default setting.
    """

    print_page_range: PdfArray[int] | None = field(default=None)
    """The page numbers used to initialize the print dialog box. The array should
    contain an even number of values interpreted as pairs, with each pair specifying
    the first and last pages in a sub-range of pages to be printed (the first page being
    denoted by the number 1).

    If this value is none, the document producer may choose their own default setting.
    """

    num_copies: int | None = field(default=None)
    """The number of copies that shall be printed when the print dialog is opened for this file.

    If this value is none, the document producer may choose their own default setting,
    though this setting is usually 1.
    """

    @classmethod
    def from_dict(cls, mapping: PdfDictionary) -> Self:
        dictionary = cls()
        dictionary.data = mapping.data

        return dictionary

    @property
    def enforce(self) -> list[Enforceable] | None:
        """(PDF 2.0) An array of names of viewer preferences that shall be enforced by
        PDF processors and that shall not be overridden by subsequent selections in
        the application user interface."""
        if "Enforce" not in self:
            return

        enforced = cast(PdfArray[PdfName], self["Enforce"])

        return [cast(Enforceable, it.value.decode()) for it in enforced]


@dictmodel()
class DeveloperExtension(PdfDictionary):
    """An entry in an extension dictionary (see § 7.12.3, "Developer extensions dictionary")."""

    base_version: Annotated[str, "name"]
    """The name of the PDF version to which this extension applies.

    The name shall be consistent with the syntax used for the Version entry
    of the catalog dictionary (see § 7.7.2, "Document catalog dictionary").
    """

    level: int = field("ExtensionLevel")
    """An developer-defined integer denoting the extension being used.

    If the developer introduces more than one extension to a given base version,
    the extension level assigned by the developer should increase over time.
    """

    url: str | None = field("URL", default=None)
    """(PDF 2.0) A URL referring to the documentation for this extension."""

    revision: str | None = field("ExtensionRevision", default=None)
    """(PDF 2.0) Additional revision information on the extension level being used."""

    @classmethod
    def from_dict(cls, mapping: PdfDictionary) -> Self:
        dictionary = defaultize(cls)
        dictionary.data = mapping.data

        return dictionary


class ExtensionMap(PdfDictionary):
    """A map defining developer extensions in a document (see § 7.12, "Extensions dictionary")."""

    @classmethod
    def from_dict(cls, mapping: PdfDictionary) -> Self:
        dictionary = cls()
        dictionary.data = mapping.data

        return dictionary

    def query(self, key: str) -> DeveloperExtension | list[DeveloperExtension]:
        """Returns a developer-defined extension (or a sequence of them) for
        a base prefix ``key``."""

        if key == "Type":
            raise ValueError("not a valid extension name")

        extension = self[key]
        if isinstance(extension, PdfArray):
            return [DeveloperExtension.from_dict(cast(PdfDictionary, ext)) for ext in extension]

        return DeveloperExtension.from_dict(cast(PdfDictionary, extension))


@dictmodel()
class MarkInfo(PdfDictionary):
    """Information relevant to specialized uses of structured PDF documents.

    See § 14.7, "Logical structure" for details.
    """

    marked: bool = False
    """Whether the document claims to conform to tagged PDF conventions."""

    suspects: bool = False
    """(PDF 1.6; deprecated in PDF 2.0) Whether the document includes tag suspects
    which are applied for marked content elements whose page content order could not
    be determined.
    
    In such case, the document may not fully conform to tagged PDF conventions.
    """

    user_properties: bool = False
    """(PDF 1.6) Whether structure elements including user properties are present 
    in the document.
    
    See § 14.7.6.4, "User properties" for details.
    """

    @classmethod
    def from_dict(cls, mapping: PdfDictionary) -> Self:
        dictionary = cls()
        dictionary.data = mapping.data

        return dictionary
