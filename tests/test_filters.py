from __future__ import annotations

from typing import cast

from pdfnaut import PdfParser
from pdfnaut.cos.objects import PdfStream
from pdfnaut.filters import ASCII85Filter, ASCIIHexFilter, FlateFilter, RunLengthFilter


def test_ascii() -> None:
    assert ASCIIHexFilter().decompress(b"50444673>") == b"PDFs"
    assert ASCII85Filter().decompress(b":ddco~>") == b"PDFs"

    assert ASCIIHexFilter().compress(b"band") == b"62616E64>"
    assert ASCII85Filter().compress(b"band") == b"@UX.b~>"


def test_flate() -> None:
    # No predictor
    encoded_str = b"x\x9c\x0bpq+\x06\x00\x03\x0f\x01N"
    assert FlateFilter().decompress(encoded_str) == b"PDFs"
    assert FlateFilter().compress(b"PDFs") == encoded_str


def test_rle() -> None:
    with open("tests/docs/river-rle-image.pdf", "rb") as fp:
        pdf = PdfParser(fp.read())
        pdf.parse()

        rle_stream = cast(PdfStream, pdf.get_object((3, 0)))

        with (
            open("tests/docs/filters/rle-input.jpg", "rb") as input_image,
            open("tests/docs/filters/rle-output.bin", "rb") as output,
        ):
            assert RunLengthFilter().decompress(rle_stream.raw) == input_image.read()

            input_image.seek(0)
            assert RunLengthFilter().compress(input_image.read()) == output.read()
