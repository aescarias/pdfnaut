from __future__ import annotations

from typing import TypedDict, TYPE_CHECKING, Any

from pdfnaut.objects import PdfName, PdfHexString, PdfIndirectRef, PdfStream
from pdfnaut.typings.encryption import Encrypt

if TYPE_CHECKING:
    from typing_extensions import Required


class StreamExtent(TypedDict, total=False):
    Length: Required[int]
    Filter: PdfName | list[PdfName]
    DecodeParms: dict[str, Any] | list[dict[str, Any]]
    F: bytes
    FFilter: bytes
    FDecodeParms: dict[str, Any] | list[dict[str, Any]]
    DL: int


class Trailer(TypedDict, total=False):
    Size: Required[int]
    Prev: int
    Root: Required[PdfIndirectRef[Catalog]]
    Encrypt: Encrypt | PdfIndirectRef[Encrypt]
    Info: PdfIndirectRef[Info]
    ID: list[PdfHexString | bytes]


class XRefStream(StreamExtent, Trailer, total=False):
    Type: Required[PdfName]
    Size: Required[int]
    Index: list[int]
    Prev: int
    W: Required[list[int]]


class Catalog(TypedDict, total=False):
    Type: Required[PdfName]
    Version: PdfName
    Extensions: dict[str, Any] # noimpl
    Pages: Required[PdfIndirectRef[PagesTree]]
    PageLabels: dict[str, Any] # number tree, noimpl
    Names: dict[str, Any] # noimpl
    Dests: dict[str, Any] # noimpl
    ViewerPreferences: dict[str, Any] # noimpl
    PageLayout: PdfName # make more exact
    PageMode: PdfName # make more exact
    Outlines: PdfIndirectRef[dict[str, Any]] # noimpl
    Threads: list[Any] # noimpl
    OpenAction: list[Any] | dict[str, Any] # noimpl
    AA: dict[str, Any]
    URI: dict[str, Any]
    AcroForm: dict[str, Any]
    Metadata: PdfIndirectRef[PdfStream]
    StructTreeRoot: dict[str, Any]
    MarkInfo: dict[str, Any]
    Lang: bytes
    SpiderInfo: dict[str, Any]
    OutputIntents: list[Any]
    PieceInfo: dict[str, Any]
    OCProperties: dict[str, Any]
    Perms: dict[str, Any]
    Legal: dict[str, Any]
    Requirements: list[Any]
    Collection: dict[str, Any]
    NeedsRendering: bool


class Info(TypedDict, total=False):
    Title: bytes
    Author: bytes
    Subject: bytes
    Keywords: bytes
    Creator: bytes
    Producer: bytes
    CreationDate: bytes
    ModDate: bytes
    Trapped: PdfName


class PagesTree(TypedDict, total=False):
    Type: Required[PdfName]
    Parent: PdfIndirectRef[PagesTree]
    Kids: Required[list[PdfIndirectRef[PagesTree | Page]]]
    Count: Required[int]


class Page(TypedDict, total=False):
    Type: Required[PdfName]
    Parent: Required[PdfIndirectRef[PagesTree]]
    LastModified: bytes 
    Resources: Required[dict[str, Any]]
    MediaBox: Required[list[int | float]] # rect
    CropBox: list[int | float]
    BleedBox: list[int | float]
    TrimBox: list[int | float]
    ArtBox: list[int | float]
    BoxColorInfo: dict[str, Any]
    Contents: PdfIndirectRef[PdfStream]
    Rotate: int
    Group: dict[str, Any]
    Thumb: PdfIndirectRef[PdfStream]
    B: list[PdfIndirectRef[Any]]
    Dur: int
    Trans: dict[str, Any]
    Annots: list[dict[str, Any]]
    AA: dict[str, Any]
    Metadata: PdfIndirectRef[PdfStream]
    PieceInfo: dict[str, Any]
    StructParents: int
    ID: bytes | PdfHexString
    PZ: int
    SeparationInfo: dict[str, Any]
    Tabs: PdfName
    TemplateInstantiated: PdfName
    PressSteps: dict[str, Any]
    UserUnit: int | float
    VP: dict[str, Any]
