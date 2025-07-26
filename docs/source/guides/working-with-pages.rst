Working with Pages
==================

Pages are the contents that make up a PDF document. In PDFs, pages are stored in a tree structure known as the page tree. For simpler documents, it is usually a flat tree, but for larger documents, it may be comprised of multiple branches or leaf nodes for optimization purposes.

The *page object* (represented as :class:`.Page`) contains information about the page's contents, resources, and appearance. 

Accessing Pages
---------------

Direct access to the page tree is possible via :attr:`.PdfDocument.page_tree`. However, in typical usage, you will want to use :attr:`.PdfDocument.pages` instead which provides a page list that abstracts the tree structure into a flat collection of pages.

.. code-block:: python

    from pdfnaut import PdfDocument

    pdf = PdfDocument.from_filename(r"tests/docs/usenix-example-paper.pdf")
    print(pdf.pages)     # <pdfnaut.page_list.PageList object at ...>
    print(pdf.pages[0])  # <Page mediabox=[0, 0, 612, 792] rotation=0>

The page list mostly behaves like any other Python sequence and so operations commonly performed on those should work similarly in a page list.

- To access the first page of a PDF, you do ``pdf.pages[0]``.
- To access the last page, you do ``pdf.pages[-1]``.
- The length of the page list can be obtained via ``len(pdf.pages)``.
- The page list also supports accessing items via slicing so something like ``pdf.pages[2:5]`` is allowed.

Modifying Pages
---------------

As the :class:`.Page` objects inherits from a :class:`.PdfDictionary`, you can modify its contents as you would any other mapping (for details on the entries in a page object, see § 7.7.3.3, "Page objects" in the PDF 2.0 specification).

See the example below:

.. code-block:: python

    from pdfnaut import PdfDocument
    from pdfnaut.cos.objects import PdfArray

    pdf = PdfDocument.from_filename(r"tests/docs/usenix-example-paper.pdf")

    pdf.pages[0]["CropBox"] = PdfArray([10, 10, 200, 200])

In this example, the ``CropBox`` property is modified so that a visual crop starting at position (10, 10) and ending at position (200, 200) takes place.

For commonly accessed properties, you may also access and modify them in attribute form:

.. code-block:: python

    pdf.pages[0].cropbox = PdfArray([10, 10, 200, 200])

This performs the same action described in the previous example.


Inserting Pages
---------------

One of the most common operations performed when manipulating PDFs is from a set of actions known as *page assembly*. Page assembly generally refers to the process of inserting and removing pages from a document.

To insert pages to a PDF, you can use the :meth:`.PageList.append` and :meth:`.PageList.insert` methods.

.. code-block:: python

    from pdfnaut import PdfDocument
    from pdfnaut.objects import Page

    pdf = PdfDocument.from_filename(r"tests/docs/usenix-example-paper.pdf")

    pdf.pages.append(Page(size=(595, 842)))

In the above example, a blank A4-size page is appended to the end of the document.

You may also insert pages from a different document.

.. code-block:: python

    from pdfnaut import PdfDocument

    pdf1 = PdfDocument.from_filename(r"tests/docs/usenix-example-paper.pdf")
    pdf2 = PdfDocument.from_filename(r"tests/docs/pdf2-incremental-pdf")

    pdf1.pages.insert(2, pdf2.pages[0])

The example above inserts a page from the second PDF into the second position (before the third page). 

Two things should be noted here:

1. Unless the page is newly created, the page contents are always copied into the document. 
2. Elements such as form widgets or certain types of annotations will not be preserved or are unlikely to work as these are fundamentally dependent on the document itself rather than the page they're being used in.

It is also possible to append multiple pages to a PDF using the :meth:`.PageList.extend` method.


Removing Pages
--------------

pdfnaut also allows removing pages via the :meth:`.PageList.pop` method.

.. code-block:: python

    from pdfnaut import PdfDocument
    from pdfnaut.objects import Page

    pdf = PdfDocument.from_filename(r"tests/docs/usenix-example-paper.pdf")

    pdf.pages.pop(0)

In the above example, this pops the first page in the document.

Removing pages via the ``del`` operation is also supported: ``del pdf.pages[n]``.
