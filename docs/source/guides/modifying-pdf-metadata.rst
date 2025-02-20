Modifying PDF metadata
======================

PDFs may store metadata in two ways: the document information or "DocInfo" dictionary and metadata streams applicable to either an individual object or to the document itself.

The document information dictionary is specified in the ``/Info`` key of the PDF trailer. It provides document-level metadata and is easy to work with. PDF 2.0 has however deprecated most of its keys in favor of using metadata streams.

Metadata streams store metadata in `XMP <https://en.wikipedia.org/wiki/Extensible_Metadata_Platform>`_ format and are the recommended way of applying object or document-level metadata.

pdfnaut can natively read from and write to both document information dictionaries and metadata streams.

Reading document information
----------------------------

The DocInfo dictionary can be accessed using the :attr:`.PdfDocument.doc_info` attribute. If you want a list of all fields available, you can look at the :class:`.Info` class.

Note that the DocInfo dictionary and all of its fields are optional (may be ``None``).

.. code-block:: python
    
    from pdfnaut import PdfDocument
    
    pdf = PdfDocument.from_filename("./tests/docs/sample.pdf")
    # It is possible for a document to not have DocInfo
    assert pdf.doc_info is not None, "No document information available."
    
    print(pdf.doc_info.title) # None
    print(pdf.doc_info.producer) # Nevrona Designs


Reading XMP metadata
--------------------

The XMP metadata stored at the document level can be accessed using the :attr:`.PdfDocument.xmp_info` attribute. For information on available properties, see :class:`.XmpMetadata`.

.. code-block:: python
    
    from pdfnaut import PdfDocument
    
    doc = PdfDocument.from_filename("./tests/docs/pdf2-incremental.pdf")
    # It is possible for a document to not have XMP metadata
    assert doc.xmp_info is not None, "No document XMP metadata available."
    
    print(doc.xmp_info.dc_title["x-default"]) # A simple PDF 2.0 example file
    print(doc.xmp_info.xmp_create_date) # 2017-05-24 10:30:11+00:00
    print(doc.xmp_info.dc_creator)  # ["Datalogics Incorporated"]


Writing document information
----------------------------

Adding or modifying document information can be done by modifying the respective attributes in :attr:`.PdfDocument.doc_info`. Read :class:`.Info` for information on each entry.

.. code-block:: python

    import datetime

    from pdfnaut import PdfDocument
    from pdfnaut.objects.trailer import Info
    
    pdf = PdfDocument.from_filename("./tests/docs/sample.pdf")
    if pdf.doc_info is None:
        # Creates a new DocInfo dictionary if not specified.
        pdf.doc_info = Info()
    
    pdf.doc_info.title = "Sample PDF file"
    pdf.doc_info.modify_date = datetime.datetime.now()

    pdf.save("new-sample.pdf")

If you want to remove the DocInfo dictionary, simply set the ``doc_info`` attribute to None.

.. code-block:: python

    from pdfnaut import PdfDocument

    pdf = PdfDocument.from_filename("./tests/docs/sample.pdf")
    pdf.doc_info = None
    
    pdf.save("new-sample.pdf")


Writing XMP metadata
--------------------

Adding or modifying XMP metadata can be modified in a similar manner to modifying the DocInfo dictionary by modifying the respective attributes. Read :class:`.XmpMetadata` for information on each entry.

.. code-block:: python

    import datetime

    from pdfnaut import PdfDocument
    from pdfnaut.objects.xmp import XmpMetadata
    
    doc = PdfDocument.from_filename("./tests/docs/sample.pdf")
    if doc.xmp_info is None:
        # Creates a new XMP metadata object if not specified.
        doc.xmp_info = XmpMetadata()
    
    doc.xmp_info.dc_title = "Sample PDF file"
    doc.xmp_info.xmp_modify_date = datetime.datetime.now()

    doc.save("new-sample.pdf")

If you want to remove the document-level XMP metadata, simply set the ``xmp_info`` attribute to None.

.. code-block:: python

    from pdfnaut import PdfDocument

    doc = PdfDocument.from_filename("./tests/docs/sample.pdf")
    doc.xmp_info = None
    
    doc.save("new-sample.pdf")
