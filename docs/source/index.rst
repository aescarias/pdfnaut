.. pdfnaut documentation master file, created by
   sphinx-quickstart on Fri Mar  1 16:14:45 2024.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

pdfnaut
=======

.. warning::
   This library is currently in a very early stage of development. It has only been tested with a small set of known to be spec-compliant documents.

pdfnaut aims to become a PDF processor for Python -- a library capable of reading and writing PDF documents.

pdfnaut currently works best for handling low-level scenarios. A high-level reader (:class:`~pdfnaut.document.PdfDocument`) is provided although it's pretty much in the works.

Features
--------

- Low level, typed PDF manipulation
- Encryption (AES/ARC4)
- Document building/serialization

Install
-------

``pdfnaut`` can be installed from PyPI:

.. tab-set::

    .. tab-item:: Linux/Mac

      .. code-block:: sh

         python3 -m pip install pdfnaut 

    .. tab-item:: Windows

      .. code-block:: sh

         python -m pip install pdfnaut

.. important:: 
   While ``pdfnaut`` supports encryption with ARC4 and AES, it does not include their implementations by default. You must either supply your own or preferably install a supported package like ``pycryptodome`` that can provide these.

Examples
--------

The low-level API, seen in the example below, illustrates how ``pdfnaut`` can be used to inspect PDFs and retrieve information. Of course, each PDF will have a different structure and so knowledge of that structure is needed.

.. code-block:: python

   from pdfnaut import PdfParser

   with open("tests/docs/sample.pdf", "rb") as doc:
      pdf = PdfParser(doc.read())
      pdf.parse()

      # Get the pages object from the trailer
      root = pdf.get_object(pdf.trailer["Root"])
      page_tree = pdf.get_object(root["Pages"])
      
      # Get the contents of the first page
      page = pdf.get_object(page_tree["Kids"][0])
      page_stream = pdf.get_object(page["Contents"])
      print(page_stream.decode())

The high-level API currently provides some abstraction for :class:`~pdfnaut.cos.parser.PdfParser`. Notably, it includes a helper property for accessing pages called :attr:`~pdfnaut.document.PdfDocument.flattened_pages`.

.. code-block:: python
   
   from pdfnaut import PdfDocument

   pdf = PdfDocument.from_filename("tests/docs/sample.pdf")
   first_page = list(pdf.flattened_pages)[0]
   if "Contents" in first_page:
      first_page_stream = pdf.get_object(first_page["Contents"])
      print(first_page_stream.decode())


.. toctree::
   :maxdepth: 2
   :caption: Reference
   :hidden:
   
   PDF Tokenizer <reference/cos/tokenizer>
   PDF Parser <reference/cos/parser>
   PDF Serializer <reference/cos/serializer>
   PDF Document <reference/document>
   Objects <reference/cos/objects>
   Filters <reference/filters>
   Exceptions <reference/exceptions>
   Standard Security Handler <reference/standard_handler>
   Typings <reference/typings>

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
