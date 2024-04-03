Objects Reference
=================

The PDF specification recognizes 8 basic objects. pdfnaut attempts to map these objects as closely as possible to their equivalent Python objects.

.. csv-table:: pdfnaut Object Mapping
    :header: "PDF Object", "Python Object"

    "Booleans (true/false)", "``True``/``False``"
    "Integers (123)", "``int``"
    "Real numbers (123.456)", "``float``"
    "Literal strings (``(hello world)``)", "``bytes``"
    "Hexadecimal strings (``<616263>``)", ":class:`~pdfnaut.objects.base.PdfHexString`"
    "Names (``/Type``)", ":class:`~pdfnaut.objects.base.PdfName`"
    "Arrays (``[1 2 3]``)", "``list``"
    "Dictionaries (``<< /Type /Catalog ... >>``)", "``dict``"
    "Streams", ":class:`~pdfnaut.objects.stream.PdfStream`"
    "Null", ":class:`~pdfnaut.objects.base.PdfNull`"
    "Indirect references (1 0 R)", ":class:`~pdfnaut.objects.base.PdfIndirectRef`"

Base Objects
------------

.. automodule:: pdfnaut.objects.base
    :members:

Stream Objects
--------------

.. automodule:: pdfnaut.objects.stream
    :members:

XRef Objects
------------

.. automodule:: pdfnaut.objects.xref
    :members:
