from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict, Literal, Any

from pdfnaut.objects import PdfName, PdfHexString, PdfIndirectRef, PdfStream
from pdfnaut.typings.encryption import Encrypt

if TYPE_CHECKING:
    from typing_extensions import Required


class StreamExtent(TypedDict, total=False):
    Length: Required[int]
    """The number of bytes in the encoded stream."""
    Filter: PdfName | list[PdfName]
    """The filter (or filters) the document was encoded in."""
    DecodeParms: dict[str, Any] | list[dict[str, Any]]
    """The decode parameters for the filter or each of the filters specified."""
    F: bytes
    """The File the stream's contents is stored in."""
    FFilter: PdfName | list[PdfName]
    """Same as Filter, but for a file."""
    FDecodeParms: dict[str, Any] | list[dict[str, Any]]
    """Same as DecodeParms, but for a file."""
    DL: int
    """'Decoded Length' - The number of bytes in the decoded stream."""


class Trailer(TypedDict, total=False):
    Size: Required[int]
    """The total number of entries in the combined cross-reference table."""
    Prev: int
    """The previous trailer if present."""
    Root: Required[PdfIndirectRef[Catalog]]
    """A reference to the document's catalog."""
    Encrypt: Encrypt | PdfIndirectRef[Encrypt]
    """The document's encryption dictionary."""
    Info: PdfIndirectRef[Info]
    """The document-level information dictionary."""
    ID: list[PdfHexString | bytes]
    """A list of two bytestrings constituting a file identifier. The first bytestring is 
    produced when the document is first created and shall not change while the 
    second bytestring shall change when the document is modified."""


class XRefStream(StreamExtent, Trailer, total=False):
    Type: Required[PdfName[Literal[b"XRef"]]]
    """Shall be 'XRef'."""
    Size: Required[int]
    """The total number of entries in the combined cross-reference table."""
    Index: list[int]
    """A list containing a pair of integers for each subsection of the table. The first shall 
    be the first object number in the subsection, the second shall be its number of entries."""
    Prev: int
    """The previous cross-reference stream if present."""
    W: Required[list[int]]
    """A list of integers specifying the byte Widths of the fields in a single 
    cross-reference entry. For PDF 1.5, this list contains 3 integers."""


PageMode = Literal[b"UseNone", b"UseOutlines", b"UseThumbs", b"FullScreen", 
                   b"UseOC", b"UseAttachments"]
PageLayout = Literal[b"SinglePage", b"OneColumn", b"TwoColumnLeft", 
                     b"TwoColumnRight", b"TwoPageLeft", b"TwoPageRight"]

class Catalog(TypedDict, total=False):
    Type: Required[PdfName[Literal[b"Catalog"]]]
    """Shall be 'Catalog'."""
    Version: PdfName
    """The version of the PDF document. Use this entry if it is later than the one 
    specified in  the file header. Otherwise, or if this entry is not present, 
    use the file header instead."""
    Extensions: dict[str, Any] # noimpl
    """The extensions dictionary. (``§ 7.12 Extensions Dictionary``)"""
    Pages: Required[PdfIndirectRef[PageTree]]
    """The root of the pages tree. (``§ 7.7.3 Page Tree``)"""
    PageLabels: dict[str, Any] # number tree, noimpl
    """A number tree specifying how the pages are labelled."""
    Names: dict[str, Any] # noimpl
    """The document's name dictionary."""
    Dests: dict[str, Any] # noimpl
    """A dictionary of named destinations"""
    ViewerPreferences: dict[str, Any] # noimpl
    """Instructions on how the viewer should preferably display this document."""
    PageLayout: PdfName[PageLayout]
    """The page layout to use when the document is opened."""
    PageMode: PdfName[PageMode]
    """The page mode -- how should the document be displayed when opened."""
    Outlines: PdfIndirectRef[Outlines]
    """The document's outline dictionary. (aka. bookmarks)"""
    Threads: list[dict[str, Any]] # noimpl
    """The document's article threads."""
    OpenAction: list[Any] | dict[str, Any] # noimpl
    """The action (or actions) to perform when the document is opened."""
    AA: dict[str, Any] # noimpl
    """Additional Actions or trigger events affecting the document as a whole."""
    URI: dict[str, Any] # noimpl
    """URI Actions affecting the document as a whole."""
    AcroForm: dict[str, Any] # noimpl
    """The document's interactive form dictionary."""
    Metadata: PdfIndirectRef[PdfStream]
    """The document-level metadata stream."""
    StructTreeRoot: dict[str, Any] # noimpl
    """The document's structure tree root dictionary."""
    MarkInfo: dict[str, Any] # noimpl
    """Mark information dictionary for Tagged PDFs."""
    Lang: bytes
    """A language identifier for the document."""
    SpiderInfo: dict[str, Any] # noimpl
    """A Web Capture information dictionary."""
    OutputIntents: list[Any] # noimpl
    """A dictionary specifying the color characteristics of output devices on which 
    the document might be rendered."""
    PieceInfo: dict[str, Any] # noimpl
    """A page-piece dictionary for the document."""
    OCProperties: dict[str, Any] # noimpl
    """The document's optional content properties."""
    Perms: dict[str, Any] # noimpl
    """The document's user access permissions dictionary."""
    Legal: dict[str, Any] # noimpl
    """A dictionary containing Legal Content Attestations."""
    Requirements: list[dict[str, Any]] # noimpl
    """A list of dictionaries specifying requirements for this document."""
    Collection: dict[str, Any] # noimpl
    """A collection dictionary useful for enhancing the presentation of file attachments."""
    NeedsRendering: bool
    """Whether to expedite the display of PDF documents containing XFA forms."""


Trapped = Literal[b"True", b"False", b"Unknown"]

