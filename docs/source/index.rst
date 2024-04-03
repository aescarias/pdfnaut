.. pdfnaut documentation master file, created by
   sphinx-quickstart on Fri Mar  1 16:14:45 2024.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

pdfnaut
=======

.. warning::
   This library is currently in a very early stage of development. It has only been tested with a small set of known to be spec-compliant documents.

pdfnaut aims to become a PDF processor for Python -- a library capable of reading and writing PDF documents.

pdfnaut can currently read and write PDF documents at a low level. **No high-level APIs are currently provided.**

Features
--------

- Low level PDF manipulation
- Encryption (AES/ARC4)
- Serialization of basic documents

Examples
--------

The next example illustrates how ``pdfnaut`` can currently be used to read an existing PDF. Note that, due to the low-level nature of ``pdfnaut``, reading and extracting data from each document will require existing knowledge of its structure.

.. code-block:: python

   from pdfnaut import PdfParser

   with open("tests/docs/sample.pdf", "rb") as doc:
      pdf = PdfParser(doc.read())
      pdf.parse()

      # Get the pages object from the trailer
      root = pdf.resolve_reference(pdf.trailer["Root"])
      page_tree = pdf.resolve_reference(root["Pages"])
      
      # Get the contents of the first page
      page = pdf.resolve_reference(page_tree["Kids"][0])
      page_stream = pdf.resolve_reference(page["Contents"])
      print(page_stream.decompress())


.. toctree::
   :maxdepth: 2
   :caption: Reference
   :hidden:
   
   PDF Tokenizer <reference/parsers/simple>
   PDF Parser <reference/parsers/pdf>
   PDF Serializer <reference/serializer>
   Objects <reference/objects>
   Exceptions <reference/exceptions>
   Filters <reference/filters>

.. toctree::
   :maxdepth: 2
   :caption: Guides
   :hidden:

   Reading a PDF <guides/reading-pdf>
   Writing a PDF <guides/writing-pdf>
 

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
