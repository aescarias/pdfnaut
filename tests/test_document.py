from __future__ import annotations

from io import BytesIO

from pdfnaut import PdfDocument
from pdfnaut.cos.objects import PdfArray
from pdfnaut.objects import Page


def test_get_object() -> None:
    # Document with traditional xref table
    pdf = PdfDocument.from_filename(r"tests\docs\pdf2-incremental.pdf")

    assert pdf.objects[1] is pdf.catalog
    assert pdf.get_object((1, 0), cache=False) is not pdf.objects[1]

    # Document with compressed xref table
    pdf = PdfDocument.from_filename(r"tests\docs\compressed-xref.pdf")

    assert pdf.objects[1] is pdf.page_tree
    assert pdf.get_object((1, 0), cache=False) is not pdf.objects[1]


def test_add_pages_to_doc_with_flat_tree() -> None:
    orig_pdf = PdfDocument.from_filename(r"tests\docs\pdf2-incremental.pdf")

    orig_pdf.pages.append(Page(size=(500, 500)))

    orig_pdf.pages.insert(0, Page(size=(300, 300)))

    orig_pdf.save(docdata := BytesIO())

    new_pdf = PdfDocument(docdata.getvalue())

    assert len(new_pdf.pages) == 3
    assert new_pdf.pages[0].mediabox == PdfArray([0, 0, 300, 300])
    assert new_pdf.pages[-1].mediabox == PdfArray([0, 0, 500, 500])


def test_add_pages_to_doc_with_nested_tree() -> None:
    orig_pdf = PdfDocument.from_filename(r"tests\docs\pdf-with-page-tree.pdf")

    orig_pdf.pages.append(Page(size=(500, 500)))

    orig_pdf.pages.insert(0, Page(size=(300, 300)))

    orig_pdf.save(docdata := BytesIO())

    new_pdf = PdfDocument(docdata.getvalue())

    assert len(new_pdf.pages) == 6
    assert new_pdf.pages[0].mediabox == PdfArray([0, 0, 300, 300])
    assert new_pdf.pages[-1].mediabox == PdfArray([0, 0, 500, 500])
