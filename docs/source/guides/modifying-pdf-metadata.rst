Modifying PDF metadata
======================

PDFs may store metadata in two ways: the document information or "DocInfo" dictionary and metadata streams applicable to an individual object or the document itself.

The document information dictionary is specified in the ``/Info`` entry part of the PDF trailer. It provides document-level metadata and is simple to work with. PDF 2.0 has deprecated most of its keys in favor of using metadata streams.

Metadata streams store metadata in `XMP <https://en.wikipedia.org/wiki/Extensible_Metadata_Platform>`_ format and are the recommended way of applying object or document-level metadata.

pdfnaut can natively read from and write to document information dictionaries. Metadata streams are currently read-only.

Reading document information
----------------------------

The DocInfo dictionary can be accessed using the :attr:`.PdfDocument.info` attribute. If you want a list of all fields available, you can look at the :class:`.Info` class.

Note that the DocInfo dictionary and all of its fields are optional (may be ``None``).

.. code-block:: python
    
    from pdfnaut import PdfDocument
    
    doc = PdfDocument.from_filename("./tests/docs/sample.pdf")
    # It is possible for a document to not have DocInfo
    assert doc.info is not None, "No document information available."
    
    print(doc.info.title) # None
    print(doc.info.producer) # Nevrona Designs


Writing document information
----------------------------

Adding or modifying metadata can be done by modifying the respective attributes. Read :class:`.Info` for information about each entry.

.. code-block:: python

    import datetime

    from pdfnaut import PdfDocument
    from pdfnaut.objects.trailer import Info
    
    doc = PdfDocument.from_filename("./tests/docs/sample.pdf")
    if doc.info is None:
        # Creates a new DocInfo dictionary if not specified.
        doc.info = Info()
    
    doc.info.title = "Sample PDF file"
    doc.info.modify_date = datetime.datetime.now()

    doc.save("new-sample.pdf")

If you want to remove the DocInfo dictionary, simply set ``doc.info`` to None.

.. code-block:: python

    from pdfnaut import PdfDocument

    doc = PdfDocument.from_filename("./tests/docs/sample.pdf")
    doc.info = None
    
    doc.save("new-sample.pdf")
