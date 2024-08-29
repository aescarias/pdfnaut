Reading a PDF
=============

PDFs are, in essence, conformed of objects and references. You can access the objects of a PDF through means of its cross-reference table. Think of a PDF like JSON but with a way of tracking its objects.

Opening a PDF
-------------

To read a PDF with pdfnaut, use the :class:`~pdfnaut.cos.parser.PdfParser` class which accepts a ``bytes`` string with the contents of your file.

.. code-block:: python

    import pdfnaut

    with open("document.pdf", "rb") as fp:
        pdf = pdfnaut.PdfParser(fp.read())
        pdf.parse()

:meth:`~pdfnaut.cos.parser.PdfParser.parse` is responsible for processing the cross-reference table and the trailer in the PDF. These are needed to retrieve objects from the document. 

Inspecting objects
------------------

The next set of steps will depend on the document being processed. To inspect the objects included in the PDF before going further, iterate over the :attr:`~pdfnaut.cos.parser.PdfParser.xref` attribute in :class:`~pdfnaut.cos.parser.PdfParser` as follows:

.. code-block:: python

    for reference, entry in parser.xref.items():
        if hasattr(entry, "next_free_object"):
            continue

        print(pdf.get_object(reference)) 

Because the XRef table can also include "free" or unused entries, we avoid iterating over them. Then we provide the reference to :meth:`~pdfnaut.cos.parser.PdfParser.get_object`. This should print all the objects in the PDF.

Traversing a document
---------------------

Let's take, for example, the ``sample.pdf`` file available in our `test suite <https://github.com/aescarias/pdfnaut/tree/main/tests/docs>`_. To extract the contents of a page, we must first find the document's catalog. The catalog includes information useful for locating other objects in the PDF. The catalog is stored in the ``Root`` key of the document's trailer.

.. code-block:: python

    >>> root = pdf.trailer["Root"]
    >>> root
    {'Outlines': PdfReference(object_number=2, generation=0),
     'Pages': PdfReference(object_number=3, generation=0),
     'Type': PdfName(value=b'Catalog')}

Two objects of note can be found: Outlines and Pages. ``Outlines`` stores what we commonly refer to as bookmarks. ``Pages`` stores the page tree, which is what we are interested in:

.. note::

    To avoid wrapping each dictionary or array index call with :meth:`~pdfnaut.cos.parser.PdfParser.get_object`, pdfnaut and other PDF libraries will automatically resolve these references when indexing. If you are interested in the actual references, both :class:`~pdfnaut.cos.objects.containers.PdfArray` and :class:`~pdfnaut.cos.objects.containers.PdfDictionary` have a ``raw_at`` method available.

.. code-block:: python

    >>> root["Pages"]
    {'Count': 2,
     'Kids': [PdfReference(object_number=4, generation=0),
              PdfReference(object_number=6, generation=0)],
     'Type': PdfName(value=b'Pages')}

The page tree is seen above. Given that this document only includes 2 pages, they are specified as "kids" in the root node. In larger documents, it is not uncommon to see a balanced tree dividing the pages into multiple nodes for performance reasons. Next, we can extract the first page of the document:

.. code-block:: python

    >>> first_page = root["Pages"]["Kids"][0]
    >>> first_page
    {'Contents': PdfReference(object_number=5, generation=0),
     'MediaBox': [0, 0, 612.0, 792.0],
     'Parent': PdfReference(object_number=3, generation=0),
     'Resources': {
        'Font': {'F1': PdfReference(object_number=9, generation=0)},
        'ProcSet': PdfReference(object_number=8, generation=0)
     },
     'Type': PdfName(value=b'Page')
    }

Above we see the actual page. This dictionary includes the *media box* which specifies the dimensions of the page when shown, a reference to its parent, the resources used such as the font, and the contents of the page. We are looking for the contents of the page and so we can retrieve the content stream from the Contents key.

.. code-block:: python

    >>> first_page["Contents"]
    PdfStream(details={'Length': 1074})

We find ourselves with a stream. The contents of pages are defined in streams known as **content streams**. This kind of stream includes instructions on how a PDF processor should render this page. In this case, it is not compressed (it does not have a Filter). So we can easily read it:

.. code-block:: python

    >>> first_page["Contents"].decode()
    b'2 J\r\nBT\r\n0 0 0 rg\r\n/F1 0027 Tf\r\n57.3750 722.2800 Td\r\n( A Simple PDF File ) Tj\r\nET\r\nBT\r\n/F1 0010 Tf\r\n69.2500 688.6080 Td\r\n[...]ET\r\n'

A content stream is comprised of operators and operands (where operands are specified first). In this case, it would simply write "A Simple PDF File" at the position defined by the Td operands (and with the font /F1 included in our Resources which, in this case, points to Helvetica).
