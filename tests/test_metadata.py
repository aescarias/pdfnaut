from __future__ import annotations

import datetime
from io import BytesIO

import pdfnaut
from pdfnaut import MetadataCopyDirection, PdfDocument
from pdfnaut.objects.catalog import ViewerPreferences
from pdfnaut.objects.xmp import XmpMetadata


def test_docinfo_read() -> None:
    with PdfDocument(r"tests\docs\sample.pdf") as pdf:
        assert pdf.doc_info is not None
        assert pdf.doc_info.creator == "Rave (http://www.nevrona.com/rave)"
        assert pdf.doc_info.creation_date == datetime.datetime(
            2006, 3, 1, 7, 28, 26, tzinfo=datetime.timezone.utc
        )


def test_docinfo_write() -> None:
    fp = BytesIO()

    # we don't need the microsecond since iso 8824 doesn't support them
    modify_date = datetime.datetime(2025, 3, 2, 15, 51, 0, tzinfo=datetime.timezone.utc)

    with PdfDocument(r"tests\docs\sample.pdf") as original_pdf:
        assert original_pdf.doc_info is not None

        original_pdf.doc_info.title = "Sample PDF file"
        original_pdf.doc_info.modify_date = modify_date

        original_pdf.save(fp)

    with PdfDocument(fp) as edited_pdf:
        assert edited_pdf.doc_info is not None

        assert edited_pdf.doc_info.title == "Sample PDF file"
        assert edited_pdf.doc_info.modify_date == modify_date


def test_docinfo_remove() -> None:
    fp = BytesIO()
    with PdfDocument(r"tests\docs\sample.pdf") as original_pdf:
        assert original_pdf.doc_info is not None

        # test removal of attribute
        del original_pdf.doc_info.producer
        assert original_pdf.doc_info.producer is None

        # then remove the doc info completely
        original_pdf.doc_info = None
        original_pdf.save(fp)

    # check that removal was done
    with PdfDocument(fp) as edited_pdf:
        assert edited_pdf.doc_info is None


def test_xmp_read() -> None:
    with PdfDocument(r"tests\docs\pdf2-incremental.pdf") as original_pdf:
        assert original_pdf.xmp_info is not None

        # Text property
        assert (
            original_pdf.xmp_info.pdf_producer == "Datalogics - example producer program name here"
        )

        # Date property
        assert original_pdf.xmp_info.xmp_create_date == datetime.datetime(
            2017, 5, 24, 10, 30, 11, tzinfo=datetime.timezone.utc
        )

        # Language alternate property
        assert original_pdf.xmp_info.dc_title == {"x-default": "A simple PDF 2.0 example file"}

        # List property
        assert original_pdf.xmp_info.dc_creator == ["Datalogics Incorporated"]


def test_xmp_write() -> None:
    fp = BytesIO()
    dt = datetime.datetime(2025, 7, 14, 0, 0, 47, 125681, tzinfo=datetime.timezone.utc)

    with PdfDocument(r"tests\docs\river-rle-image.pdf") as original_pdf:
        original_pdf.xmp_info = XmpMetadata()

        # Text property
        original_pdf.xmp_info.pdf_producer = f"pdfnaut {pdfnaut.__version__}"

        # Date property
        original_pdf.xmp_info.xmp_create_date = dt
        original_pdf.xmp_info.xmp_modify_date = dt

        # Language alternate property
        original_pdf.xmp_info.dc_title = {"x-default": "The Tetons and the Snake River"}

        # List property
        original_pdf.xmp_info.dc_creator = ["Ansel Adams"]

        original_pdf.save(fp)

    with PdfDocument(fp) as edited_pdf:
        assert edited_pdf.xmp_info is not None

        assert edited_pdf.xmp_info.pdf_producer == f"pdfnaut {pdfnaut.__version__}"
        assert edited_pdf.xmp_info.xmp_create_date == dt
        assert edited_pdf.xmp_info.xmp_modify_date == dt
        assert edited_pdf.xmp_info.dc_title == {"x-default": "The Tetons and the Snake River"}
        assert edited_pdf.xmp_info.dc_creator == ["Ansel Adams"]


def test_xmp_remove() -> None:
    fp = BytesIO()
    with PdfDocument(r"tests\docs\pdf2-incremental.pdf") as original_pdf:
        assert original_pdf.xmp_info is not None

        # test removal of attribute first
        del original_pdf.xmp_info.pdf_keywords
        assert original_pdf.xmp_info.pdf_keywords is None

        # then completely remove the xmp metadata
        original_pdf.xmp_info = None

        # check that removal was done
        original_pdf.save(fp)

    with PdfDocument(fp) as edited_pdf:
        assert edited_pdf.xmp_info is None


def test_copy_metadata() -> None:
    with PdfDocument(r"tests\docs\pdf2-incremental.pdf") as pdf:
        assert pdf.doc_info is None
        assert pdf.xmp_info is not None
        pdf.copy_metadata(MetadataCopyDirection.XMP_TO_DOC_INFO)

        assert pdf.doc_info is not None
        assert pdf.doc_info.title == "A simple PDF 2.0 example file"
        assert pdf.doc_info.author == "Datalogics Incorporated"
        assert (
            pdf.doc_info.subject
            == "Demonstration of a simple PDF 2.0 file, including comments related to "
            "differences from earlier PDF revisions and helpful hints about PDF."
        )
        assert pdf.doc_info.keywords == "PDF 2.0 sample example"
        assert pdf.doc_info.creator == "Datalogics - example creator tool name here"
        assert pdf.doc_info.producer == "Datalogics - example producer program name here"
        assert pdf.doc_info.creation_date == datetime.datetime(
            2017, 5, 24, 10, 30, 11, tzinfo=datetime.timezone.utc
        )
        assert pdf.doc_info.modify_date == datetime.datetime(
            2017, 7, 11, 7, 55, 11, tzinfo=datetime.timezone.utc
        )


def test_viewer_preferences() -> None:
    with PdfDocument(r"tests\docs\wikipedia-xmp.pdf") as pdf:
        assert pdf.viewer_preferences is not None

        # boolean set in document
        assert pdf.viewer_preferences.display_doc_title
        # default value being string for name field
        assert pdf.viewer_preferences.direction == "L2R"
        # default value being None for name field
        assert pdf.viewer_preferences.duplex is None


def test_viewer_preferences_save() -> None:
    fp = BytesIO()

    with PdfDocument(r"tests\docs\pdf2-incremental.pdf") as original_pdf:
        original_pdf.viewer_preferences = ViewerPreferences()
        original_pdf.save(fp)

    with PdfDocument(fp) as edited_pdf:
        assert edited_pdf.viewer_preferences
        assert not edited_pdf.viewer_preferences.display_doc_title
