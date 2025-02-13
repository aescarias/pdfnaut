from __future__ import annotations

import datetime
from typing import Any, cast

from pdfnaut import PdfDocument

# from pdfnaut.cos.objects.nomore_date import PdfDate


def test_docinfo() -> None:
    """Tests the DocInfo dictionary in a PDF file."""
    document = PdfDocument.from_filename("tests/docs/sample.pdf")

    assert document.doc_info is not None
    assert document.doc_info.author is None
    assert document.doc_info.creator == "Rave (http://www.nevrona.com/rave)"
    assert document.doc_info.producer == "Nevrona Designs"
    assert document.doc_info.creation_date_raw == "D:20060301072826"
    assert document.doc_info.creation_date == PdfDate(2006, 3, 1, 7, 28, 26)

    document.doc_info.subject = "Hello, world!"
    assert cast("dict[str, Any]", document.trailer["Info"])["Subject"] == b"Hello, world!"


def test_xmp_metadata() -> None:
    """Tests the DocInfo dictionary in a PDF file."""
    document = PdfDocument.from_filename("tests/docs/pdf2-incremental.pdf")

    assert document.xmp_metadata is not None

    assert document.xmp_metadata.producer == "Datalogics - example producer program name here"
    assert document.xmp_metadata.create_date == datetime.datetime(
        2017, 5, 24, 10, 30, 11, tzinfo=datetime.timezone.utc
    )
    assert document.xmp_metadata.file_format == "application/pdf"

    titles = document.xmp_metadata.titles
    assert len(titles) == 1 and titles["x-default"] == "A simple PDF 2.0 example file"

    creators = document.xmp_metadata.creators
    assert len(creators) == 1 and creators[0] == "Datalogics Incorporated"
