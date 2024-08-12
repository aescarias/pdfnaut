# Unit tests for parsing a subset of handcrafted and example files.
import pytest

from pdfnaut.cos import PdfParser
from pdfnaut.cos.objects import PdfStream
from pdfnaut.exceptions import PdfParseError


def test_simple_pdf() -> None:
    """Tests a simple PDF. In this context, "simple" means an unencrypted PDF 
    with no compression and few pages of content."""
    with open("tests/docs/sample.pdf", "rb") as data:
        parser = PdfParser(data.read())
        parser.parse()

        assert len(parser.xref) == parser.trailer["Size"]
        
        catalog = parser.trailer["Root"]
        metadata = parser.trailer["Info"]
        assert catalog is not None and metadata is not None
        
        first_page = catalog["Pages"]["Kids"][0]
        assert isinstance(first_page["Contents"], PdfStream)


def test_invalid_pdfs() -> None:
    """Tests invalid PDF scenarios. The cases included should all fail."""
    # "PDF" with no header
    with pytest.raises(PdfParseError):
        parser = PdfParser(b"The content doesn't matter. The header not being here does.")
        parser.parse()

    # PDF with an invalid \\Length in stream
    with pytest.raises(PdfParseError):
        with open("tests/docs/pdf-with-bad-stream.pdf", "rb") as data:
            parser = PdfParser(data.read())
            parser.parse()

            parser.get_object((1, 0))


def test_pdf_with_incremental() -> None:
    """Tests whether an incremental PDF is parsed correctly. Basically, whether the 
    correct trailer is provided and whether the XRefs are merged."""
    with open("tests/docs/pdf2-incremental.pdf", "rb") as data:
        parser = PdfParser(data.read())
        parser.parse()
        
        assert len(parser.updates) == 2
        assert parser.trailer["Size"] == len(parser.xref)


def test_pdf_with_xref_stream() -> None:
    """Tests a PDF document with a compressed XRef stream"""
    with open("tests/docs/compressed-xref.pdf", "rb") as data:
        parser = PdfParser(data.read())
        parser.parse()

        catalog = parser.trailer["Root"]
        first_page = catalog["Pages"]["Kids"][0]
        stream = first_page["Contents"].decode()

        assert stream.startswith(b"q\n0.000008871 0 595.32 841.92 re\n") 


def test_pdf_with_strict_mode() -> None:
    """Tests a PDF document with a wrong XRef offset. Asserts that it will not open with strict=True."""
    with pytest.raises(PdfParseError):
        with open("tests/docs/random-annots.pdf", "rb") as data:
            parser = PdfParser(data.read(), strict=True)
            parser.parse()

    with open("tests/docs/random-annots.pdf", "rb") as data:
        parser = PdfParser(data.read(), strict=False)
        parser.parse()

        catalog = parser.trailer["Root"]
        assert catalog["Type"].value == b"Catalog"
