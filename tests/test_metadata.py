from __future__ import annotations

import datetime
from io import BytesIO

import pdfnaut
from pdfnaut import PdfDocument
from pdfnaut.objects.catalog import ViewerPreferences
from pdfnaut.objects.xmp import XmpMetadata


def test_docinfo_read() -> None:
    pdf = PdfDocument.from_filename(r"tests\docs\sample.pdf")

    assert pdf.doc_info is not None

    assert pdf.doc_info.creator == "Rave (http://www.nevrona.com/rave)"

    assert pdf.doc_info.creation_date == datetime.datetime(
        2006, 3, 1, 7, 28, 26, tzinfo=datetime.timezone.utc
    )


def test_docinfo_write() -> None:
    original_pdf = PdfDocument.from_filename(r"tests\docs\sample.pdf")
    assert original_pdf.doc_info is not None

    # we don't need the microsecond since iso 8824 doesn't support them
    modify_date = datetime.datetime(2025, 3, 2, 15, 51, 0, tzinfo=datetime.timezone.utc)

    original_pdf.doc_info.title = "Sample PDF file"
    original_pdf.doc_info.modify_date = modify_date

    original_pdf.save((fp := BytesIO()))

    fp.seek(0)

    edited_pdf = PdfDocument(fp.read())
    assert edited_pdf.doc_info is not None

    assert edited_pdf.doc_info.title == "Sample PDF file"
    assert edited_pdf.doc_info.modify_date == modify_date


def test_docinfo_remove() -> None:
    original_pdf = PdfDocument.from_filename(r"tests\docs\sample.pdf")
    original_pdf.doc_info = None

    original_pdf.save((fp := BytesIO()))

    fp.seek(0)

    edited_pdf = PdfDocument(fp.read())
    assert edited_pdf.doc_info is None


def test_xmp_read() -> None:
    original_pdf = PdfDocument.from_filename(r"tests\docs\pdf2-incremental.pdf")

    assert original_pdf.xmp_info is not None

    # Text property
    assert original_pdf.xmp_info.pdf_producer == "Datalogics - example producer program name here"

    # Date property
    assert original_pdf.xmp_info.xmp_create_date == datetime.datetime(
        2017, 5, 24, 10, 30, 11, tzinfo=datetime.timezone.utc
    )

    # Language alternate property
    assert original_pdf.xmp_info.dc_title == {"x-default": "A simple PDF 2.0 example file"}

    # List property
    assert original_pdf.xmp_info.dc_creator == ["Datalogics Incorporated"]


def test_xmp_write() -> None:
    original_pdf = PdfDocument.from_filename(r"tests\docs\river-rle-image.pdf")

    original_pdf.xmp_info = XmpMetadata()

    # Text property
    original_pdf.xmp_info.pdf_producer = f"pdfnaut {pdfnaut.__version__}"

    # Date property
    dt = datetime.datetime(2025, 7, 14, 0, 0, 47, 125681, tzinfo=datetime.timezone.utc)

    original_pdf.xmp_info.xmp_create_date = dt
    original_pdf.xmp_info.xmp_modify_date = dt

    # Language alternate property
    original_pdf.xmp_info.dc_title = {"x-default": "The Tetons and the Snake River"}

    # List property
    original_pdf.xmp_info.dc_creator = ["Ansel Adams"]

    original_pdf.save((fp := BytesIO()))

    fp.seek(0)

    edited_pdf = PdfDocument(fp.read())
    assert edited_pdf.xmp_info is not None

    assert edited_pdf.xmp_info.pdf_producer == f"pdfnaut {pdfnaut.__version__}"
    assert edited_pdf.xmp_info.xmp_create_date == dt
    assert edited_pdf.xmp_info.xmp_modify_date == dt
    assert edited_pdf.xmp_info.dc_title == {"x-default": "The Tetons and the Snake River"}
    assert edited_pdf.xmp_info.dc_creator == ["Ansel Adams"]


def test_xmp_remove() -> None:
    original_pdf = PdfDocument.from_filename(r"tests\docs\pdf2-incremental.pdf")
    original_pdf.xmp_info = None

    original_pdf.save((fp := BytesIO()))

    fp.seek(0)

    edited_pdf = PdfDocument(fp.read())
    assert edited_pdf.xmp_info is None


def test_viewer_preferences() -> None:
    original_pdf = PdfDocument.from_filename(r"tests\docs\wikipedia-xmp.pdf")

    assert original_pdf.viewer_preferences is not None

    # boolean set in document
    assert original_pdf.viewer_preferences.display_doc_title
    # default value being string for name accessor
    assert original_pdf.viewer_preferences.direction == "L2R"
    # default value being None for name accessor
    assert original_pdf.viewer_preferences.duplex is None


def test_viewer_preferences_save() -> None:
    original_pdf = PdfDocument.from_filename(r"tests\docs\pdf2-incremental.pdf")
    original_pdf.viewer_preferences = ViewerPreferences()
    original_pdf.save(fp := BytesIO())
    fp.seek(0)

    edited_pdf = PdfDocument(fp.read())
    assert edited_pdf.viewer_preferences
    assert not edited_pdf.viewer_preferences.display_doc_title
