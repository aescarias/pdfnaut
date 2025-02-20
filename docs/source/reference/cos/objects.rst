COS Objects Reference
=====================

The `PDF 2.0 specification <https://developer.adobe.com/document-services/docs/assets/5b15559b96303194340b99820d3a70fa/PDF_ISO_32000-2.pdf>`_ defines the following basic object types:

.. csv-table:: pdfnaut Object Mapping
    :header: "PDF Object", "Python Object"

    "Booleans (true/false)", "``True`` / ``False``"
    "Integers (123)", "``int``"
    "Real numbers (123.456)", "``float``"
    "Literal strings (``(hello world)``)", "``bytes``"
    "Hexadecimal strings (``<616263>``)", ":class:`~pdfnaut.cos.objects.base.PdfHexString`"
    "Names (``/Type``)", ":class:`~pdfnaut.cos.objects.base.PdfName`"
    "Arrays (``[1 2 3]``)", ":class:`~pdfnaut.cos.objects.containers.PdfArray`"
    "Dictionaries (``<< /Type /Catalog ... >>``)", ":class:`~pdfnaut.cos.objects.containers.PdfDictionary`"
    "Streams", ":class:`~pdfnaut.cos.objects.stream.PdfStream`"
    "Null", ":class:`~pdfnaut.cos.objects.base.PdfNull`"
    "Indirect references (1 0 R)", ":class:`~pdfnaut.cos.objects.base.PdfReference`"

The spec also defines general-purpose data structures built from the basic object types.

* Strings are divided into:

  * ASCII strings.
  * Byte strings: hex strings or literal strings containing binary data.
  * PDFDocEncoded strings
  * Text strings: encoded in either PDFDocEncoding, UTF-16BE or (PDF 2.0) UTF-8. The latter was introduced in PDF 2.0

* Dates: implemented as :func:`~pdfnaut.common.dates.encode_iso8824` and :func:`~pdfnaut.common.dates.parse_iso8824`.
* The following data structures are currently not implemented explicitly:

  * File specifications
  * Functions
  * Name trees
  * Number trees
  * Rectangles
  * Text streams


Base Objects
------------

.. automodule:: pdfnaut.cos.objects.base
    :members:

Stream Objects
--------------

.. automodule:: pdfnaut.cos.objects.stream
    :members:

Container Objects
-----------------

.. automodule:: pdfnaut.cos.objects.containers
    :members:

XRef Objects
------------

.. automodule:: pdfnaut.cos.objects.xref
    :members:
