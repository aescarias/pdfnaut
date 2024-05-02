from pdfnaut.filters import ASCIIHexFilter, ASCII85Filter, FlateFilter

def test_ascii() -> None:
    assert ASCIIHexFilter().decode(b"50444673>") == b"PDFs"
    assert ASCII85Filter().decode(b":ddco~>") == b"PDFs"

def test_flate() -> None:
    # No predictor
    assert FlateFilter().decode(b"x\x9c\x0bpq+\x06\x00\x03\x0f\x01N") == b"PDFs"
