COS Objects Reference
=====================

The `PDF 2.0 specification <https://developer.adobe.com/document-services/docs/assets/5b15559b96303194340b99820d3a70fa/PDF_ISO_32000-2.pdf>`_ defines the following object types:

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
