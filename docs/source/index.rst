.. pdfnaut documentation master file, created by
   sphinx-quickstart on Fri Mar  1 16:14:45 2024.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

pdfnaut
=======

.. warning::
   This library is currently in a very early stage of development. It has only been tested with a small set of known to be spec-compliant documents. 

pdfnaut aims to become a PDF processor for Python -- a library capable of reading and writing PDF documents.

pdfnaut currently works best for handling low-level scenarios. A high-level reader and writer (:class:`~pdfnaut.document.PdfDocument`) is available although it's a work in progress.

pdfnaut is currently capable of the following:

- Reading compressed & encrypted PDF documents (AES/ARC4, see note below).
- Inspecting PDFs and extracting data from them.
- Viewing and editing document information.
- Building PDFs from scratch.

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
   If you plan to use ``pdfnaut`` with encrypted documents, you must also install a crypt provider dependency such as pyca/cryptography or PyCryptodome. See :ref:`standard security handler`.

Examples
--------

The low-level API, seen in the example below, illustrates how ``pdfnaut`` can be used to inspect PDFs and retrieve information. Of course, each PDF will have a different structure and so knowledge of that structure is needed.

.. code-block:: python

   from pdfnaut import PdfParser

   with open("tests/docs/sample.pdf", "rb") as doc:
      pdf = PdfParser(doc.read())
      pdf.parse()

      pages = pdf.trailer["Root"]["Pages"]

      first_page_stream = pages["Kids"][0]["Contents"]
      print(first_page_stream.decode())

The high-level API currently provides some abstraction for :class:`~pdfnaut.cos.parser.PdfParser`. Notably, it includes a helper property for accessing pages called :attr:`~pdfnaut.document.PdfDocument.flattened_pages`.

.. code-block:: python
   
   from pdfnaut import PdfDocument

   pdf = PdfDocument.from_filename("tests/docs/sample.pdf")
   first_page = next(pdf.flattened_pages)
   
   if first_page.content_stream:
      print(first_page.content_stream.contents)


.. toctree::
   :maxdepth: 2
   :caption: Reference
   :hidden:

   PDF Tokenizer <reference/cos/tokenizer>
   PDF Parser <reference/cos/parser>
   PDF Serializer <reference/cos/serializer>
   PDF Document <reference/document>
   PDF Objects <reference/objects>
   Common Objects <reference/common>
   COS Objects <reference/cos/objects>
   Filters <reference/filters>
   Exceptions <reference/exceptions>
   Standard Security Handler <reference/standard_handler>

.. toctree::
   :maxdepth: 2
   :caption: Guides
   :hidden:

   Reading and inspecting a PDF <guides/reading-pdf>
   Building a PDF from scratch <guides/building-pdf>
   Modifying PDF metadata <guides/modifying-pdf-metadata>


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
