from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from pdfnaut.cos.reader import PdfReader
from pdfnaut.cos.writer import PdfWriter


@pytest.mark.parametrize("filename", ["sample.pdf", "compressed-xref.pdf"])
def test_writer_round_trip(filename: str) -> None:
    contents = Path(f"tests/docs/{filename}").read_bytes()
    output = BytesIO()

    with PdfReader(contents) as reader:
        writer = PdfWriter(reader)
        writer.save(output)

    written = output.getvalue()
    assert written.startswith(b"%PDF-2.0")

    with PdfReader(written) as reader:
        assert reader.trailer["Root"]["Type"].value == b"Catalog"
        assert reader.trailer["Size"] == len(reader.xref)
