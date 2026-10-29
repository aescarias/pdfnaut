# Unit tests for multiple parsing scenarios via a set of PDF documents.
from __future__ import annotations

import pytest

from pdfnaut.cos import PdfReader
from pdfnaut.cos.objects import PdfStream
from pdfnaut.exceptions import PdfParseError


def test_simple_pdf() -> None:
    """Tests a simple PDF: an unencrypted PDF document with no compression applied
    and a few pages of content."""

    with PdfReader("tests/docs/sample.pdf") as reader:
        assert len(reader.xref) == reader.trailer["Size"]

        catalog = reader.trailer["Root"]
        metadata = reader.trailer["Info"]
        assert catalog is not None and metadata is not None

        first_page = catalog["Pages"]["Kids"][0]
        assert isinstance(first_page["Contents"], PdfStream)


def test_invalid_pdfs() -> None:
    """Tests invalid PDF scenarios. The cases included should all fail."""

    # "PDF" with no header
    with pytest.raises(PdfParseError):
        PdfReader(b"The content doesn't matter. The header not being here does.")

    # PDF with an invalid \\Length in stream
    with pytest.raises(PdfParseError):
        with PdfReader("tests/docs/pdf-with-bad-stream.pdf") as reader:
            reader.get_object((1, 0))


def test_incremental_pdf() -> None:
    """Tests incremental PDF parsing by checking whether the correct trailer was
    selected and whether the cross-reference tables were correctly merged."""
    with PdfReader("tests/docs/pdf2-incremental.pdf") as reader:
        assert len(reader.updates) == 2
        assert reader.trailer["Size"] == len(reader.xref)


def test_pdf_with_data_at_start() -> None:
    """Tests a PDF starting with data other than the %PDF-n.m header, which is
    allowed under strict=False and allowed by the spec since PDF 2.0, though this
    behavior is discouraged.
    """
    with PdfReader("tests/docs/pdf2-with-data-at-start.pdf") as reader:
        assert reader.header_version == "2.0"
        assert reader.trailer["Root"]["Type"].value == b"Catalog"


def test_pdf_with_xref_stream() -> None:
    """Tests a PDF document with a compressed XRef stream"""
    with PdfReader("tests/docs/compressed-xref.pdf") as reader:
        catalog = reader.trailer["Root"]
        first_page = catalog["Pages"]["Kids"][0]
        stream = first_page["Contents"].decode()

        assert stream.startswith(b"q\n0.000008871 0 595.32 841.92 re\n")


def test_pdf_with_strict_mode() -> None:
    """Tests a PDF document with a wrong XRef offset. Asserts that it will not
    open with strict=True and asserts that pdfnaut will correct it otherwise."""

    with pytest.raises(PdfParseError):
        PdfReader("tests/docs/random-annots.pdf", strict=True)

    with PdfReader("tests/docs/random-annots.pdf", strict=False) as reader:
        catalog = reader.trailer["Root"]
        assert catalog["Type"].value == b"Catalog"
