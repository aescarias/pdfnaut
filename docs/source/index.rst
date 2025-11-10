pdfnaut
=======

.. warning::
   This library is currently in a very early stage of development. Expect bugs or issues.

pdfnaut aims to become a PDF processor for Python capable of reading and writing PDF documents.

pdfnaut provides high-level APIs for performing the following actions:

- Reading compressed & encrypted PDF documents (AES/ARC4, see note below).
- Inspecting PDF structure.
- Viewing and editing document metadata.
- Appending, inserting, and removing pages.
- Building PDFs from scratch.

Install
-------

``pdfnaut`` can be installed from PyPI. pdfnaut requires at least Python 3.9 or later.

.. tab-set::

    .. tab-item:: Linux/Mac

      .. code-block:: sh

         python3 -m pip install pdfnaut 

    .. tab-item:: Windows

      .. code-block:: sh

         python -m pip install pdfnaut

.. important:: 
   To use pdfnaut for reading encrypted documents, you must also install a crypt provider as described in :ref:`standard security handler`.

Examples
--------

pdfnaut provides its API through :class:`~pdfnaut.document.PdfDocument` which allows performing common actions within a PDF. For example, to access the content stream of the first page in the document, you can do as follows:

.. code-block:: python
   
   from pdfnaut import PdfDocument

   pdf = PdfDocument.from_filename("tests/docs/sample.pdf")
   for operator in pdf.pages[0].content_stream:
      print(operator)

Reading document information from a PDF is also simple:

.. code-block:: python
   
   from pdfnaut import PdfDocument

   pdf = PdfDocument.from_filename("tests/docs/sample.pdf")
   print(pdf.doc_info.title)
   print(pdf.doc_info.author)


.. toctree::
   :maxdepth: 2
   :caption: Links
   :hidden:

   Github <https://github.com/aescarias/pdfnaut>
   PyPI <https://pypi.org/project/pdfnaut>

.. toctree::
   :maxdepth: 2
   :caption: API Reference
   :hidden:

   PDF Tokenizer <reference/cos/tokenizer>
   PDF Parser <reference/cos/parser>
   PDF Serializer <reference/cos/serializer>
   PDF Document <reference/document>
   PDF Objects <reference/objects>
   PDF Page List <reference/page_list>
   Common Objects <reference/common>
   COS Objects <reference/cos/objects>
   Filters <reference/filters>
   Exceptions <reference/exceptions>
   Standard Security Handler <reference/standard_handler>

.. toctree::
   :maxdepth: 2
   :caption: User Guides
   :hidden:

   Building a PDF from scratch <guides/building-pdf>
   Modifying PDF metadata <guides/modifying-pdf-metadata>
   Reading and inspecting a PDF <guides/reading-pdf>
   Viewer preferences <guides/viewer-preferences>
   Working with outlines <guides/working-with-outlines>
   Working with pages <guides/working-with-pages>

.. toctree::
   :maxdepth: 2
   :caption: Developer Guides
   :hidden:

   Dictionary Models and Accessors <guides/dev-dictmodels>

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
