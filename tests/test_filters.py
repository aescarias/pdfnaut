from __future__ import annotations

import logging
from typing import cast

import pytest

from pdfnaut import PdfParser
from pdfnaut.cos.objects import PdfStream
from pdfnaut.exceptions import PdfFilterError
from pdfnaut.filters import ASCII85Filter, ASCIIHexFilter, FlateFilter, RunLengthFilter
from pdfnaut.filters._predictors import PNGPredictor, apply_png_prediction, undo_png_prediction


def test_ascii_hex(caplog) -> None:
    # some encoding tests
    # not much to test, except that the EOD marker is appended
    assert ASCIIHexFilter().encode(b"band") == b"62616E64>"
    assert ASCIIHexFilter().encode(b"GIF89a") == b"474946383961>"
    assert ASCIIHexFilter().encode(b"") == b">"

    # simple decoding tests
    assert ASCIIHexFilter().decode(b"50444673>") == b"PDFs"
    assert ASCIIHexFilter().decode(b">") == b""

    # decoder must accept and ignore whitespace
    assert ASCIIHexFilter().decode(b"50\x0044\r\n46 73>") == b"PDFs"

    # decoder must allow mixed-case hexadecimal
    assert ASCIIHexFilter().decode(b"ab CD eF Ab>") == b"\xab\xcd\xef\xab"

    # decoder must pad odd-length byte sequences with "0"
    assert ASCIIHexFilter().decode(b"abcde>") == b"\xab\xcd\xe0"

    # decoder must raise error on invalid characters
    with pytest.raises(PdfFilterError):
        ASCIIHexFilter().decode(b"abcdefgh>")

    # decoder should warn on missing EOD
    with caplog.at_level(logging.WARNING):
        assert ASCIIHexFilter().decode(b"62 61 6E 64>") == b"band"

    # decoder should discard data after the first EOD found
    assert ASCIIHexFilter().decode(b"64 61 74 61>72 65>61 64") == b"data"


def test_ascii_85() -> None:
    assert ASCII85Filter().decode(b":ddco~>") == b"PDFs"
    assert ASCII85Filter().encode(b"band") == b"@UX.b~>"


def test_flate() -> None:
    # No predictor
    encoded_str = b"x\x9c\x0bpq+\x06\x00\x03\x0f\x01N"
    assert FlateFilter().decode(encoded_str) == b"PDFs"
    assert FlateFilter().encode(b"PDFs") == encoded_str


def test_rle() -> None:
    with open("tests/docs/river-rle-image.pdf", "rb") as fp:
        pdf = PdfParser(fp.read())
        pdf.parse()

        rle_stream = cast(PdfStream, pdf.get_object((3, 0)))

        with (
            open("tests/docs/filters/rle-input.jpg", "rb") as input_image,
            open("tests/docs/filters/rle-output.bin", "rb") as output,
        ):
            assert RunLengthFilter().decode(rle_stream.raw) == input_image.read()

            input_image.seek(0)
            assert RunLengthFilter().encode(input_image.read()) == output.read()


def test_png_predictors():
    # PNG None
    raw_data = bytearray([10, 20, 30, 15, 25, 35, 20, 30, 40])
    decode_params = {"columns": 3, "colors": 1, "bpc": 8}

    encoded = apply_png_prediction(raw_data, PNGPredictor.NONE, **decode_params)
    assert encoded == bytearray([0, 10, 20, 30, 0, 15, 25, 35, 0, 20, 30, 40])

    decoded = undo_png_prediction(encoded, **decode_params)
    assert decoded == raw_data

    # PNG Sub (round-trip)
    encoded = apply_png_prediction(raw_data, PNGPredictor.SUB, **decode_params)
    assert encoded == bytearray([1, 10, 10, 10, 1, 15, 10, 10, 1, 20, 10, 10])

    decoded = undo_png_prediction(encoded, **decode_params)
    assert decoded == raw_data

    # PNG Paeth (round-trip)
    encoded = apply_png_prediction(raw_data, PNGPredictor.PAETH, **decode_params)
    assert encoded == bytearray([4, 10, 10, 10, 4, 5, 5, 5, 4, 5, 5, 5])

    decoded = undo_png_prediction(encoded, **decode_params)
    assert decoded == raw_data

    # PNG Optimum
    encoded = apply_png_prediction(raw_data, PNGPredictor.OPTIMUM, **decode_params)
    assert encoded == bytearray([1, 10, 10, 10, 2, 5, 5, 5, 2, 5, 5, 5])

    decoded = undo_png_prediction(encoded, **decode_params)
    assert decoded == raw_data
