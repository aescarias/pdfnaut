Modifying PDF metadata
======================

PDFs can store metadata in two ways: 

- the document information or "DocInfo" dictionary 
- metadata streams applicable to either an individual object or to the document itself.

The document information dictionary is specified in the ``/Info`` key of the PDF trailer. It provides document-level metadata and is easy to work with. PDF 2.0 has however deprecated most of its keys in favor of using metadata streams.

Metadata streams store metadata in `XMP <https://en.wikipedia.org/wiki/Extensible_Metadata_Platform>`_ format and are the recommended way of applying object or document-level metadata.

pdfnaut can natively read from and write to both document information dictionaries and metadata streams.

Reading document information
----------------------------

The DocInfo dictionary can be accessed using the :attr:`.PdfDocument.doc_info` attribute (see :class:`.Info` for a list of available fields).

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

Document-level XMP metadata can be accessed using the :attr:`.PdfDocument.xmp_info` attribute. For information on available properties, see :class:`.XmpMetadata`.

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

This is also the case if you want to remove fields from the DocInfo dictionary. Setting a field to ``None`` or using ``del`` on the field will remove it.


Writing XMP metadata
--------------------

Adding or modifying XMP metadata can be modified in a similar manner to modifying the DocInfo dictionary by modifying the respective attributes. Read :class:`.XmpMetadata` for information on each entry.

.. code-block:: python

    import datetime

    from pdfnaut import PdfDocument
    from pdfnaut.objects.xmp import XmpMetadata
    
    pdf = PdfDocument.from_filename("./tests/docs/sample.pdf")
    if pdf.xmp_info is None:
        # Creates a new XMP metadata object if not specified.
        pdf.xmp_info = XmpMetadata()
    
    pdf.xmp_info.dc_title = "Sample PDF file"
    pdf.xmp_info.xmp_modify_date = datetime.datetime.now()

    pdf.save("new-sample.pdf")

If you want to remove the document-level XMP metadata, simply set the ``xmp_info`` attribute to None.

.. code-block:: python

    from pdfnaut import PdfDocument

    doc = PdfDocument.from_filename("./tests/docs/sample.pdf")
    doc.xmp_info = None
    
    doc.save("new-sample.pdf")

Removing a field can be done by setting it to ``None`` or by using ``del``.


Reconciling PDF metadata
------------------------

As mentioned earlier, a PDF supports two types of metadata: DocInfo and XMP. Both sources should ideally be equivalent so that PDF processors can retrieve the same metadata regardless of the source they use to extract it.

:class:`.PdfDocument` provides the :meth:`.PdfDocument.copy_metadata` method which allows copying from one metadata source to another. This ensures that the data in both sources is equivalent.

.. code-block:: python

    from pdfnaut import MetadataCopyDirection, PdfDocument
    
    pdf = PdfDocument.from_filename(r"tests/docs/pdf2-incremental.pdf")

    print(pdf.doc_info)  # None
    print(pdf.xmp_info)  # <XmpMetadata pdf_producer="Datalogics" [...]>

    pdf.copy_metadata(MetadataCopyDirection.XMP_TO_DOC_INFO)
    print(pdf.doc_info)  # Info(producer="Datalogics", ...)

Because the structure of the DocInfo dictionary and XMP differ, the mappings described in ISO 32000-2:2020 (PDF 2.0) § 14.3.3 are used. Note that not all metadata fields in XMP can be copied to DocInfo and vice versa. Only the standard properties are mapped.

.. csv-table:: XMP - DocInfo Mapping
    :header: "XMP", "DocInfo"

    "pdf:Producer", "Producer"
    "pdf:Keywords", "Keywords"
    "pdf:PDFVersion", "N/A [#f1]_"
    "pdf:Trapped", "Trapped"
    "xmp:CreatorTool", "Creator"
    "xmp:CreateDate", "CreationDate"
    "xmp:MetadataDate", "ModDate"
    "xmp:ModifyDate", "ModDate"
    "dc:title", "Title [#f2]_"
    "dc:creator", "Author [#f3]_"
    "dc:description", "Subject [#f2]_"
    "dc:subject", "N/A [#f1]_"
    "dc:rights", "N/A [#f1]_"
    "dc:format", "N/A [#f1]_"

.. rubric:: Footnotes

.. [#f1] Some fields do not have equivalents in the DocInfo dictionary, hence they cannot be mapped.
.. [#f2] ``dc:title`` and ``dc:description`` are language-alternate properties, meaning they store a mapping of language names to text strings. When copying from XMP to DocInfo, the ``x-default`` key of the property is copied (or the first available entry otherwise).
.. [#f3] ``dc:creator`` is an array of text strings. When copying from XMP to DocInfo, the value of ``Author`` will be the concatenation of the values of ``dc:creator``, separated by semicolons.



