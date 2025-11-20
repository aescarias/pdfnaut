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


def test_read_outlines() -> None:
    pdf = PdfDocument.from_filename(r"tests\docs\usenix-example-paper.pdf")
    assert pdf.outline is not None

    assert len(pdf.outline.children)
    assert pdf.outline.children[0].text == "USENIX Example Paper"


def test_insert_pages_to_new_doc() -> None:
    pdf = PdfDocument.new()

    page1 = Page(size=(595, 842))
    page1["Ident"] = b"It is me!"

    page2 = Page(size=(595, 842))
    page2["Ident"] = b"I'm another page!"

    pdf.pages.insert(0, page1)
    pdf.pages.insert(0, page2)

    assert pdf.pages[0]["Ident"] == page2["Ident"]
    assert pdf.pages[1]["Ident"] == page1["Ident"]


def test_add_pages_to_doc_with_flat_tree() -> None:
    origin_pdf = PdfDocument.from_filename(r"tests\docs\pdf2-incremental.pdf")

    origin_pdf.pages.append(Page(size=(500, 500)))
    origin_pdf.pages.insert(0, Page(size=(300, 300)))

    origin_pdf.save(docdata := BytesIO())

    new_pdf = PdfDocument(docdata.getvalue())

    assert len(new_pdf.pages) == 3
    assert new_pdf.pages[0].mediabox == PdfArray([0, 0, 300, 300])
    assert new_pdf.pages[-1].mediabox == PdfArray([0, 0, 500, 500])


def test_add_pages_to_doc_with_nested_tree() -> None:
    orig_pdf = PdfDocument.from_filename(r"tests\docs\pdf-with-page-tree.pdf")

    orig_pdf.pages.append(p1 := Page(size=(500, 500)))
    orig_pdf.pages.insert(0, p2 := Page(size=(300, 300)))

    assert p1.indirect_ref is not None and p2.indirect_ref is not None
    orig_pdf.save(docdata := BytesIO())

    # saved changes
    saved_pdf = PdfDocument(docdata.getvalue())
    assert len(saved_pdf.pages) == 6
    assert saved_pdf.pages[0].mediabox == PdfArray([0, 0, 300, 300])
    assert saved_pdf.pages[-1].mediabox == PdfArray([0, 0, 500, 500])


def test_remove_pages_from_doc() -> None:
    # flat tree
    pdf = PdfDocument.from_filename(r"tests\docs\pdf2-incremental.pdf")

    last_page = pdf.pages[-1]
    assert pdf.pages.pop() is last_page
    assert last_page.indirect_ref is None
    assert len(pdf.pages) == 0

    # nested tree
    pdf = PdfDocument.from_filename(r"tests\docs\pdf-with-page-tree.pdf")

    second_page = pdf.pages[1]
    assert pdf.pages.pop(1) is second_page
    assert second_page.indirect_ref is None
    assert len(pdf.pages) == 3

    # nested tree via delitem
    pdf = PdfDocument.from_filename(r"tests\docs\pdf-with-page-tree.pdf")

    second_page = pdf.pages[1]
    del pdf.pages[1]

    assert second_page.indirect_ref is None
    assert len(pdf.pages) == 3


def test_replace_page() -> None:
    pdf = PdfDocument.from_filename("tests/docs/pdf-with-page-tree.pdf")

    prev_page = pdf.pages[0]
    new_page = Page(size=(612.4, 791))
    new_page["Ident"] = b"It is me!"

    pdf.pages[0] = new_page

    # check if the replacement invalidated the previous page's reference
    assert prev_page.indirect_ref is None
    assert new_page.indirect_ref is not None

    # check our work
    assert pdf.pages[0] is new_page


def test_replace_page_from_doc_to_doc() -> None:
    origin_pdf = PdfDocument.from_filename(r"tests\docs\pdf-with-page-tree.pdf")
    replacing_pdf = PdfDocument.from_filename(r"tests\docs\pdf2-incremental.pdf")

    origin_pdf.pages[0] = replacing_pdf.pages[0]

    replaced_page = origin_pdf.pages[0]
    source_page = replacing_pdf.pages[0]

    assert replaced_page.indirect_ref != source_page.indirect_ref


def test_index_page() -> None:
    origin_pdf = PdfDocument.from_filename(r"tests\docs\usenix-example-paper.pdf")

    page = origin_pdf.pages[2]
    assert origin_pdf.pages.index(page) == 2
    assert origin_pdf.pages.count(page) == 1  # page is present
