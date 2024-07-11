Reading a PDF
=============

PDFs are, in essence, conformed of objects and references. You can access the objects of a PDF through means of its cross-reference table. Think of a PDF like JSON but with a way of tracking its objects.

Opening a PDF
-------------

To read a PDF with pdfnaut, use the :class:`~pdfnaut.parsers.pdf.PdfParser` class which accepts a ``bytes`` string with the contents of your file.

.. code-block:: python

    import pdfnaut

    with open("document.pdf", "rb") as fp:
        pdf = pdfnaut.PdfParser(fp.read())
        pdf.parse()

:meth:`~pdfnaut.parsers.pdf.PdfParser.parse` is responsible for processing the cross-reference table and the trailer in the PDF. These are needed to retrieve objects from the document.

Inspecting objects
------------------

The next set of steps will depend on the document being processed. To inspect the objects included in the PDF before going further, iterate over the :attr:`~pdfnaut.parsers.pdf.PdfParser.xref` attribute in :class:`~pdfnaut.parsers.pdf.PdfParser` as follows:

.. code-block:: python

    for reference, entry in parser.xref.itms():
        if hasattr(entry, "next_free_object"):
            continue

        print(pdf.resolve_reference(reference)) 

Because the XRef table can also include "free" or unused entries, we avoid iterating over them. Then we provide the reference to :meth:`~pdfnaut.parsers.pdf.PdfParser.resolve_reference`. This should print all the objects in the PDF.

Traversing a document
---------------------

Let's take, for example, the ``sample.pdf`` file available in our `test suite <https://github.com/aescarias/pdfnaut/tree/main/tests/docs>`_. To extract the contents of a page, we must first find the document's catalog. The catalog includes information useful for locating other objects in the PDF. The catalog is stored in the ``Root`` key of the document's trailer.

.. code-block:: python

    >>> root = pdf.resolve_reference(pdf.trailer["Root"])
    >>> root
    {'Outlines': PdfIndirectRef(object_number=2, generation=0),
     'Pages': PdfIndirectRef(object_number=3, generation=0),
     'Type': PdfName(value=b'Catalog')}

Two objects of note can be found: Outlines and Pages. ``Outlines`` stores what we commonly refer to as bookmarks. ``Pages`` stores the page tree, which is what we are interested in:

.. code-block:: python

    >>> page_tree = pdf.resolve_reference(root["Pages"]) 
    >>> page_tree
    {'Count': 2,
     'Kids': [PdfIndirectRef(object_number=4, generation=0),
              PdfIndirectRef(object_number=6, generation=0)],
     'Type': PdfName(value=b'Pages')}

The page tree is seen above. Given that this document only includes 2 pages, they are specified as "kids" in the root node. For larger documents, it is not uncommon to divide the pages into multiple nodes for performance reasons. Next, we can extract the first page of the document:

.. code-block:: python

    >>> first_page = pdf.resolve_reference(page_tree["Kids"][0])
    >>> first_page
    {'Contents': PdfIndirectRef(object_number=5, generation=0),
     'MediaBox': [0, 0, 612.0, 792.0],
     'Parent': PdfIndirectRef(object_number=3, generation=0),
     'Resources': {
        'Font': {'F1': PdfIndirectRef(object_number=9, generation=0)},
        'ProcSet': PdfIndirectRef(object_number=8, generation=0)
     },
     'Type': PdfName(value=b'Page')
    }

Above we see the actual page. This dictionary includes the *media box* which specifies the dimensions of the page when shown, a reference to its parent, the resources used such as the font, and the contents of the page. We are looking for the contents of the page. Given that the Contents key includes a stream, it is set as an indirect reference. 

.. code-block:: python

    >>> page_contents = pdf.resolve_reference(first_page["Contents"])
    >>> page_contents
    PdfStream(details={'Length': 1074})

We find ourselves with a stream. The contents of pages are defined in streams known as **content streams**. This kind of stream includes instructions on how a PDF processor should render this page. In this case, it is not compressed (it does not have a Filter). So we can easily read it:

.. code-block:: python

    >>> page_contents.decompress()
    b'2 J\r\nBT\r\n0 0 0 rg\r\n/F1 0027 Tf\r\n57.3750 722.2800 Td\r\n( A Simple PDF File ) Tj\r\nET\r\nBT\r\n/F1 0010 Tf\r\n69.2500 688.6080 Td\r\n[...]ET\r\n'

A content stream is comprised of operators and operands (where operands are specified first). In this case, it would simply write "A Simple PDF File" at the position defined by the Td operands (and with the font /F1 included in our Resources which, in this case, points to Helvetica).
