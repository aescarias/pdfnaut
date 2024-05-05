from pdfnaut.filters import ASCIIHexFilter, ASCII85Filter, FlateFilter, RunLengthFilter
from pdfnaut import PdfParser

def test_ascii() -> None:
    assert ASCIIHexFilter().decode(b"50444673>") == b"PDFs"
    assert ASCII85Filter().decode(b":ddco~>") == b"PDFs"

    assert ASCIIHexFilter().encode(b"band") == b"62616E64>"
    assert ASCII85Filter().encode(b"band") == b"@UX.b~>"

def test_flate() -> None:
    # No predictor
    encoded_str = b"x\x9c\x0bpq+\x06\x00\x03\x0f\x01N"
    assert FlateFilter().decode(encoded_str) == b"PDFs"
    assert FlateFilter().encode(b"PDFs") == encoded_str

def test_rle() -> None:
    with open("tests/docs/shapes-rle.pdf", "rb") as fp:
        pdf = PdfParser(fp.read())
        pdf.parse()

        ref = pdf.resolve_reference((8, 0))

        with open("tests/docs/shapes-decoded.bin", "rb") as binfp:
            assert RunLengthFilter().decode(ref.raw) == binfp.read()