class Info(TypedDict, total=False):
    Title: bytes
    """The document's title."""
    Author: bytes
    """The person who made this document."""
    Subject: bytes
    """The subject of the document."""
    Keywords: bytes
    """Keywords associated with the document."""
    Creator: bytes
    """The name of the product that created the original document before converting to PDF."""
    Producer: bytes
    """The name of the product that produced a PDF from an original document."""
    CreationDate: bytes
    """The date and time the document was created."""
    ModDate: bytes
    """The date and time the document was most recently modified."""
    Trapped: PdfName[Trapped]
    """Whether the document has been modified to include trapping information."""


class PageTree(TypedDict, total=False):
    Type: Required[PdfName[Literal[b"Pages"]]]
    """Shall be 'Pages'."""
    Parent: PdfIndirectRef[PageTree]
    """The page tree node that is the immediate parent of this node."""
    Kids: Required[list[PdfIndirectRef[PageTree | Page]]]
    """The immediate children of this node."""
    Count: Required[int]
    """The number of page objects that are descendants of this node."""


class Page(TypedDict, total=False):
    Type: Required[PdfName[Literal[b"Page"]]]
    """Shall be 'Page'."""
    Parent: Required[PdfIndirectRef[PageTree]]
    """The page tree node that is the immediate parent of this node."""
    LastModified: bytes 
    """The date and time this page was most recently modified."""
    Resources: Required[dict[str, Any]] # noimpl
    """A dictionary containing any resources required by the page."""
    MediaBox: Required[list[int | float]] # rect
    """The bounds of the physical medium on which the document will be presented."""
    CropBox: list[int | float] # rect
    """The visible region of the page."""
    BleedBox: list[int | float] # rect
    """The region to which the contents of the page shall be clipped when output in a 
    production format."""
    TrimBox: list[int | float] # rect
    """The intended dimensions of the finished page after trimming."""
    ArtBox: list[int | float] # rect
    """The extent of the page's meaningful content as intended by the page's creator."""
    BoxColorInfo: dict[str, Any] # noimpl
    """The colors and visual characteristics to be used when displaying guidelines 
    on the screen for the boundaries."""
    Contents: PdfIndirectRef[PdfStream] | list[PdfIndirectRef[PdfStream]]
    """A content stream describing the contents of the page."""
    Rotate: int
    """The number of degrees by which the page shall be rotated clockwise."""
    Group: dict[str, Any] # noimpl
    """The attributes of the page's page group for use in the transparent imaging model."""
    Thumb: PdfIndirectRef[PdfStream]
    """The page's thumbnail image."""
    B: list[PdfIndirectRef[Any]]
    """A list of indirect references to article beads."""
    Dur: int
    """The page's display duration until advancing to the next page when being presented."""
    Trans: dict[str, Any]
    """Transition effects to apply to the page when being presented."""
    Annots: list[dict[str, Any] | PdfIndirectRef[dict[str, Any]]]
    """Annotation dictionaries for the document."""
    AA: dict[str, Any]
    """Additional Actions or trigger events defined for this page."""
    Metadata: PdfIndirectRef[PdfStream]
    """The metadata stream for this page."""
    PieceInfo: dict[str, Any]
    """A page piece dictionary for this page."""
    StructParents: int
    """The integer key of the page's entry in the structural parent tree."""
    ID: PdfIndirectRef[bytes | PdfHexString] | bytes | PdfHexString
    """The digital identifier of the page's parent Web Capture content set."""
    PZ: int
    """The page's Preferred Zoom magnification factor."""
    SeparationInfo: dict[str, Any]
    """A separation dictionary that shall contain information needed to generate 
    color separations for the page."""
    Tabs: PdfName
    """The tab order that shall be used for annotations in this page."""
    TemplateInstantiated: PdfName
    """The name of the originating page object."""
    PressSteps: dict[str, Any]
    """A navigation node dictionary that shall represent the first node on the page."""
    UserUnit: int | float
    """A positive number that shall give the size of the default user space units,
    in multiples of 1/72. (1 user unit = 1/72 of an inch = 1 point)"""
    VP: dict[str, Any]
    """Viewport dictionaries for rectangular regions in the page."""


class Outlines(TypedDict, total=False):
    Type: PdfName[Literal[b"Outlines"]]
    """Shall be 'Outlines'."""
    First: PdfIndirectRef[OutlineItem]
    """The first top-level item in the outline."""
    Last: PdfIndirectRef[OutlineItem]
    """The last top-level item in the outline."""
    Count: int
    """The total number of visible outline items at all levels of the outline."""


class OutlineItem(TypedDict, total=False):
    Title: Required[bytes]
    """The text that shall be displayed for this outline."""
    Parent: Required[PdfIndirectRef[OutlineItem | Outlines]]
    """The parent of this item in the outline hierarchy."""
    Prev: PdfIndirectRef[OutlineItem]
    """The previous item at this outline level"""
    Next: PdfIndirectRef[OutlineItem]
    """The next item at this outline level."""
    First: PdfIndirectRef[OutlineItem]
    """The first of this item's immediate children in the outline hierarchy."""
    Last: PdfIndirectRef[OutlineItem]
    """The last of this item's immediate children in the outline hierarchy."""
    Count: int
    """The sum of the number of visible descendant outline items at all levels."""
    Dest: bytes | PdfName | list[Any] # noimpl
    """The destination that shall be displayed when the outline is activated."""
    A: dict[str, Any] # noimpl
    """The Action that shall be performed when the outline is activated."""
    SE: PdfIndirectRef[dict[str, Any]] # noimpl
    """The Structure Element to which the item refers."""
    C: list[int | float]
    """The color that shall be used for the outline's text in RGB."""
    F: int
    """A set of flags specifying style characteristics for the outline's text."""
