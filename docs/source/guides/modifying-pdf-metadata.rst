Modifying PDF metadata
======================

PDFs may store metadata in two ways: the document information dictionary (the ``/Info`` entry part of the PDF trailer) or object-level metadata streams applicable to an individual object or the document itself.

The document information dictionary is simple and applies to the document itself. Most fields in this dictionary were deprecated in PDF 2.0 in favor of using metadata streams.

Metadata streams use `XMP <https://en.wikipedia.org/wiki/Extensible_Metadata_Platform>`_ for storing information and is the recommended way of applying object or document-level metadata.

pdfnaut can natively read from and write to document information dictionaries. Metadata streams using XMP currently have no special support.

Reading document information
----------------------------

The DocInfo dictionary is exposed as :attr:`.PdfDocument.info`. A list of all fields for the DocInfo dictionary is exposed as :class:`.Info`. The DocInfo dictionary is optional (may be ``None``) and all of its fields are also optional. 

.. code-block:: python
    
    from pdfnaut import PdfDocument
    
    doc = PdfDocument.from_filename("../tests/docs/sample.pdf")
    # It is possible for a document to not have information
    assert doc.info is not None, "No document information available."
    
    print(doc.info.title) # None
    print(doc.info.producer) # Nevrona Designs

Writing document information
----------------------------

Modifying the docinfo is as simple as setting one of the fields to a new value:

.. code-block:: python

    import datetime

    from pdfnaut import PdfDocument
    from pdfnaut.objects.trailer import Info
    
    doc = PdfDocument.from_filename("../tests/docs/sample.pdf")
    if doc.info is None:
        doc.info = Info()
    
    doc.info.title = "Sample PDF file"
    doc.info.modify_date = datetime.datetime.now()

    doc.save("new-sample.pdf")

If you want to remove the docinfo dictionary, you can set ``doc.info`` to None.
