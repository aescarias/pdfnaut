import pytest

from pdfnaut.parsers import PdfParser
from pdfnaut.objects import PdfStream, PdfIndirectRef
from pdfnaut.exceptions import PdfParseError

def test_simple_pdf() -> None:
    with open("tests/docs/sample.pdf", "rb") as data:
        parser = PdfParser(data.read())
        parser.parse()

        xref = parser.xref.sections[0]

        assert len(xref.entries) == xref.count
        assert len(xref.entries) == parser.trailer["Size"]

        catalog = parser.resolve_reference(parser.trailer["Root"])
        metadata = parser.resolve_reference(parser.trailer["Info"])
        assert catalog is not None and metadata is not None
        
        pages = parser.resolve_reference(catalog["Pages"])
        first_page = parser.resolve_reference(pages["Kids"][0])
        first_page_contents = parser.resolve_reference(first_page["Contents"])
        assert isinstance(first_page_contents, PdfStream)

def test_invalid_pdfs() -> None:
    # "PDF" with no header
    with pytest.raises(PdfParseError):
        parser = PdfParser(b"The content doesn't matter. The header not being here does.")
        parser.parse()

    # PDF with an invalid \\Length in stream
    with pytest.raises(ValueError):
        with open("tests/docs/pdf-with-bad-stream.pdf", "rb") as data:
            parser = PdfParser(data.read())
            parser.parse()
            parser.resolve_reference(PdfIndirectRef(1, 0))

def test_pdf_with_incremental() -> None:
    with open("tests/docs/pdf2-incremental.pdf", "rb") as data:
        parser = PdfParser(data.read())
        parser.parse()
        
        assert len(parser.update_xrefs) == 2 and len(parser._trailers) == 2
        assert parser.trailer["Size"] == parser.xref.sections[0].count

def test_pdf_with_xref_stream() -> None:
    with open("tests/docs/super-compressed.pdf", "rb") as data:
        parser = PdfParser(data.read())
        parser.parse()

        catalog = parser.resolve_reference(parser.trailer["Root"])
        pages = parser.resolve_reference(catalog["Pages"])
        first_page = parser.resolve_reference(pages["Kids"][0])
        stream = parser.resolve_reference(first_page["Contents"]).decompress()

        assert stream.startswith(b"q\n0.000008871 0 595.32 841.92 re\n") 