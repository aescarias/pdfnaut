Reading a PDF
=============

.. note::

    The following guide documents the low-level PDF reader class. Unless you are inspecting the internals, use :class:`PdfDocument`.
    
PDFs are, in essence, conformed of objects and references. To locate an object, a PDF file includes a cross-reference table specifying the offset of objects in the document.

Opening a PDF
-------------

To read a PDF with pdfnaut, use :class:`~pdfnaut.cos.reader.PdfReader`. It accepts a file path, a binary stream, or the document contents as ``bytes``. The reader parses the cross-reference data and trailer during construction.

.. code-block:: python

    from pdfnaut import PdfReader

    with PdfReader("document.pdf") as pdf:
        ...

The reader processes the cross-reference data and trailer when it is initialized.

.. warning::

    When providing a filename or file-backed object to :class:`PdfReader`, you must close :class:`PdfReader` to release file handles and resources when finished. This can be done by using :class:`PdfReader` as a context manager (recommended) or by calling :meth:`PdfReader.close` after you are done with the PDF document.

    When providing a file-backed object, :meth:`PdfReader.close` will only release the internal resources used by the reader. It will not close the provided object. this allows you to continue using the file object for other operations in your program.


Inspecting objects
------------------

To inspect the objects included in a PDF before going further, iterate over the :attr:`~pdfnaut.cos.reader.PdfReader.xref` attribute in :class:`~pdfnaut.cos.reader.PdfReader` as follows. The following example should print all objects in a PDF document:

.. code-block:: python

    for reference, entry in pdf.xref.items():
        if isinstance(entry, FreeXRefEntry):
            continue

        print(pdf.get_object(reference))


Because the XRef table can include "free" entries, we skip them using the :meth:`isinstance` check. The reference of the object is then provided to :meth:`~pdfnaut.cos.reader.PdfReader.get_object` so it is resolved into a PDF object. 

Another option is to directly iterate over the object store (:attr:`~pdfnaut.cos.reader.PdfReader.objects`). The object store will automatically resolve the PDF objects, so calling ``get_object()`` is unnecessary.

.. code-block:: python

    for pdf_object in pdf.objects.values():
        if isinstance(pdf_object, FreeObject):
            continue

        print(pdf_object)

Note that we check for :class:`~pdfnaut.cos.reader.FreeObject` rather than :class:`.FreeXRefEntry`. This is the abstraction used by the object store to represent free entries.

Traversing a document
---------------------

Traversing the document will allow us to extract information about its contents. Let's take, for example, the ``sample.pdf`` file available in our `test suite <https://github.com/aescarias/pdfnaut/tree/main/tests/docs>`_. To extract the contents of a page, we must first find the document's catalog. The catalog includes references to important objects in the PDF. The catalog is stored in the ``Root`` key of the document's trailer.

.. code-block:: python

    >>> root = pdf.trailer["Root"]
    >>> root
    {'Outlines': PdfReference(object_number=2, generation=0),
     'Pages': PdfReference(object_number=3, generation=0),
     'Type': PdfName(value=b'Catalog')}

Two items of note can be found: *Outlines* and *Pages*. 

- The ``Outlines`` key stores the document's outline tree (commonly referred to as "bookmarks").
- The ``Pages`` key stores the document's page tree, which is what we are interested in.

.. note::

    To avoid wrapping each dictionary or array index call with :meth:`~pdfnaut.cos.reader.PdfReader.get_object`, pdfnaut and other PDF libraries will automatically resolve these references when indexing. If you are interested in the actual references, both :class:`~pdfnaut.cos.objects.containers.PdfArray` and :class:`~pdfnaut.cos.objects.containers.PdfDictionary` have a ``data`` attribute containing the raw object.

.. code-block:: python

    >>> root["Pages"]
    {'Count': 2,
     'Kids': [PdfReference(object_number=4, generation=0),
              PdfReference(object_number=6, generation=0)],
     'Type': PdfName(value=b'Pages')}

The page tree is seen above. As this document only has 2 pages, they are directly referenced in the *Kids* array of the root node. In larger documents, it is not uncommon to see the pages split into multiple nodes (i.e. a balanced tree) for performance reasons.

Next, we can extract the first page of the document:

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

Above we see the actual page. This dictionary includes the *media box* which specifies the dimensions of the page when shown, a reference to its parent, the resources used such as the font, and the contents of the page. We are looking for the contents of the page and so we can retrieve the content stream from the *Contents* key.

.. code-block:: python

    >>> first_page["Contents"]
    PdfStream(details={'Length': 1074})

We find ourselves with a stream. The contents of pages are defined in streams known as **content streams**. Content streams include instructions on how a PDF processor should render the page. In this case, the stream is encoded as is and so we can easily read it.

.. code-block:: python

    >>> first_page["Contents"].decode()
    b'2 J\r\nBT\r\n0 0 0 rg\r\n/F1 0027 Tf\r\n57.3750 722.2800 Td\r\n( A Simple PDF File ) Tj\r\nET\r\nBT\r\n/F1 0010 Tf\r\n69.2500 688.6080 Td\r\n[...]ET\r\n'

.. note::

    The stream above is abridged for demonstration purposes. Only a portion of its contents is shown.

A content stream is comprised of operators and operands (operands being specified first). In this case, the renderer would write "A Simple PDF File" at the position defined by the Td operands and applying the font specified in the Tf operands (``/F1`` is a name in our Resources dictionary which in our case points to Helvetica).

Writing a copy
--------------

To write a copy of the PDF document, you use :class:`.PdfWriter`. The PDF writer takes the reader's object store and serializes it into a new PDF document.

.. code-block:: python

    with pdfnaut.PdfReader("document.pdf") as pdf:
        pdfnaut.PdfWriter(pdf).save("copy.pdf")
