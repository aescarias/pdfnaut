from enum import Enum
from typing import TYPE_CHECKING

from ..objects.trailer import Info
from ..objects.xmp import XmpMetadata

if TYPE_CHECKING:
    from ..document import PdfDocument


class MetadataCopyDirection(Enum):
    """The metadata source to copy from."""

    XMP_TO_DOC_INFO = 0
    """Copy XMP metadata to DocInfo."""

    DOC_INFO_TO_XMP = 1
    """Copy DocInfo to XMP metadata."""


def copy_xmp_to_doc_info(pdf: "PdfDocument") -> None:
    """Copies XMP metadata to the document information dictionary, replacing it if it exists."""

    def x_default_or_first(prop: dict[str, str]) -> str:
        return prop.get("x-default", next(iter(prop.values())))

    xmp = pdf.xmp_info

    if xmp is None:
        raise ValueError("The requested metadata source is not available")

    doc_info = Info()
    doc_info.producer = xmp.pdf_producer
    doc_info.keywords = xmp.pdf_keywords

    if (trapped := xmp.pdf_trapped) in ("True", "False"):
        doc_info.trapped = trapped

    doc_info.creator = xmp.xmp_creator_tool
    doc_info.creation_date = xmp.xmp_create_date
    doc_info.modify_date = xmp.xmp_modify_date

    if xmp.dc_title:
        doc_info.title = x_default_or_first(xmp.dc_title)

    if xmp.dc_creator:
        doc_info.author = "; ".join(xmp.dc_creator)

    if xmp.dc_description:
        doc_info.subject = x_default_or_first(xmp.dc_description)

    pdf.doc_info = doc_info


def copy_doc_info_to_xmp(pdf: "PdfDocument") -> None:
    """Copies the document information dictionary to the XMP metadata, replacing it if it exists."""
    doc_info = pdf.doc_info

    if doc_info is None:
        raise ValueError("The requested metadata source is not available")

    xmp = XmpMetadata()
    xmp.pdf_producer = doc_info.producer
    xmp.pdf_keywords = doc_info.keywords
    xmp.pdf_pdfversion = pdf.pdf_version

    if doc_info.trapped in ("True", "False"):
        xmp.pdf_trapped = doc_info.trapped

    xmp.xmp_creator_tool = doc_info.creator
    xmp.xmp_create_date = doc_info.creation_date
    xmp.xmp_metadata_date = doc_info.modify_date
    xmp.xmp_modify_date = doc_info.modify_date

    if doc_info.title:
        xmp.dc_title = {"x-default": doc_info.title}

    if doc_info.author:
        xmp.dc_creator = [doc_info.author]

    if doc_info.subject:
        xmp.dc_description = {"x-default": doc_info.subject}

    pdf.xmp_info = xmp
