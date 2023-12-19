import pytest

from pdfnaut.parse import PdfParser, PdfParseError
from pdfnaut.types import PdfStream, PdfIndirectRef

# TODO: Add more tests as the library evolves
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

def test_unsupported_pdf() -> None:
    # This PDF has its XRef compressed
    with pytest.raises(NotImplementedError):
        with open("tests/docs/super-compressed.pdf", "rb") as data:
            parser = PdfParser(data.read())
            parser.parse()

def test_pdf_with_incremental() -> None:
    with open("tests/docs/pdf2-incremental.pdf", "rb") as data:
        parser = PdfParser(data.read())
        parser.parse()
        
        assert len(parser.update_xrefs) == 2 and len(parser._trailers) == 2
        